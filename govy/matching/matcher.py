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
    GapCode.ACTIVE_MISSING: "ignore_principle",
    GapCode.CONC_MISSING: "ignore_concentration",
    GapCode.CONC_MISMATCH: "ignore_concentration",
    GapCode.FORM_MISSING: "ignore_form",
    GapCode.FORM_MISMATCH: "ignore_form",
    GapCode.PKG_MISSING: "ignore_pkg",
    GapCode.PKG_MISMATCH: "ignore_pkg",
    GapCode.VOLUME_MISSING: "ignore_volume",
    GapCode.VOLUME_MISMATCH: "ignore_volume",
}


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
        ))

    # --- CONCENTRACAO (exata) ---
    if p.conc_num is None or p.conc_unit is None or p.conc_den_unit is None:
        gaps.append(Gap(
            GapCode.CONC_MISSING,
            required=req_conc,
            evidence=p.evidence,
        ))
    else:
        found_conc = _fmt_conc(p.conc_num, p.conc_unit, p.conc_den_unit)
        conc_equal = (
            p.conc_unit == item_requirement.conc_unit
            and p.conc_den_unit == item_requirement.conc_den_unit
            and abs(p.conc_num - item_requirement.conc_num) < 1e-9
        )
        if not conc_equal:
            gaps.append(Gap(
                GapCode.CONC_MISMATCH,
                required=req_conc,
                found=found_conc,
                evidence=p.evidence,
            ))

    # --- FORMA FARMACEUTICA (estrita) ---
    if not p.form:
        gaps.append(Gap(GapCode.FORM_MISSING, required=req_form))
    elif normalize_text(p.form) != normalize_text(req_form):
        gaps.append(Gap(
            GapCode.FORM_MISMATCH,
            required=req_form,
            found=p.form,
            evidence=p.evidence,
        ))

    # --- EMBALAGEM (busca global no texto) ---
    if not pkg_match:
        gaps.append(Gap(
            GapCode.PKG_MISSING,
            required=item_requirement.pkg,
        ))

    # --- VOLUME (prefere vol da apresentação, fallback RE_PKG_VOL global) ---
    vol_ok = False
    found_vol_str = None
    vol_evidence = None

    if p.vol is not None and p.vol_unit is not None:
        found_vol_str = f"{p.vol:g} {p.vol_unit}"
        vol_evidence = p.evidence
        vol_ok = (
            abs(p.vol - item_requirement.vol) < 1e-9
            and p.vol_unit == item_requirement.vol_unit
        )
    else:
        m_pkg = RE_PKG_VOL.search(t)
        if m_pkg:
            found_vol = parse_number(m_pkg.group("vol"))
            found_unit = normalize_text(m_pkg.group("unit"))
            found_vol_str = f"{found_vol:g} {found_unit}"
            vol_evidence = _evidence_around(t, m_pkg)
            vol_ok = (
                abs(found_vol - item_requirement.vol) < 1e-9
                and found_unit == item_requirement.vol_unit
            )

    if not vol_ok:
        gaps.append(Gap(
            GapCode.VOLUME_MISMATCH,
            required=req_pkgvol,
            found=found_vol_str,
            evidence=vol_evidence,
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

    # Princípio ativo (MVP: busca literal)
    principle_ok = item_requirement.principle in t

    # Disclaimer se algum waiver está ativo
    waiver_used = any([
        waivers.ignore_principle,
        waivers.ignore_concentration,
        waivers.ignore_form,
        waivers.ignore_pkg,
        waivers.ignore_volume,
    ])
    disclaimer = WAIVER_DISCLAIMER if waiver_used else None

    # Sem apresentações → UNMATCH (waivers não salvam sem evidência)
    if not pres:
        all_gaps = []
        if not principle_ok:
            all_gaps.append(Gap(
                GapCode.ACTIVE_MISSING,
                required=item_requirement.principle,
            ))
        all_gaps.append(Gap(
            GapCode.CONC_MISSING,
            required=_fmt_conc(
                item_requirement.conc_num,
                item_requirement.conc_unit,
                item_requirement.conc_den_unit,
            ),
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

    # Determine status
    other = [x for x in pres if x is not best_match] if not best_effective else []

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

def format_popup(result: MatchResult, item_requirement: ItemRequirement) -> str:
    """
    Gera string curta para UI (popup). Target: ≤220 chars.

    Usa códigos compactos (ACTIVE, CONC, FORM, PKG, VOL) + evidence snippet.

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
        return (
            f"{base} | OK: {item_requirement.principle}; {req_conc}; "
            f"{item_requirement.form}; {req_pkgvol}"
        )

    # UNMATCH — compact gaps com evidence
    parts = []
    for g in result.gaps[:3]:
        compact = GAP_COMPACT.get(g.code, g.code.value)
        if g.required and g.found:
            part = f"{compact}: req {g.required} got {g.found}"
        elif g.required:
            part = f"{compact}: req {g.required}"
        else:
            part = compact
        # Append evidence se cabe
        if g.evidence and len(part) < 100:
            ev_short = g.evidence[:80]
            part += f' | "{ev_short}"'
        parts.append(part)
    gap_str = "; ".join(parts) if parts else "(sem gaps detectados)"

    s = f"{base} | {gap_str}"
    if result.disclaimer:
        s += " | RISCO"
    return s
