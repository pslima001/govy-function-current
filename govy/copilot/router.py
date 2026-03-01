# govy/copilot/router.py
"""
Router — classifica intenção do usuário e escolhe tom da resposta.

Contextos:
  - licitacao_workspace (dentro da página de uma licitação)
  - site_geral (fora do workspace)

Intenções:
  - pergunta_juridica
  - checklist_conformidade
  - pergunta_bi
  - operacional_sistema
  - tentativa_defesa (BLOQUEADA antes de qualquer processamento)
  - outro
"""
import re
from typing import Literal

from govy.copilot.contracts import Intent, Tone, WorkspaceContext, WorkspaceDoc

Context = Literal["licitacao_workspace", "site_geral"]

# ─── Detecção de defesa (alta prioridade — checado primeiro) ─────────

_DEFENSE_PATTERNS = [
    # Termos diretos
    r"\brecurso\s+(administrativo|hierárquico|hierarquico)\b",
    r"\brecurso\b(?!.*\b(humano|financeiro|orçament|material|disponível|disponivel|computacional)\b)",
    r"\bimpugna",
    r"\bcontrarrazo",
    r"\bdefesa\s+(administrativa|prévia|previa|recursal)\b",
    r"\braz[oõ]es\s+(recursa|de\s+defesa)",
    r"\bminuta\b.*\b(recurso|impugna|defesa)\b",
    r"\bpeti[cç][aã]o\b",
    r"\bpe[cç]a\b.*\b(administrativa|recursal|defesa)\b",
    r"\bmanifesta[cç][aã]o\b.*\b(pr[eé]via|defesa|recursal)\b",
    # Verbos de produção + peça
    r"\bfa[cç]a\s+(um|uma|o|a)\s+(recurso|impugna|defesa|peti[cç])",
    r"\belabore?\b.*\b(recurso|impugna|defesa|peti[cç])",
    r"\bredigir?\b.*\b(recurso|impugna|defesa|peti[cç])",
    r"\b(crie?|gere?|monte|escreva|produza)\b.*\b(recurso|impugna|defesa|peti[cç]|contrarrazo)",
    r"\b(preparar?|montar?)\b.*\b(recurso|impugna|defesa|peti[cç]|contrarrazo)",
    # Frases ambíguas que indicam defesa
    r"\bcomo\s+(recorrer|impugnar|contestar)\b",
    r"\bquero\s+(recorrer|impugnar|contestar)\b",
    r"\bpreciso\s+(recorrer|impugnar|contestar)\b",
    r"\b(posso|consigo|devo)\s+(recorrer|impugnar|contestar)\b",
    r"\bme\s+ajud[ae]\b.*\b(recorrer|impugnar|contestar|defesa)\b",
    # Pedidos de modelo/template
    r"\b(modelo|template|minuta)\s+(de\s+)?(recurso|impugna|defesa|peti[cç]|contrarrazo)\b",
]

_DEFENSE_RE = [re.compile(p, re.IGNORECASE) for p in _DEFENSE_PATTERNS]

# ─── Keywords por intenção ───────────────────────────────────────────

_BI_KEYWORDS = [
    # Termos genéricos de BI
    "dashboard", "bi", "indicador", "métrica", "metricas", "kpi",
    "gráfico", "grafico", "estatística", "ranking", "volume",
    "quantas licitações", "quantos editais", "média de valor",
    "total de", "percentual", "evolução",
    # Preço / valor
    "menor preço", "maior preço", "preço mínimo", "preço máximo",
    "preço previsto", "preço estimado", "valor estimado",
    "ticket médio", "ticket medio",
    # Propostas / participantes
    "média de propostas", "quantas propostas", "quantas empresas",
    "previsão de participantes", "previsao de participantes",
    # Disputa
    "redução na disputa", "reducao na disputa", "% de redução",
    "queda de preço", "redução de preço",
    # Histórico
    "histórico de preço", "historico de preco", "histórico de participação",
    "historico de participacao",
    # Dispersão / outliers
    "dispersão", "dispersao", "outlier", "desvio padrão",
    # Plataformas
    "por plataforma", "pncp", "comprasnet", "bec",
    # Localidade + volume
    "qual cidade", "qual uf", "mais participantes",
]

# ─── Metric type mapping ────────────────────────────────────────────

_METRIC_PATTERNS: list[tuple[str, list[str]]] = [
    ("min_price", [
        "menor preço", "preço mínimo", "preco minimo", "menor valor",
        "valor mínimo", "valor minimo",
    ]),
    ("max_price", [
        "maior preço", "preço máximo", "preco maximo", "maior valor",
        "valor máximo", "valor maximo",
    ]),
    ("avg_bids", [
        "média de propostas", "media de propostas", "quantas propostas em média",
        "quantas propostas",
    ]),
    ("price_drop_pct", [
        "redução na disputa", "reducao na disputa", "% de redução",
        "% redução", "queda de preço", "redução de preço",
        "reducao de preco",
    ]),
    ("avg_price", [
        "ticket médio", "ticket medio", "preço médio", "preco medio",
        "média de preço", "media de preco",
    ]),
    ("expected_price", [
        "preço previsto", "preco previsto", "preço estimado", "preco estimado",
        "valor estimado", "valor previsto",
    ]),
    ("participants_forecast", [
        "quantas empresas", "previsão de participantes", "previsao de participantes",
        "quantos fornecedores", "quantos licitantes",
    ]),
]

# ─── Platform mapping ───────────────────────────────────────────────

