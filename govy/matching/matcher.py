"""
govy.matching.matcher — Motor de matching determinístico (regex-first).

Regras:
- MATCH = atende EXATAMENTE todos os componentes, sem waivers.
- MATCH_WITH_WAIVER = teria gaps, mas waivers suprimiram todos.
- UNMATCH = existe ≥1 gap não coberto por waiver.
- Para medicamentos: qualquer diferença (inclusive "supera") = gap.
- Se o item exige volume/apresentação, isso vira baseline obrigatório.
- Bula pode ter várias apresentações: matching vale isoladamente por apresentação.
  => Se existir pelo menos 1 apresentação sem gaps efetivos → MATCH ou MATCH_WITH_WAIVER.
  => As demais ficam como "outras apresentações" (informativo).
- Waivers ativos sempre geram DISCLAIMER de risco (inexecução contratual).

Output pensado para popups: objetivo, curto, com GAPs compactos + evidência.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from .models import (
    Gap,
    GapCode,
    GAP_COMPACT,
    ItemRequirement,
    MatchResult,
    Presentation,
    WaiverConfig,
)
from .normalizers import normalize_text, parse_number
from .parsers import RE_PKG_VOL, extract_presentations_from_bula_text


# =============================================================================
# FORMATAÇÃO AUXILIAR
# =============================================================================

def _fmt_conc(num: Optional[float], unit: str, den_unit: str) -> str:
    """Formata concentração para exibição (ex: '10 MG/ML')."""
    if num is None:
        return ""
    if abs(num - round(num)) < 1e-9:
        num_s = str(int(round(num)))
    else:
        num_s = f"{num:.6g}"
    return f"{num_s} {unit}/{den_unit}"


def _fmt_pkg_vol(pkg: str, vol: Optional[float], unit: str) -> str:
    """Formata embalagem + volume (ex: 'FRASCO-AMPOLA 50 ML')."""
    if vol is None:
        return pkg
    if abs(vol - round(vol)) < 1e-9:
        vol_s = str(int(round(vol)))
    else:
        vol_s = f"{vol:.6g}"
    return f"{pkg} {vol_s} {unit}"


def _evidence_around(text: str, m: Optional[re.Match], window: int = 70) -> Optional[str]:
    """Extract short evidence snippet around a regex match."""
    if not m:
        return None
    left = max(0, m.start() - window)
    right = min(len(text), m.end() + window)
    snippet = text[left:right].strip()
    snippet = re.sub(r"\s+", " ", snippet)
    return snippet[:220] if snippet else None


# =============================================================================
# MATCHING ENGINE
# =============================================================================

WAIVER_DISCLAIMER = (
    "RISCO: tolerancias podem nao atender edital e gerar inexecucao contratual."
)

# Mapping GapCode → waiver field name
_GAP_WAIVER_FIELD = {
    # ACTIVE_MISSING removido: substancia/principio ativo NUNCA e waivable (CP16).
    GapCode.CONC_MISSING: "ignore_concentration",
    GapCode.CONC_MISMATCH: "ignore_concentration",
    GapCode.FORM_MISSING: "ignore_form",
    GapCode.FORM_MISMATCH: "ignore_form",
    GapCode.PKG_MISSING: "ignore_pkg",
    GapCode.PKG_MISMATCH: "ignore_pkg",
    GapCode.VOLUME_MISSING: "ignore_volume",
    GapCode.VOLUME_MISMATCH: "ignore_volume",
}

# Constante explicita: gaps elegiveis a waiver (auditoria).
# ACTIVE_MISSING fica FORA para sempre.
WAIVABLE_GAPS = frozenset(_GAP_WAIVER_FIELD.keys())


def _split_by_waivers(
    gaps: List[Gap], waivers: WaiverConfig
) -> Tuple[List[Gap], List[Gap]]:
    """Split gaps into (effective, waived)."""
    effective = []
    waived = []
    for g in gaps:
        field_name = _GAP_WAIVER_FIELD.get(g.code)
        if field_name and getattr(waivers, field_name, False):
            waived.append(g)
        else:
            effective.append(g)
    return effective, waived


# Broader search for ANY packaging term (for evidence when canonical PKG missing)
_RE_PKG_ANY = re.compile(
    r"(?i)\b(FRASCO-AMPOLA|AMPOLA|FRASCO|SERINGA|BISNAGA|TUBO|BLISTER)\b"
)

# Unit conversion to common base (MG for mass, ML for volume)
_MASS_TO_MG = {"MG": 1.0, "G": 1000.0, "MCG": 0.001}
_VOL_TO_ML = {"ML": 1.0, "L": 1000.0}


def _to_mg(value: float, unit: str) -> Optional[float]:
    """Convert mass to MG. Returns None for non-mass units (e.g. UI)."""
    factor = _MASS_TO_MG.get(unit)
    return value * factor if factor is not None else None


def _to_ml(value: float, unit: str) -> Optional[float]:
    """Convert volume to ML. Returns None for unknown units."""
    factor = _VOL_TO_ML.get(unit)
    return value * factor if factor is not None else None


def _nearly_equal(a: float, b: float, rel_tol: float = 1e-6) -> bool:
    """Compare floats with relative tolerance (handles unit conversion rounding)."""
    if a == b:
        return True
    largest = max(abs(a), abs(b))
    if largest == 0:
        return True
    return abs(a - b) / largest < rel_tol


def _conc_equal(
    item_requirement: ItemRequirement, p: Presentation
) -> bool:
    """
    Compare concentration with unit conversion (CP15).

    Cross-multiply avoids float division artifacts:
      req 10 MG/ML + bula 500 MG/50 ML → 10*50 == 500 → True
    Unit conversion handles pharmacological equivalence:
      req 10 MG/ML + bula 0.01 G/ML → 10 MG == 10 MG → True
      req 100 UI/ML + bula 100 MG/ML → UI not convertible → False
      req 100 UI/ML + bula 100000 UI/L → 100 UI/ML == 100 UI/ML → True
    """
    if p.conc_unit is None or p.conc_den_unit is None:
        return False

    req_num_mg = _to_mg(item_requirement.conc_num, item_requirement.conc_unit)
    p_conc_mg = _to_mg(p.conc_num, p.conc_unit) if p.conc_num is not None else None
    req_den_ml = _to_ml(1.0, item_requirement.conc_den_unit)
    p_den_ml = _to_ml(1.0, p.conc_den_unit)

    if req_num_mg is None:
        # Non-convertible numerator (UI etc.) — require exact numerator unit
        if p.conc_unit != item_requirement.conc_unit:
            return False
        if p.conc_num is None:
            return False
        # Denominator: convert to ML if both sides are convertible
        if req_den_ml is not None and p_den_ml is not None:
            req_per_ml = item_requirement.conc_num / req_den_ml
            p_per_ml = p.conc_num / p_den_ml
            return _nearly_equal(req_per_ml, p_per_ml)
        # Non-convertible denominator — require exact match
        if p.conc_den_unit != item_requirement.conc_den_unit:
            return False
        return _nearly_equal(p.conc_num, item_requirement.conc_num)

    # Both sides mass-convertible — normalize to MG/ML
    if req_den_ml is None or p_den_ml is None:
        return False

    # Cross-multiply path: dose/vol available on bula side
    if p.dose is not None and p.vol is not None and p.dose_unit and p.vol_unit:
        dose_mg = _to_mg(p.dose, p.dose_unit)
        vol_ml = _to_ml(p.vol, p.vol_unit)
        if dose_mg is not None and vol_ml is not None and vol_ml > 0:
            # Cross-multiply: req_num_mg * vol_ml == dose_mg * req_den_ml
            lhs = req_num_mg * vol_ml
            rhs = dose_mg * req_den_ml
            return _nearly_equal(lhs, rhs)

    # Fallback: compare derived conc_num after normalization to MG/ML
    if p_conc_mg is None:
        return False
    req_conc_normalized = req_num_mg / req_den_ml
    p_conc_normalized = p_conc_mg / p_den_ml
    return _nearly_equal(req_conc_normalized, p_conc_normalized)


def _req_snippet(raw: str, max_len: int = 120) -> Optional[str]:
    """Extract short snippet from ItemRequirement.raw for gap context (CP18)."""
    if not raw:
        return None
    s = re.sub(r"\s+", " ", raw).strip()
    return s[:max_len] if s else None


def _compute_all_gaps(
    item_requirement: ItemRequirement,
    p: Presentation,
    t: str,
    principle_ok: bool,
    pkg_match: Optional[re.Match],
) -> List[Gap]:
    """
    Compute ALL gaps for a presentation (ignoring waivers).
    Waivers are applied by the caller via _split_by_waivers().
    """
    gaps: List[Gap] = []
    snippet = _req_snippet(item_requirement.raw)

    req_conc = _fmt_conc(
        item_requirement.conc_num,
        item_requirement.conc_unit,
        item_requirement.conc_den_unit,
    )
    req_form = item_requirement.form
    req_pkgvol = _fmt_pkg_vol(
        item_requirement.pkg, item_requirement.vol, item_requirement.vol_unit
    )

    # --- PRINCIPIO ATIVO ---
    if not principle_ok:
        gaps.append(Gap(
            GapCode.ACTIVE_MISSING,
            required=item_requirement.principle,
            req_snippet=snippet,
        ))

    # --- CONCENTRACAO (cross-multiply quando possível) ---
    if p.conc_num is None or p.conc_unit is None or p.conc_den_unit is None:
        gaps.append(Gap(
            GapCode.CONC_MISSING,
            required=req_conc,
            evidence=p.evidence,
            req_snippet=snippet,
        ))
    else:
        if not _conc_equal(item_requirement, p):
            found_conc = _fmt_conc(p.conc_num, p.conc_unit, p.conc_den_unit)
            gaps.append(Gap(
                GapCode.CONC_MISMATCH,
                required=req_conc,
                found=found_conc,
                evidence=p.evidence,
                req_snippet=snippet,
            ))

    # --- FORMA FARMACEUTICA (estrita) ---
    if not p.form:
        gaps.append(Gap(
            GapCode.FORM_MISSING,
            required=req_form,
            evidence=p.evidence,
            req_snippet=snippet,
        ))
    elif normalize_text(p.form) != normalize_text(req_form):
        gaps.append(Gap(
            GapCode.FORM_MISMATCH,
            required=req_form,
            found=p.form,
            evidence=p.evidence,
            req_snippet=snippet,
        ))

    # --- EMBALAGEM (busca global) ---
    if not pkg_match:
        # Busca tolerante para evidence (pode achar "AMPOLA" mesmo que "FRASCO-AMPOLA" falte)
        any_pkg = _RE_PKG_ANY.search(t)
        pkg_ev = _evidence_around(t, any_pkg) if any_pkg else p.evidence
        gaps.append(Gap(
            GapCode.PKG_MISSING,
            required=item_requirement.pkg,
            found=any_pkg.group(1) if any_pkg else None,
            evidence=pkg_ev,
            req_snippet=snippet,
        ))

    # --- VOLUME (prefere RE_PKG_VOL packaging, fallback p.vol) ---
    # p.vol from dose/vol captures is the concentration DENOMINATOR (e.g. 10 in
    # "100 MG/10 ML"), NOT the packaging volume. Packaging volume comes from
    # RE_PKG_VOL (e.g. "FRASCO-AMPOLA 50 ML").
    vol_ok = False
    found_vol_str = None
    vol_evidence = None

    m_pkg_vol = RE_PKG_VOL.search(t)
    if m_pkg_vol:
        found_vol = parse_number(m_pkg_vol.group("vol"))
        found_unit = normalize_text(m_pkg_vol.group("unit"))
        found_vol_str = f"{found_vol:g} {found_unit}"
        vol_evidence = _evidence_around(t, m_pkg_vol)
        found_vol_ml = _to_ml(found_vol, found_unit)
        req_vol_ml = _to_ml(item_requirement.vol, item_requirement.vol_unit)
        vol_ok = (
            found_vol_ml is not None
            and req_vol_ml is not None
            and abs(found_vol_ml - req_vol_ml) < 1e-6
        )
    elif p.vol is not None and p.vol_unit is not None:
        found_vol_str = f"{p.vol:g} {p.vol_unit}"
        vol_evidence = p.evidence
        found_vol_ml = _to_ml(p.vol, p.vol_unit)
        req_vol_ml = _to_ml(item_requirement.vol, item_requirement.vol_unit)
        vol_ok = (
            found_vol_ml is not None
            and req_vol_ml is not None
            and abs(found_vol_ml - req_vol_ml) < 1e-6
        )

    if not vol_ok:
        gaps.append(Gap(
            GapCode.VOLUME_MISMATCH,
            required=req_pkgvol,
            found=found_vol_str,
            evidence=vol_evidence,
            req_snippet=snippet,
        ))

    return gaps


def match_item_to_bula(
    item_id: str,
    item_requirement: ItemRequirement,
    bula_text: str,
    waivers: WaiverConfig = WaiverConfig(),
) -> MatchResult:
    """
    Matching por apresentação (isolado).

    Status:
    - MATCH: ≥1 apresentação 100% aderente, sem waivers necessários.
    - MATCH_WITH_WAIVER: ≥1 apresentação aderente somente graças a waivers.
    - UNMATCH: nenhuma apresentação atende (mesmo com waivers).

    Args:
        item_id: Identificador do item (ex: "38")
        item_requirement: Requisito parseado do item do TR
        bula_text: Texto completo da bula/ficha (raw ou já normalizado)
        waivers: Tolerâncias opcionais

    Returns:
        MatchResult com status, gaps efetivos, waived_gaps, e apresentação.
    """
    t = normalize_text(bula_text)
    pres = extract_presentations_from_bula_text(t)

    # Princípio ativo: word-boundary (protege contra substring parcial)
    # \bVINCRISTINA\b casa em "SULFATO DE VINCRISTINA" (bom)
    # \bVIN\b NÃO casa em "VINCRISTINA" (proteção contra fragmentos)
    principle_re = re.compile(
        r"\b" + re.escape(item_requirement.principle) + r"\b"
    )
    principle_ok = bool(principle_re.search(t))

    # Disclaimer se algum waiver está ativo
    # ignore_principle nao entra: substancia nunca e waivable (CP16).
    waiver_used = any([
        waivers.ignore_concentration,
        waivers.ignore_form,
        waivers.ignore_pkg,
        waivers.ignore_volume,
    ])
    disclaimer = WAIVER_DISCLAIMER if waiver_used else None

    # Sem apresentações → UNMATCH (waivers não salvam sem evidência)
    snippet = _req_snippet(item_requirement.raw)
    if not pres:
        all_gaps = []
        if not principle_ok:
            all_gaps.append(Gap(
                GapCode.ACTIVE_MISSING,
                required=item_requirement.principle,
                req_snippet=snippet,
            ))
        all_gaps.append(Gap(
            GapCode.CONC_MISSING,
            required=_fmt_conc(
                item_requirement.conc_num,
                item_requirement.conc_unit,
                item_requirement.conc_den_unit,
            ),
            req_snippet=snippet,
        ))
        effective, waived = _split_by_waivers(all_gaps, waivers)
        return MatchResult(
            status="UNMATCH",
            item_id=item_id,
            best_presentation=None,
            gaps=effective if effective else all_gaps,
            other_presentations=[],
            waived_gaps=waived,
            disclaimer=disclaimer,
        )

    # PKG: busca global (uma vez)
    pkg_regex = re.compile(rf"\b{re.escape(item_requirement.pkg)}\b")
    pkg_match = pkg_regex.search(t)

    # Avaliar cada apresentação
    best_match: Optional[Presentation] = None
    best_effective: List[Gap] = []
    best_waived: List[Gap] = []

    for p in pres:
        all_gaps = _compute_all_gaps(
            item_requirement, p, t, principle_ok, pkg_match
        )
        effective, waived = _split_by_waivers(all_gaps, waivers)

        # Melhor = menos gaps efetivos
        if best_match is None or len(effective) < len(best_effective):
            best_match = p
            best_effective = effective
            best_waived = waived

        # Sem gaps efetivos → match encontrado
        if not effective:
            break

    # Determine status (CP17: other_presentations sempre populado)
    other = [x for x in pres if x is not best_match]

    if not best_effective:
        status = "MATCH_WITH_WAIVER" if best_waived else "MATCH"
    else:
        status = "UNMATCH"

    return MatchResult(
        status=status,
        item_id=item_id,
        best_presentation=best_match,
        gaps=best_effective,
        other_presentations=other,
        waived_gaps=best_waived,
        disclaimer=disclaimer,
    )


# =============================================================================
# OUTPUT CURTO (POPUP)
# =============================================================================

_POPUP_MAX = 220


def _fmt_gap_part(g: Gap, with_evidence: bool = True) -> str:
    """Format a single gap for popup display."""
    compact = GAP_COMPACT.get(g.code, g.code.value)
    if g.required and g.found:
        part = f"{compact}: req {g.required} got {g.found}"
    elif g.required:
        part = f"{compact}: req {g.required}"
    else:
        part = compact
    if with_evidence and g.evidence and len(part) < 100:
        ev_short = g.evidence[:80]
        part += f' | "{ev_short}"'
    return part


def _fmt_req_context(item_requirement: ItemRequirement, max_len: int = 80) -> str:
    """Format short TR context line for UNMATCH popup (CP19)."""
    raw = re.sub(r"\s+", " ", item_requirement.raw).strip()
    if len(raw) <= max_len:
        return f'TR: "{raw}"'
    return f'TR: "{raw[:max_len]}..."'


def format_popup(result: MatchResult, item_requirement: ItemRequirement) -> str:
    """
    Gera string curta para UI (popup). Hard cap: 220 chars.

    Usa códigos compactos (ACTIVE, CONC, FORM, PKG, VOL) + evidence snippet.
    Graceful degradation: se > 220 chars, remove evidence; se ainda > 220,
    reduz a 1 gap; por fim trunca.

    Formato MATCH:
      MATCH [+] | Item 38 | OK: RITUXIMABE; 10 MG/ML; SOLUCAO INJETAVEL; FRASCO-AMPOLA 50 ML

    Formato UNMATCH:
      UNMATCH [X] | Item 38 | CONC: req 10 MG/ML got 5 MG/ML | "...500 MG/60 ML..."
    """
    is_match = result.status in ("MATCH", "MATCH_WITH_WAIVER")
    icon = "+" if is_match else "X"
    base = f"{result.status} [{icon}] | Item {result.item_id}"

    if result.disclaimer:
        base += " [!]"

    if is_match and result.best_presentation:
        req_conc = _fmt_conc(
            item_requirement.conc_num,
            item_requirement.conc_unit,
            item_requirement.conc_den_unit,
        )
        req_pkgvol = _fmt_pkg_vol(
            item_requirement.pkg, item_requirement.vol, item_requirement.vol_unit
        )
        s = (
            f"{base} | OK: {item_requirement.principle}; {req_conc}; "
            f"{item_requirement.form}; {req_pkgvol}"
        )
        return s[:_POPUP_MAX]

    # UNMATCH — compact gaps com evidence + TR context (CP19)
    suffix = " | RISCO" if result.disclaimer else ""
    tr_ctx = _fmt_req_context(item_requirement)

    # Try 1: up to 3 gaps with evidence + TR context
    parts = [_fmt_gap_part(g, with_evidence=True) for g in result.gaps[:3]]
    gap_str = "; ".join(parts) if parts else "(sem gaps detectados)"
    s = f"{base} | {gap_str}{suffix}"
    if len(s) + len(tr_ctx) + 3 <= _POPUP_MAX:
        s = f"{s} | {tr_ctx}"
    if len(s) <= _POPUP_MAX:
        return s

    # Try 2: up to 3 gaps without evidence + TR context
    parts = [_fmt_gap_part(g, with_evidence=False) for g in result.gaps[:3]]
    gap_str = "; ".join(parts)
    s = f"{base} | {gap_str}{suffix}"
    if len(s) + len(tr_ctx) + 3 <= _POPUP_MAX:
        s = f"{s} | {tr_ctx}"
    if len(s) <= _POPUP_MAX:
        return s

    # Try 3: first gap only, without evidence
    parts = [_fmt_gap_part(result.gaps[0], with_evidence=False)] if result.gaps else []
    gap_str = parts[0] if parts else "(sem gaps)"
    s = f"{base} | {gap_str}{suffix}"
    if len(s) + len(tr_ctx) + 3 <= _POPUP_MAX:
        s = f"{s} | {tr_ctx}"
    return s[:_POPUP_MAX]
