"""
mapping_tce_to_kblegal.py
Transforma output do tce_parser_v3 → schema kb-legal (19 campos)
para indexação no Azure AI Search.

Usado pelo Queue Trigger parse-tce-pdf antes de gravar em kb-raw.
"""

import hashlib
import re
from typing import Dict, List, Optional, Any

MISSING = "__MISSING__"

# ============================================================
# MAPEAMENTO DE CAMPOS
# ============================================================
#
# tce_parser_v3 (25 campos)    →   kb-legal (19 campos)
# ─────────────────────────────────────────────────────────────
# tribunal_type                →   tribunal (TCU, TCE)
# tribunal_name                →   (usado em citation/source)
# uf                           →   uf
# region                       →   region (CENTRO-OESTE → CENTRO_OESTE)
# processo                     →   (usado em citation/source/title)
# acordao_numero               →   (usado em citation/title)
# relator                      →   (usado em citation)
# orgao_julgador               →   (usado em citation)
# ementa                       →   content (principal)
# dispositivo                  →   content (concatenado)
# holding_outcome              →   holding_outcome
# effect                       →   effect
# publication_number           →   (metadata, não indexado)
# publication_date             →   (usado para year)
# julgamento_date              →   (usado para year)
# references                   →   (metadata, não indexado)
# linked_processes             →   (metadata, não indexado)
# procedural_stage             →   procedural_stage
# claim_pattern                →   claim_pattern (lista → primeiro item)
# authority_score              →   authority_score (str → float)
# year                         →   year (str → int)
# is_current                   →   is_current (str → bool)
# key_citation                 →   (usado em content/citation)
# key_citation_speaker         →   (metadata)
# key_citation_source          →   (metadata)
#
# CAMPOS kb-legal SEM MAPEAMENTO DIRETO:
# chunk_id      → gerado (sha1 do blob_path)
# doc_type      → sempre "jurisprudencia"
# secao         → inferido do conteúdo (tese/vital/contexto_minimo)
# remedy_type   → inferido da ementa (REPRESENTACAO/DENUNCIA/etc)
# source        → construído (tribunal_name + processo)
# title         → construído (tipo + processo + acordao)
# citation      → construído (processo + acordao + tribunal + relator)
# embedding     → gerado na hora da indexação (OpenAI)
# ============================================================


# --- Normalização de region ---
REGION_NORMALIZE = {
    "CENTRO-OESTE": "CENTRO_OESTE",
    "CENTRO_OESTE": "CENTRO_OESTE",
    "SUDESTE": "SUDESTE",
    "SUL": "SUL",
    "NORDESTE": "NORDESTE",
    "NORTE": "NORTE",
}


# --- Inferência de remedy_type ---
REMEDY_PATTERNS = {
    "REPRESENTACAO": r"\bREPRESENTA[ÇC][ÃA]O\b",
    "DENUNCIA": r"\bDEN[ÚU]NCIA\b",
    "CONSULTA": r"\bCONSULTA\b",
    "RECURSO": r"\bRECURSO\b|\bEMBARGOS?\b|\bAGRAVO\b|\bPEDIDO\s+DE\s+REEXAME\b",
    "ORIENTACAO_GERAL": r"\bORIENTA[ÇC][ÃA]O\b|\bINSTRU[ÇC][ÃA]O\s+NORMATIVA\b",
}


def _infer_remedy_type(ementa: str, dispositivo: str) -> Optional[str]:
    """Infere remedy_type a partir da ementa ou dispositivo."""
    for text in (ementa, dispositivo):
        if not text or text == MISSING:
            continue
        upper = text.upper()
        for remedy, pattern in REMEDY_PATTERNS.items():
            if re.search(pattern, upper, flags=re.IGNORECASE):
                return remedy
    return None  # omitir se não detectado


