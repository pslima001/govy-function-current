"""
GOVY - Guia TCU Stage Tag Enum (frozen)
========================================
Canonical enum of stage_tag values used in the guia_tcu KB.

These 6 values map the TCU Manual chapters to phases of the public
procurement process. 'governanca' is a cross-cutting layer (Cap 2)
that doesn't belong to a specific procurement phase but governs all.

Frozen: 2026-02-27.  Any change requires reindex.
"""

from typing import FrozenSet

# ─── Canonical Enum ──────────────────────────────────────────────────────────
# WARNING: Do NOT add/remove/rename values without reindexing.

STAGE_TAGS: FrozenSet[str] = frozenset({
    "planejamento",   # Cap 1 (intro), 3 (metaprocesso), 4 (planejamento da contratação)
    "edital",         # Cap 5.1-5.2 (divulgação do edital, apresentação de propostas)
    "seleção",        # Cap 5.3-5.11 (lances, julgamento, habilitação, recursos, contratação direta)
    "contrato",       # Cap 5.11 (formalização, cláusulas, garantias, duração)
    "gestão",         # Cap 6 (execução, alteração, prorrogação, extinção)
    "governança",     # Cap 2 (integridade, riscos, gestão estratégica, transparência, auditoria)
})

# Mapping to procedural_stage values stored in kb-legal index
STAGE_TAG_TO_PROCEDURAL_STAGE = {
    "planejamento": "PLANEJAMENTO",
    "edital":       "EDITAL",
    "seleção":      "SELECAO",
    "contrato":     "CONTRATO",
    "gestão":       "GESTAO",
    "governança":   "GOVERNANCA",
}

# Reverse mapping (index value -> stage_tag)
PROCEDURAL_STAGE_TO_STAGE_TAG = {v: k for k, v in STAGE_TAG_TO_PROCEDURAL_STAGE.items()}

# All valid procedural_stage values in the index for guia_tcu
PROCEDURAL_STAGES: FrozenSet[str] = frozenset(STAGE_TAG_TO_PROCEDURAL_STAGE.values())


def validate_stage_tag(tag: str) -> bool:
    """Check if a stage_tag is in the canonical enum."""
    return tag in STAGE_TAGS


def validate_procedural_stage(stage: str) -> bool:
    """Check if a procedural_stage value is valid for guia_tcu."""
    return stage in PROCEDURAL_STAGES
