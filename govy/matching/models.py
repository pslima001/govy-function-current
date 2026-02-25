"""
govy.matching.models — Data models e enums para matching de medicamentos.

Modelos imutáveis (frozen dataclasses) para:
- Requisitos extraídos do item do edital/TR
- Apresentações detectadas na bula
- Gaps (divergências) e resultado do matching
- Configuração de waivers (tolerâncias)
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


# =============================================================================
# ENUMS
# =============================================================================

class GapCode(str, Enum):
    """Códigos padronizados de divergência entre requisito e bula."""
    ACTIVE_MISSING = "ACTIVE_MISSING"       # Princípio ativo não encontrado
    CONC_MISSING = "CONC_MISSING"           # Concentração não detectada
    CONC_MISMATCH = "CONC_MISMATCH"         # Concentração diferente
    FORM_MISSING = "FORM_MISSING"           # Forma farmacêutica não detectada
    FORM_MISMATCH = "FORM_MISMATCH"         # Forma farmacêutica diferente
    PKG_MISSING = "PKG_MISSING"             # Embalagem não detectada
    PKG_MISMATCH = "PKG_MISMATCH"           # Embalagem diferente
    VOLUME_MISSING = "VOLUME_MISSING"       # Volume não detectado
    VOLUME_MISMATCH = "VOLUME_MISMATCH"     # Volume diferente


# =============================================================================
# DATA MODELS
# =============================================================================

@dataclass(frozen=True)
class ItemRequirement:
    """Requisito extraído da descrição MAIS completa do item do edital/TR."""
    raw: str                        # texto original
    principle: str                  # princípio ativo normalizado
    conc_num: float                 # concentração numérica (ex: 10.0)
    conc_unit: str                  # unidade concentração (MG/MCG/G/UI)
    conc_den_unit: str              # unidade denominador (ML/L)
    form: str                       # forma farmacêutica normalizada
    pkg: str                        # embalagem (FRASCO-AMPOLA/AMPOLA/FRASCO/SERINGA)
    vol: float                      # volume (ex: 50.0)
    vol_unit: str                   # unidade volume (ML/L)


@dataclass(frozen=True)
class Presentation:
    """Uma apresentação detectada na bula/ficha técnica."""
    dose: Optional[float]           # dose total (ex: 500.0 se 500 mg/50 ml)
    dose_unit: Optional[str]        # unidade dose (MG/MCG/G/UI)
    vol: Optional[float]            # volume (ex: 50.0)
    vol_unit: Optional[str]         # unidade volume (ML/L)
    conc_num: Optional[float]       # concentração derivada ou explícita
    conc_unit: Optional[str]        # unidade concentração
    conc_den_unit: Optional[str]    # unidade denominador
    form: Optional[str]             # forma farmacêutica normalizada
    evidence: str                   # trecho curto da bula onde foi capturada


@dataclass(frozen=True)
class Gap:
    """Uma divergência específica entre requisito do item e apresentação da bula."""
    code: GapCode
    required: Optional[str] = None  # valor exigido no edital
    found: Optional[str] = None     # valor encontrado na bula (None se ausente)


@dataclass(frozen=True)
class MatchResult:
    """Resultado do matching de um item contra uma bula."""
    status: str                             # "MATCH" | "UNMATCH"
    item_id: str
    best_presentation: Optional[Presentation]
    gaps: List[Gap]
    other_presentations: List[Presentation]
    disclaimer: Optional[str] = None        # presente se waiver foi aplicado


@dataclass(frozen=True)
class WaiverConfig:
    """
    Tolerâncias que o usuário pode aplicar a componentes do matching.
    Se True, aquele componente é ignorado na decisão (gera disclaimer de risco).
    """
    ignore_principle: bool = False
    ignore_concentration: bool = False
    ignore_form: bool = False
    ignore_pkg: bool = False
    ignore_volume: bool = False