# --- Inferência de secao ---
def _infer_secao(parser: Dict[str, Any]) -> str:
    """
    Infere a seção do chunk para o kb-legal.
    - tese: ementa com dispositivo (conteúdo completo)
    - vital: só key_citation forte
    - contexto_minimo: dados incompletos
    """
    has_ementa = parser.get("ementa", MISSING) != MISSING
    has_dispositivo = parser.get("dispositivo", MISSING) != MISSING
    has_key_citation = parser.get("key_citation", MISSING) != MISSING

    if has_ementa and has_dispositivo:
        return "tese"
    if has_ementa or has_key_citation:
        return "vital"
    return "contexto_minimo"


# --- Construção de content ---
def _build_content(parser: Dict[str, Any]) -> str:
    """
    Monta o campo content (texto citável/searchable).
    Ordem: ementa + dispositivo + key_citation (sem duplicar).
    """
    parts = []

    ementa = parser.get("ementa", MISSING)
    if ementa and ementa != MISSING:
        parts.append(f"EMENTA: {ementa}")

    relatorio = parser.get("relatorio", MISSING)
    if relatorio and relatorio != MISSING:
        parts.append(f"RELATÓRIO: {relatorio}")

    fundamentacao = parser.get("fundamentacao", MISSING)
    if fundamentacao and fundamentacao != MISSING:
        parts.append(f"FUNDAMENTAÇÃO: {fundamentacao}")

    conclusao = parser.get("conclusao", MISSING)
    if conclusao and conclusao != MISSING:
        parts.append(f"CONCLUSÃO: {conclusao}")

    dispositivo = parser.get("dispositivo", MISSING)
    if dispositivo and dispositivo != MISSING:
        parts.append(f"DISPOSITIVO: {dispositivo}")

    # key_citation só se não estiver contida no dispositivo
    key_cit = parser.get("key_citation", MISSING)
    if key_cit and key_cit != MISSING:
        if dispositivo == MISSING or key_cit not in dispositivo:
            parts.append(f"CITAÇÃO PRINCIPAL: {key_cit}")

    return "\n\n".join(parts) if parts else ""


# --- Construção de citation ---
def _build_citation(parser: Dict[str, Any]) -> str:
    """
    Monta o campo citation (como citar este documento).
    Formato: "TRIBUNAL. Acórdão nº X. Processo Y. Relator: Z."
    """
    fragments = []

    tribunal = parser.get("tribunal_name", MISSING)
    if tribunal and tribunal != MISSING:
        fragments.append(tribunal)

    acordao = parser.get("acordao_numero", MISSING)
    if acordao and acordao != MISSING:
        fragments.append(f"Acórdão nº {acordao}")

    processo = parser.get("processo", MISSING)
    if processo and processo != MISSING:
        fragments.append(f"Processo {processo}")

    relator = parser.get("relator", MISSING)
    if relator and relator != MISSING:
        fragments.append(f"Relator: {relator}")

    orgao = parser.get("orgao_julgador", MISSING)
    if orgao and orgao != MISSING:
        fragments.append(f"Órgão: {orgao}")

    return ". ".join(fragments) + "." if fragments else ""


# --- Construção de title ---
def _build_title(parser: Dict[str, Any], display_name: Optional[str] = None) -> str:
    """
    Monta um título descritivo.
    Formato: "Acórdão X - Processo Y - TRIBUNAL"
    """
    parts = []

    acordao = parser.get("acordao_numero", MISSING)
    if acordao and acordao != MISSING:
        parts.append(f"Acórdão {acordao}")

    processo = parser.get("processo", MISSING)
    if processo and processo != MISSING:
        parts.append(f"Proc. {processo}")

    if display_name:
        parts.append(display_name)
    else:
        tribunal = parser.get("tribunal_name", MISSING)
        if tribunal and tribunal != MISSING:
            t_type = parser.get("tribunal_type", "")
            uf = parser.get("uf", MISSING)
            if t_type == "TCU":
                parts.append("TCU")
            elif t_type == "TCE" and uf != MISSING:
                parts.append(f"TCE-{uf}")
            else:
                parts.append(tribunal[:30])

    return " - ".join(parts) if parts else "Jurisprudência sem título"


