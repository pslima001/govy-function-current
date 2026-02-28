# govy/copilot/contracts.py
"""
Contratos de resposta do Copiloto.
Toda resposta sai neste formato padronizado (JSON-serializável).
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal, Dict, Any

Intent = Literal[
    "pergunta_juridica",
    "checklist_conformidade",
    "pergunta_bi",
    "operacional_sistema",
    "tentativa_defesa",
    "outro",
]

Tone = Literal["simples", "tecnico", "juridico"]

EvidenceSource = Literal["kb", "bi", "workspace_doc"]

MetricType = Literal[
    "min_price",
    "max_price",
    "avg_price",
    "avg_bids",
    "price_drop_pct",
    "expected_price",
    "participants_forecast",
    "other",
]

Platform = Literal["pncp", "comprasnet", "bec", "other", "unknown"]

TimePreset = Literal["last_6m", "last_12m", "last_24m"]


DocType = Literal["edital", "tr", "etp", "minuta", "anexo", "ata", "outro"]


@dataclass
class WorkspaceDoc:
    """Documento disponível no workspace."""
    name: str
    doc_type: str           # DocType
    indexed: bool = False   # True se já tem texto indexado/pesquisável


@dataclass
class WorkspaceContext:
    """Contexto enriquecido do workspace da licitação."""
    mode: str                                       # "licitacao_workspace" | "site_geral"
    workspace_id: Optional[str] = None
    licitacao_id: Optional[str] = None
    uf: Optional[str] = None
    orgao: Optional[str] = None
    available_docs: List[WorkspaceDoc] = field(default_factory=list)
    has_indexed_text: bool = False                   # True se ao menos 1 doc tem texto indexado

    def has_doc_type(self, doc_type: str) -> bool:
        return any(d.doc_type == doc_type for d in self.available_docs)

    def doc_names(self) -> List[str]:
        return [d.name for d in self.available_docs]


@dataclass
class Evidence:
    source: EvidenceSource
    id: str                     # chunk_id, query_id, doc_id
    snippet: str                # 200-400 chars
    confidence: float           # 0..1
    title: Optional[str] = None
    doc_type: Optional[str] = None      # lei, jurisprudencia, guia_tcu
    tribunal: Optional[str] = None
    uf: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BiProductQuery:
    raw: str
    normalized: Optional[str] = None
    catalog_code: Optional[str] = None
    confidence: float = 0.0


@dataclass
class BiLocation:
    city: Optional[str] = None
    uf: Optional[str] = None
    orgao: Optional[str] = None


@dataclass
class BiTimeRange:
    date_from: Optional[str] = None     # YYYY-MM-DD
    date_to: Optional[str] = None       # YYYY-MM-DD
    preset: Optional[str] = None        # last_6m, last_12m, last_24m


@dataclass
class BiRequestDraft:
    request_id: str
    created_at_utc: str
    user_question_raw: str
    metric_type: str                                # MetricType
    product_query: BiProductQuery = field(default_factory=lambda: BiProductQuery(raw=""))
    location: BiLocation = field(default_factory=BiLocation)
    platform: str = "unknown"                       # Platform
    time_range: BiTimeRange = field(default_factory=BiTimeRange)
    workspace_id: Optional[str] = None
    licitacao_id: Optional[str] = None
    needs_user_input: List[str] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CopilotOutput:
    intent: Intent
    tone: Tone
    answer: str
    uncertainty: Optional[str] = None
    followup_questions: List[str] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    flags: Dict[str, Any] = field(default_factory=dict)
    bi_pending: bool = False
    bi_request_draft: Optional[BiRequestDraft] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        if d.get("bi_request_draft") is None:
            d.pop("bi_request_draft", None)
        if not d.get("bi_pending"):
            d.pop("bi_pending", None)
        return d

    def to_json_response(self) -> dict:
        """Formato final para o endpoint HTTP."""
        return {
            "status": "success",
            "copilot": self.to_dict(),
        }
