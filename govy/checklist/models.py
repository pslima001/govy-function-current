"""
GOVY Checklist — Data models
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Sinalização possível para cada check
SINALIZACAO_OK = "OK"
SINALIZACAO_ATENCAO = "Atenção"
SINALIZACAO_NAO_CONFORME = "Não conforme"
SINALIZACAO_NAO_IDENTIFICADO = "Não encontrado no texto"

SINALIZACOES_VALIDAS = frozenset({
    SINALIZACAO_OK,
    SINALIZACAO_ATENCAO,
    SINALIZACAO_NAO_CONFORME,
    SINALIZACAO_NAO_IDENTIFICADO,
})


@dataclass
class GuiaTcuRef:
    """Referência a uma seção do Guia TCU."""
    section_id: str
    section_title: str
    source_url: str
    score: float = 0.0


@dataclass
class CheckItem:
    """Um item do checklist de auditoria."""
    check_id: str
    stage_tag: str
    pergunta_de_auditoria: str
    sinalizacao: str
    trecho_do_edital: str
    referencia_guia_tcu: GuiaTcuRef
    observacao: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "stage_tag": self.stage_tag,
            "pergunta_de_auditoria": self.pergunta_de_auditoria,
            "sinalizacao": self.sinalizacao,
            "trecho_do_edital": self.trecho_do_edital,
            "referencia_guia_tcu": {
                "section_id": self.referencia_guia_tcu.section_id,
                "section_title": self.referencia_guia_tcu.section_title,
                "source_url": self.referencia_guia_tcu.source_url,
                "score": self.referencia_guia_tcu.score,
            },
            "observacao": self.observacao,
        }


@dataclass
class ChecklistResult:
    """Resultado completo do checklist."""
    run_id: str
    arquivo_analisado: str
    total_checks: int
    checks: List[CheckItem] = field(default_factory=list)
    stage_tag_distribution: Dict[str, int] = field(default_factory=dict)
    sinalizacao_distribution: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "checklist_edital_v1",
            "run_id": self.run_id,
            "arquivo_analisado": self.arquivo_analisado,
            "total_checks": self.total_checks,
            "stage_tag_distribution": self.stage_tag_distribution,
            "sinalizacao_distribution": self.sinalizacao_distribution,
            "checks": [c.to_dict() for c in self.checks],
        }