# --- Construção de source ---
def _build_source(parser: Dict[str, Any], blob_path: str = "", display_name: Optional[str] = None) -> str:
    """
    Fonte original do documento.
    Formato: "TCE-SP / tce-sp/acordaos/10026_989_24_acordao.pdf"
    """
    parts = []

    if display_name:
        parts.append(display_name)
    else:
        t_type = parser.get("tribunal_type", "")
        uf = parser.get("uf", MISSING)
        if t_type == "TCU":
            parts.append("TCU")
        elif t_type and uf and uf != MISSING:
            parts.append(f"{t_type}-{uf}")
        elif t_type:
            parts.append(t_type)

    if blob_path:
        parts.append(blob_path)

    return " / ".join(parts) if parts else ""


# --- Geração de chunk_id ---
def generate_chunk_id(blob_path: str, blob_etag: str = "") -> str:
    """
    Gera chunk_id determinístico e seguro para Azure Search.
    Regra: [a-zA-Z0-9_-=] somente.
    """
    raw = f"{blob_path}:{blob_etag}" if blob_etag else blob_path
    sha = hashlib.sha1(raw.encode()).hexdigest()
    # Prefixo para identificar origem
    return f"tce-{sha}"


# ============================================================
# FUNÇÃO PRINCIPAL DE TRANSFORMAÇÃO
# ============================================================

def transform_parser_to_kblegal(
    parser_output: Dict[str, Any],
    blob_path: str,
    blob_etag: str = "",
    config=None,
) -> Dict[str, Any]:
    """
    Transforma output do tce_parser_v3 para schema kb-legal.

    Args:
        parser_output: dict retornado por parse_text() ou parse_pdf_bytes()
        blob_path: caminho do blob no container sttcejurisprudencia
        blob_etag: etag do blob (para idempotência)
        config: TribunalConfig opcional — quando presente, usa registry
                como source of truth para tribunal/uf/authority_score/region

    Returns:
        dict pronto para indexar no kb-legal (19 campos, sem embedding)
        embedding é adicionado pelo indexador.
    """
    p = parser_output  # alias

    # --- Campos diretos com conversão ---
    doc: Dict[str, Any] = {
        "chunk_id": generate_chunk_id(blob_path, blob_etag),
        "doc_type": "jurisprudencia",
    }

    # Se config fornecido, registry é source of truth para identidade
    if config:
        # tribunal_type derivado do tribunal_id (tce-sc → TCE, tcu → TCU)
        doc["tribunal"] = config.tribunal_id.split("-")[0].upper()
        if config.uf:
            doc["uf"] = config.uf
        doc["authority_score"] = config.authority_score
        from govy.api.tce_parser_v3 import REGION_MAP
        if config.uf and config.uf in REGION_MAP:
            doc["region"] = REGION_NORMALIZE.get(REGION_MAP[config.uf], REGION_MAP[config.uf])
    else:
        # Fallback: inferir do parser (comportamento original)
        tribunal = p.get("tribunal_type", MISSING)
        if tribunal and tribunal != MISSING:
            doc["tribunal"] = tribunal

        uf = p.get("uf", MISSING)
        if uf and uf != MISSING:
            doc["uf"] = uf

    # content (searchable)
    content = _build_content(p)
    if content:
        doc["content"] = content
    else:
        # Sem conteúdo útil → não indexar
        return {}

    # citation
    citation = _build_citation(p)
    if citation:
        doc["citation"] = citation

    # authority_score (str "0.75" → float) — skip if config already set it
    if "authority_score" not in doc:
        auth = p.get("authority_score", MISSING)
        if auth and auth != MISSING:
            try:
                doc["authority_score"] = float(auth)
            except (ValueError, TypeError):
                pass

    # year (str "2024" → int)
    year = p.get("year", MISSING)
    if year and year != MISSING:
        try:
            doc["year"] = int(year)
        except (ValueError, TypeError):
            pass

    # secao
    doc["secao"] = _infer_secao(p)

    # procedural_stage (direto, já em enum correto)
    stage = p.get("procedural_stage", MISSING)
    if stage and stage != MISSING:
        doc["procedural_stage"] = stage

    # holding_outcome
    outcome = p.get("holding_outcome", MISSING)
    if outcome and outcome != MISSING:
        doc["holding_outcome"] = outcome

    # remedy_type (inferido)
    remedy = _infer_remedy_type(
        p.get("ementa", MISSING),
        p.get("dispositivo", MISSING),
    )
    if remedy:
        doc["remedy_type"] = remedy

    # claim_pattern (lista → primeiro item, ou concatenado)
    patterns = p.get("claim_pattern", [])
    if patterns and isinstance(patterns, list) and len(patterns) > 0:
        doc["claim_pattern"] = patterns[0]  # Azure Search: Edm.String

    # effect
    effect = p.get("effect", MISSING)
    if effect and effect != MISSING:
        doc["effect"] = effect

    # region (normaliza CENTRO-OESTE → CENTRO_OESTE) — skip if config already set it
    if "region" not in doc:
        region = p.get("region", MISSING)
        if region and region != MISSING:
            doc["region"] = REGION_NORMALIZE.get(region, region)

    # source / title — use display_name from config when available
    dn = config.display_name if config else None
    source = _build_source(p, blob_path, display_name=dn)
    if source:
        doc["source"] = source

    # title
    doc["title"] = _build_title(p, display_name=dn)

    # is_current (str "True"/"False" → bool)
    current = p.get("is_current", MISSING)
    if current and current != MISSING:
        if isinstance(current, str):
            doc["is_current"] = current.lower() == "true"
        elif isinstance(current, bool):
            doc["is_current"] = current

    return doc