_PLATFORM_PATTERNS: list[tuple[str, list[str]]] = [
    ("pncp", ["pncp"]),
    ("comprasnet", ["comprasnet"]),
    ("bec", ["bec", "bolsa eletrônica", "bolsa eletronica"]),
]

# ─── Time range preset mapping ──────────────────────────────────────

_TIME_PRESETS: list[tuple[str, list[str]]] = [
    ("last_6m", ["últimos 6 meses", "ultimos 6 meses", "6 meses"]),
    ("last_12m", ["últimos 12 meses", "ultimos 12 meses", "12 meses", "último ano", "ultimo ano"]),
    ("last_24m", ["últimos 24 meses", "ultimos 24 meses", "24 meses", "últimos 2 anos", "ultimos 2 anos"]),
]


def detect_bi_metric_type(user_text: str) -> str:
    """Mapeia texto do usuário para metric_type. Retorna 'other' se incerto."""
    t = user_text.lower()
    for metric, patterns in _METRIC_PATTERNS:
        if any(p in t for p in patterns):
            return metric
    return "other"


def detect_bi_platform(user_text: str) -> str:
    """Detecta plataforma mencionada. Retorna 'unknown' se não detectar."""
    t = user_text.lower()
    for platform, patterns in _PLATFORM_PATTERNS:
        if any(p in t for p in patterns):
            return platform
    return "unknown"


def detect_bi_time_preset(user_text: str) -> str:
    """Detecta preset de período. Retorna None se não detectar."""
    t = user_text.lower()
    for preset, patterns in _TIME_PRESETS:
        if any(p in t for p in patterns):
            return preset
    return None

_CHECKLIST_KEYWORDS = [
    "checklist", "conformidade", "edital está ok", "faltando cláusula",
    "verificar edital", "analisar edital", "está conforme",
    "itens obrigatórios", "itens obrigatorios", "validar edital",
]

_OPERACIONAL_KEYWORDS = [
    "como uso", "como funciona", "onde fica", "configurar", "botão",
    "login", "senha", "cadastro", "plataforma", "sistema govy",
    "ajuda", "tutorial",
]

# ─── Tone: keywords que elevam a profundidade ────────────────────────

_TECNICO_KEYWORDS = [
    "art.", "inciso", "jurisprudência", "jurisprudencia", "acórdão",
    "acordao", "tcu", "tce", "lei 14.133", "lei 8.666", "decreto",
    "súmula", "sumula", "in ", "instrução normativa",
]

_JURIDICO_KEYWORDS = [
    "ratio decidendi", "distinção", "distincao", "precedente",
    "nulidade", "vício", "vicio", "ato administrativo",
    "discricionariedade", "vinculação", "motivação", "publicidade",
    "legalidade", "isonomia", "contraditório", "ampla defesa",
    "proporcionalidade", "razoabilidade",
]


def detect_context(context_data: dict) -> Context:
    """Detecta se estamos no workspace de uma licitação ou no site geral."""
    if context_data.get("workspace_id") or context_data.get("licitacao_id"):
        return "licitacao_workspace"
    return "site_geral"


def build_workspace_context(context_data: dict) -> WorkspaceContext:
    """
    Constrói WorkspaceContext enriquecido a partir do dict de contexto do request.

    O frontend envia:
      context: {
        workspace_id: "...",
        licitacao_id: "...",
        uf: "SP",
        orgao: "...",
        available_docs: [
          {"name": "edital.pdf", "doc_type": "edital", "indexed": true},
          {"name": "TR_v2.pdf", "doc_type": "tr", "indexed": true},
        ]
      }
    """
    mode = detect_context(context_data)

    # Parsear available_docs do request
    raw_docs = context_data.get("available_docs") or []
    docs = []
    for d in raw_docs:
        if isinstance(d, dict) and d.get("name"):
            docs.append(WorkspaceDoc(
                name=d["name"],
                doc_type=d.get("doc_type", "outro"),
                indexed=bool(d.get("indexed", False)),
            ))

    has_indexed = any(d.indexed for d in docs)

    return WorkspaceContext(
        mode=mode,
        workspace_id=context_data.get("workspace_id"),
        licitacao_id=context_data.get("licitacao_id"),
        uf=context_data.get("uf"),
        orgao=context_data.get("orgao"),
        available_docs=docs,
        has_indexed_text=has_indexed,
    )


def detect_intent(user_text: str) -> Intent:
    """
    Classifica a intenção do usuário.
    Ordem de prioridade: defesa > BI > checklist > operacional > jurídica
    """
    t = user_text.lower()

    # 1. Defesa — sempre primeiro (bloqueante)
    if any(r.search(t) for r in _DEFENSE_RE):
        return "tentativa_defesa"

    # 2. BI
    if any(k in t for k in _BI_KEYWORDS):
        return "pergunta_bi"

    # 3. Checklist
    if any(k in t for k in _CHECKLIST_KEYWORDS):
        return "checklist_conformidade"

    # 4. Operacional
    if any(k in t for k in _OPERACIONAL_KEYWORDS):
        return "operacional_sistema"

    # 5. Default: pergunta jurídica
    return "pergunta_juridica"


def choose_tone(user_text: str) -> Tone:
    """
    Tom adaptativo:
    - simples (default): linguagem acessível
    - tecnico: quando usa termos de legislação/tribunais
    - juridico: quando demonstra profundidade doutrinária/processual
    """
    t = user_text.lower()

    if any(k in t for k in _JURIDICO_KEYWORDS):
        return "juridico"

    if any(k in t for k in _TECNICO_KEYWORDS):
        return "tecnico"

    return "simples"
