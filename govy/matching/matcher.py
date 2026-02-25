"""
govy.matching.matcher — Motor de matching determinístico (regex-first).

Regras:
- MATCH = atende EXATAMENTE todos os componentes exigidos no item.
- Para medicamentos: qualquer diferença (inclusive "supera") = UNMATCH.
- Se o item exige volume/apresentação, isso vira baseline obrigatório.
- Bula pode ter várias apresentações: matching vale isoladamente por apresentação.
  => Se existir pelo menos 1 apresentação 100% aderente → item = MATCH.
  => As demais ficam como "outras apresentações" (informativo).
- Tolerâncias (waivers) geram DISCLAIMER de risco (inexecução contratual).

Output pensado para popups: objetivo, curto, com GAPs padronizados.
"""
from __future__ import annotations

import re
from typing import List, Optional

from .models import (
    Gap,
    GapCode,
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


# =============================================================================
# MATCHING ENGINE
# =============================================================================

WAIVER_DISCLAIMER = (
    "RISCO: tolerancias podem nao atender edital e gerar inexecucao contratual."
)


def match_item_to_bula(
    item_id: str,
    item_requirement: ItemRequirement,
    bula_text: str,
    waivers: WaiverConfig = WaiverConfig(),
) -> MatchResult:
    """
    Matching por apresentação (isolado).

    Retorna MATCH se existir pelo menos 1 apresentação 100% aderente
    ao baseline do item, respeitando waivers.

    Args:
        item_id: Identificador do item (ex: "38")
        item_requirement: Requisito parseado do item do TR
        bula_text: Texto completo da bula/ficha (raw ou já normalizado)
        waivers: Tolerâncias opcionais

    Returns:
        MatchResult com status, gaps, e melhor apresentação encontrada.
    """
    t = normalize_text(bula_text)
    pres = extract_presentations_from_bula_text(t)

    # Princípio ativo deve existir na bula (MVP: busca literal)
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

    # Sem apresentações detectadas → UNMATCH
    if not pres:
        gaps: List[Gap] = []
        if not waivers.ignore_principle and not principle_ok:
            gaps.append(Gap(
                GapCode.ACTIVE_MISSING,
                required=item_requirement.principle,
            ))
        if not waivers.ignore_concentration:
            gaps.append(Gap(
                GapCode.CONC_MISSING,
                required=_fmt_conc(
                    item_requirement.conc_num,
                    item_requirement.conc_unit,
                    item_requirement.conc_den_unit,
                ),
            ))
        return MatchResult(
            status="UNMATCH",
            item_id=item_id,
            best_presentation=None,
            gaps=gaps,
            other_presentations=[],
            disclaimer=disclaimer,
        )

    best_match: Optional[Presentation] = None
    best_gaps: List[Gap] = []
    other: List[Presentation] = []

    req_conc = _fmt_conc(
        item_requirement.conc_num,
        item_requirement.conc_unit,
        item_requirement.conc_den_unit,
    )
    req_form = item_requirement.form
    req_pkgvol = _fmt_pkg_vol(
        item_requirement.pkg, item_requirement.vol, item_requirement.vol_unit
    )

    for p in pres:
        gaps: List[Gap] = []

        # --- PRINCIPIO ATIVO ---
        if not waivers.ignore_principle and not principle_ok:
            gaps.append(Gap(
                GapCode.ACTIVE_MISSING,
                required=item_requirement.principle,
            ))

        # --- CONCENTRACAO (exata) ---
        if not waivers.ignore_concentration:
            if p.conc_num is None or p.conc_unit is None or p.conc_den_unit is None:
                gaps.append(Gap(GapCode.CONC_MISSING, required=req_conc))
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
                    ))

        # --- FORMA FARMACEUTICA (estrita) ---
        if not waivers.ignore_form:
            if not p.form:
                gaps.append(Gap(GapCode.FORM_MISSING, required=req_form))
            elif normalize_text(p.form) != normalize_text(req_form):
                gaps.append(Gap(
                    GapCode.FORM_MISMATCH,
                    required=req_form,
                    found=p.form,
                ))

        # --- EMBALAGEM (busca global no texto — MVP) ---
        if not waivers.ignore_pkg:
            pkg_found = bool(
                re.search(rf"\b{re.escape(item_requirement.pkg)}\b", t)
            )
            if not pkg_found:
                gaps.append(Gap(GapCode.PKG_MISSING, required=item_requirement.pkg))

        # --- VOLUME ---
        if not waivers.ignore_volume:
            vol_ok = False
            found_vol_str = None

            if p.vol is not None and p.vol_unit is not None:
                found_vol_str = f"{p.vol:g} {p.vol_unit}"
                vol_ok = (
                    abs(p.vol - item_requirement.vol) < 1e-9
                    and p.vol_unit == item_requirement.vol_unit
                )
            else:
                # fallback: busca PKG ... VOL UNIT no texto
                m_pkg = RE_PKG_VOL.search(t)
                if m_pkg:
                    found_vol = parse_number(m_pkg.group("vol"))
                    found_unit = normalize_text(m_pkg.group("unit"))
                    found_vol_str = f"{found_vol:g} {found_unit}"
                    vol_ok = (
                        abs(found_vol - item_requirement.vol) < 1e-9
                        and found_unit == item_requirement.vol_unit
                    )

            if not vol_ok:
                gaps.append(Gap(
                    GapCode.VOLUME_MISMATCH,
                    required=req_pkgvol,
                    found=found_vol_str,
                ))

        # Se sem gaps → MATCH (primeira apresentação que bate)
        if not gaps:
            best_match = p
            best_gaps = []
            other = [x for x in pres if x is not p]
            break

        # Guarda "melhor tentativa" (menos gaps)
        if best_match is None or len(gaps) < len(best_gaps):
            best_match = p
            best_gaps = gaps

    if best_gaps:
        return MatchResult(
            status="UNMATCH",
            item_id=item_id,
            best_presentation=best_match,
            gaps=best_gaps,
            other_presentations=[],
            disclaimer=disclaimer,
        )

    return MatchResult(
        status="MATCH",
        item_id=item_id,
        best_presentation=best_match,
        gaps=[],
        other_presentations=other,
        disclaimer=disclaimer,
    )


# =============================================================================
# OUTPUT CURTO (POPUP)
# =============================================================================

def format_popup(result: MatchResult, item_requirement: ItemRequirement) -> str:
    """
    Gera string curta e objetiva para UI (popup).

    Formato MATCH:
      MATCH | Item 38 | OK: RITUXIMABE; 10 MG/ML; SOLUCAO INJETAVEL; FRASCO-AMPOLA 50 ML

    Formato UNMATCH:
      UNMATCH | Item 38 | CONC_MISMATCH: req=10 MG/ML got=5 MG/ML; FORM_MISSING: req=...
    """
    icon = "+" if result.status == "MATCH" else "X"
    base = f"{result.status} [{icon}] | Item {result.item_id}"

    if result.disclaimer:
        base += " [!]"

    if result.status == "MATCH" and result.best_presentation:
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

    # UNMATCH — lista gaps (até 3)
    parts = []
    for g in result.gaps[:3]:
        if g.required and g.found:
            parts.append(f"{g.code}: req={g.required} got={g.found}")
        elif g.required:
            parts.append(f"{g.code}: req={g.required}")
        else:
            parts.append(f"{g.code}")
    gap_str = "; ".join(parts) if parts else "GAP: (sem detalhes)"

    s = f"{base} | {gap_str}"
    if result.disclaimer:
        s += f" | {WAIVER_DISCLAIMER}"
    return s