# ============================================================
# VALIDAÇÃO DO DOCUMENTO
# ============================================================

KB_LEGAL_REQUIRED = {"chunk_id", "doc_type", "content"}
KB_LEGAL_ALL_FIELDS = {
    "chunk_id", "doc_type", "tribunal", "uf", "content", "citation",
    "authority_score", "year", "secao", "procedural_stage",
    "holding_outcome", "remedy_type", "claim_pattern", "effect",
    "region", "source", "title", "is_current",
    # embedding é adicionado pelo indexador
}


def validate_kblegal_doc(doc: Dict[str, Any]) -> List[str]:
    """
    Valida documento transformado contra schema kb-legal.
    Retorna lista de erros (vazia = OK).
    """
    errors = []

    if not doc:
        return ["Documento vazio (parser sem conteúdo útil)"]

    # Campos obrigatórios
    for field in KB_LEGAL_REQUIRED:
        if field not in doc:
            errors.append(f"Campo obrigatório ausente: {field}")

    # Campos desconhecidos
    unknown = set(doc.keys()) - KB_LEGAL_ALL_FIELDS
    if unknown:
        errors.append(f"Campos desconhecidos: {unknown}")

    # Tipos
    if "authority_score" in doc and not isinstance(doc["authority_score"], float):
        errors.append(f"authority_score deve ser float, got {type(doc['authority_score'])}")

    if "year" in doc and not isinstance(doc["year"], int):
        errors.append(f"year deve ser int, got {type(doc['year'])}")

    if "is_current" in doc and not isinstance(doc["is_current"], bool):
        errors.append(f"is_current deve ser bool, got {type(doc['is_current'])}")

    # Enums válidos
    valid_stages = {"EDITAL", "HABILITACAO", "JULGAMENTO", "CONTRATACAO", "EXECUCAO"}
    if "procedural_stage" in doc and doc["procedural_stage"] not in valid_stages:
        errors.append(f"procedural_stage inválido: {doc['procedural_stage']}")

    valid_outcomes = {"DETERMINOU_AJUSTE", "AFASTOU", "ORIENTOU", "SANCIONOU", "ARQUIVOU", "ABSOLVEU"}
    if "holding_outcome" in doc and doc["holding_outcome"] not in valid_outcomes:
        errors.append(f"holding_outcome inválido: {doc['holding_outcome']}")

    valid_effects = {"FLEXIBILIZA", "RIGORIZA", "CONDICIONAL"}
    if "effect" in doc and doc["effect"] not in valid_effects:
        errors.append(f"effect inválido: {doc['effect']}")

    valid_regions = {"SUDESTE", "SUL", "NORDESTE", "CENTRO_OESTE", "NORTE"}
    if "region" in doc and doc["region"] not in valid_regions:
        errors.append(f"region inválido: {doc['region']}")

    valid_secao = {"tese", "vital", "fundamento_legal", "limites", "contexto_minimo"}
    if "secao" in doc and doc["secao"] not in valid_secao:
        errors.append(f"secao inválido: {doc['secao']}")

    valid_remedy = {"REPRESENTACAO", "DENUNCIA", "CONSULTA", "RECURSO", "ORIENTACAO_GERAL"}
    if "remedy_type" in doc and doc["remedy_type"] not in valid_remedy:
        errors.append(f"remedy_type inválido: {doc['remedy_type']}")

    return errors


# ============================================================
# TESTE RÁPIDO
# ============================================================

if __name__ == "__main__":
    # Simula output do tce_parser_v3
    sample_parser_output = {
        "tribunal_type": "TCE",
        "tribunal_name": "TRIBUNAL DE CONTAS DO ESTADO DE SAO PAULO",
        "uf": "SP",
        "region": "SUDESTE",
        "processo": "TC-010026.989.24-4",
        "acordao_numero": "720/2024",
        "relator": "DIMAS RAMALHO",
        "orgao_julgador": "Primeira Câmara",
        "ementa": "LICITAÇÃO. PREGÃO ELETRÔNICO. EXIGÊNCIA DE ATESTADO DE CAPACIDADE TÉCNICA EM QUANTIDADE DESPROPORCIONAL AO OBJETO. RESTRIÇÃO À COMPETITIVIDADE. IRREGULARIDADE.",
        "dispositivo": "ACORDAM os membros da Primeira Câmara do Tribunal de Contas do Estado de São Paulo, nos termos do voto do Relator, por unanimidade, em julgar IRREGULAR o edital, determinar a anulação do certame e aplicar multa de 500 UFESPs.",
        "holding_outcome": "SANCIONOU",
        "effect": "RIGORIZA",
        "publication_number": "12345",
        "publication_date": "15/03/2024",
        "julgamento_date": "10/03/2024",
        "references": ["TC/1234/2022"],
        "linked_processes": ["TC/1234/2022"],
        "procedural_stage": "EDITAL",
        "claim_pattern": ["RESTRICAO_COMPETITIVIDADE"],
        "authority_score": "0.73",
        "year": "2024",
        "is_current": "True",
        "key_citation": "ACORDAM os membros... julgar IRREGULAR... aplicar multa",
        "key_citation_speaker": "TRIBUNAL",
        "key_citation_source": "DISPOSITIVO",
    }

    blob = "tce-sp/acordaos/10026_989_24_acordao.pdf"
    doc = transform_parser_to_kblegal(sample_parser_output, blob, "0x8DCABC123")

    print("=" * 70)
    print("MAPEAMENTO tce_parser_v3 → kb-legal")
    print("=" * 70)

    import json
    print(json.dumps(doc, indent=2, ensure_ascii=False))

    errors = validate_kblegal_doc(doc)
    if errors:
        print(f"\n❌ ERROS: {errors}")
    else:
        print(f"\n✅ Documento válido - {len(doc)} campos preenchidos de 19")
        print(f"   Campos presentes: {sorted(doc.keys())}")
        print(f"   Campos ausentes: {sorted(KB_LEGAL_ALL_FIELDS - set(doc.keys()))}")
