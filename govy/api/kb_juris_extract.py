# kb_juris_extract.py - Pipeline 2-pass para classificacao de jurisprudencia
# Versao: 3.0 | Data: 30/01/2026
# SPEC: Review Queue com validacao juridica completa

"""
Pipeline de extracao e classificacao de jurisprudencia:
1. GPT-4o extrai campos (classificador)
2. Claude Sonnet audita (auditor)
3. Auto-approve se confidence >= 0.90 e auditor concorda
4. Senao, envia para review_queue

NOVIDADES v3.0:
- Review Queue com Azure Blob Storage
- 4 status: pending, approved, rejected, blocked
- Validacao de citabilidade obrigatoria
- Checklist semantico (verbo_decisorio, regra_abstrata)
- Flags de risco (condicionalidade, excecao, mau_uso_rag)
- chunk_type separado de secao
"""

import azure.functions as func
import json
import logging
import time
import uuid
import traceback
import re
import os
from typing import Optional, Tuple
from datetime import datetime

# ==============================================================================
# IMPORTS - BLOB STORAGE
# ==============================================================================

try:
    from azure.storage.blob import BlobServiceClient, ContainerClient
    from govy.utils.azure_clients import get_blob_service_client as _get_blob_svc
except ImportError:
    logging.warning("azure-storage-blob nao instalado")
    BlobServiceClient = None
    ContainerClient = None
    _get_blob_svc = None
# ==============================================================================
# IMPORTS - JURIS CONSTANTS
# ==============================================================================

try:
    from govy.utils.juris_constants import (
        normalize_chunk_for_upsert,
        validate_chunk_for_upsert,
        clamp_procedural_stage,
        clamp_holding_outcome,
        clamp_remedy_type,
        clamp_effect,
        clamp_secao,
        UF_TO_REGION,
        AUTHORITY_SCORES,
    )
except ImportError:
    logging.warning("juris_constants nao encontrado, usando funcoes inline")

    def clamp_procedural_stage(v): return v if v in ["EDITAL","DISPUTA","JULGAMENTO","HABILITACAO","CONTRATACAO","EXECUCAO","PAGAMENTO","SANCIONAMENTO","NAO_CLARO"] else "NAO_CLARO"
    def clamp_holding_outcome(v): return v if v in ["MANTEVE","AFASTOU","DETERMINOU_AJUSTE","ANULOU","NAO_CLARO"] else "NAO_CLARO"
    def clamp_remedy_type(v): return v if v in ["IMPUGNACAO","RECURSO","CONTRARRAZOES","REPRESENTACAO","DENUNCIA","ORIENTACAO_GERAL","NAO_CLARO"] else "ORIENTACAO_GERAL"
    def clamp_effect(v): return v if v in ["FLEXIBILIZA","RIGORIZA","CONDICIONAL","NAO_CLARO"] else "CONDICIONAL"
    def clamp_secao(v): return v if v in ["EMENTA","RELATORIO","FUNDAMENTACAO","DISPOSITIVO","VOTO","TESE","VITAL","FUNDAMENTO_LEGAL","LIMITES","CONTEXTO_MINIMO","NAO_CLARO"] else "NAO_CLARO"

    UF_TO_REGION = {
        "SP": "SUDESTE", "RJ": "SUDESTE", "MG": "SUDESTE", "ES": "SUDESTE",
        "PR": "SUL", "SC": "SUL", "RS": "SUL",
        "BA": "NORDESTE", "PE": "NORDESTE", "CE": "NORDESTE", "MA": "NORDESTE",
        "PB": "NORDESTE", "RN": "NORDESTE", "AL": "NORDESTE", "SE": "NORDESTE", "PI": "NORDESTE",
        "GO": "CENTRO_OESTE", "MT": "CENTRO_OESTE", "MS": "CENTRO_OESTE", "DF": "CENTRO_OESTE",
        "AM": "NORTE", "PA": "NORTE", "AC": "NORTE", "RO": "NORTE",
        "RR": "NORTE", "AP": "NORTE", "TO": "NORTE"
    }
    AUTHORITY_SCORES = {"TCU": 0.90, "TCE": 0.80}

    def normalize_chunk_for_upsert(chunk, tribunal=None):
        return chunk

    def validate_chunk_for_upsert(chunk):
        return (True, [])


# ==============================================================================
# ENUMS E CONSTANTES
# ==============================================================================

CHUNK_TYPES = ["TESE", "VITAL", "FUNDAMENTO_LEGAL", "LIMITES", "CONTEXTO_MINIMO", "NAO_CLARO"]
ORGAO_JULGADOR = ["PLENARIO", "PRIMEIRA_CAMARA", "SEGUNDA_CAMARA", "OUTRO", "NAO_CLARO"]
MOTIVO_NAO_CITAVEL = ["SEM_LASTRO", "FRAGMENTADO", "DUPLICADO", "OUTRO"]
BLOCKED_REASONS = ["SEM_LASTRO", "MISTURA_TESE_VITAL", "ENUM_INCERTO", "CHUNK_QUEBRADO", "OUTRO"]
REVIEW_STATUS = ["APROVADO", "APROVADO_COM_EDICAO", "REJEITADO", "BLOQUEADO"]

MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]
CONFIDENCE_THRESHOLD = 0.90
MIN_TEXT_LENGTH = 500

REVIEW_QUEUE_CONTAINER = "review-queue"

# ==============================================================================
# HELPERS - SAFE RESPONSE / SAFE HANDLER / BLOB ACCESS
# ==============================================================================

def _json_response(payload: dict, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(payload, ensure_ascii=False),
        status_code=status_code,
        mimetype="application/json",
        headers={"Access-Control-Allow-Origin": "*"},
    )

def _safe_handler(fn_name: str, handler_fn):
    try:
        return handler_fn()
    except Exception as e:
        logging.exception("Unhandled error in %s", fn_name)  # traceback completo
        return _json_response(
            {"status": "error", "message": f"{fn_name} failed: {type(e).__name__}: {str(e)}"},
            status_code=500,
        )

def _get_blob_container_client():
    if BlobServiceClient is None:
        raise RuntimeError("azure-storage-blob nao instalado no ambiente")

    container_name = os.getenv("REVIEW_QUEUE_CONTAINER", REVIEW_QUEUE_CONTAINER)
    bsc = _get_blob_svc()
    return bsc.get_container_client(container_name)

def list_queue_items(folder: str, limit: int = 200) -> list:
    cc = _get_blob_container_client()
    prefix = f"{folder}/"
    items = []

    try:
        for b in cc.list_blobs(name_starts_with=prefix):
            try:
                data = cc.download_blob(b.name).readall()
                obj = json.loads(data)
                items.append(obj)
            except Exception:
                logging.warning("Skipping invalid blob json: %s", b.name, exc_info=True)

            if len(items) >= limit:
                break
    except Exception as e:
        logging.warning("Error listing blobs for prefix %s: %s", prefix, str(e), exc_info=True)
        return []

    return items



# ==============================================================================
# FUNCOES DE CLAMP
# ==============================================================================

def clamp_chunk_type(v):
    """Clamp chunk_type para valores validos."""
    if v and v.upper() in CHUNK_TYPES:
        return v.upper()
    return "NAO_CLARO"


def clamp_orgao_julgador(v):
    """Clamp orgao_julgador para valores validos."""
    if not v:
        return "NAO_CLARO"
    v_upper = v.upper().replace(" ", "_").replace("-", "_")
    if v_upper in ORGAO_JULGADOR:
        return v_upper
    if "PLEN" in v_upper:
        return "PLENARIO"
    if "PRIMEIRA" in v_upper or "1" in v_upper:
        return "PRIMEIRA_CAMARA"
    if "SEGUNDA" in v_upper or "2" in v_upper:
        return "SEGUNDA_CAMARA"
    return "OUTRO"


def parse_acordao_numero(citation: str) -> Optional[str]:
    """Extrai numero do acordao de uma citacao."""
    if not citation:
        return None
    # Padroes: "Acordao 123/2024", "AC-123-2024", "123/2024-Plenario"
    patterns = [
        r'[Aa]c[oó]rd[aã]o\s*n?[ºo]?\s*(\d+[/-]\d{4})',
        r'[Aa][Cc][-_]?(\d+[-/]\d{4})',
        r'(\d{1,5}[/-]\d{4})[-\s]*[Pp]len',
        r'(\d{1,5}[/-]\d{4})',
    ]
    for pattern in patterns:
        match = re.search(pattern, citation)
        if match:
            num = match.group(1).replace("-", "/")
            return num
    return None


def parse_data_julgamento(text: str) -> Optional[str]:
    """Extrai data de julgamento do texto (retorna ISO YYYY-MM-DD quando possível)."""
    if not text:
        return None

    # 1) formatos numéricos: dd/mm/aaaa ou dd-mm-aaaa
    m = re.search(r'\b(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})\b', text)
    if m:
        d = int(m.group(1))
        mo = int(m.group(2))
        y = int(m.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2100:
            return f"{y:04d}-{mo:02d}-{d:02d}"

    # 2) formatos textuais: "30 de janeiro de 2026"
    meses = {
        "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
        "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12
    }
    m2 = re.search(r'\b(\d{1,2})\s+de\s+([A-Za-zçÇáàâãéêíóôõúüÁÀÂÃÉÊÍÓÔÕÚÜ]+)\s+de\s+(\d{4})\b', text, flags=re.IGNORECASE)
    if m2:
        d = int(m2.group(1))
        mes_raw = m2.group(2).lower()
        mes = meses.get(mes_raw)
        y = int(m2.group(3))
        if mes and 1 <= d <= 31 and 1900 <= y <= 2100:
            return f"{y:04d}-{mes:02d}-{d:02d}"

    # 3) fallback: procurar "julgado em dd/mm/aaaa"
    m3 = re.search(r'julgad[oa]\s+em\s+(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})', text, flags=re.IGNORECASE)
    if m3:
        d = int(m3.group(1)); mo = int(m3.group(2)); y = int(m3.group(3))
        if 1 <= d <= 31 and 1 <= mo <= 12 and 1900 <= y <= 2100:
            return f"{y:04d}-{mo:02d}-{d:02d}"

    return None
# Padroes: "12/03/2024", "12.03.2024", "2024-03-12"
    patterns = [
        r'(\d{2}[/.-]\d{2}[/.-]\d{4})',
        r'(\d{4}[/.-]\d{2}[/.-]\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


# ==============================================================================
# BLOB STORAGE HELPERS
# ==============================================================================

def get_blob_container() -> ContainerClient:
    """Retorna container client para review-queue."""
    blob_service = _get_blob_svc()
    container = blob_service.get_container_client(REVIEW_QUEUE_CONTAINER)
    
    try:
        container.get_container_properties()
    except:
        container.create_container()
    
    return container


def save_to_queue(folder: str, item_id: str, data: dict) -> bool:
    """Salva item em uma pasta do blob storage."""
    try:
        container = get_blob_container()
        blob_name = f"{folder}/{item_id}.json"
        
        container.upload_blob(
            name=blob_name,
            data=json.dumps(data, ensure_ascii=False, indent=2),
            overwrite=True
        )
        logging.info(f"Saved to {blob_name}")
        return True
    except Exception as e:
        logging.error(f"Failed to save to {folder}: {e}")
        return False


def load_from_queue(folder: str, item_id: str) -> Optional[dict]:
    """Carrega item de uma pasta do blob storage."""
    try:
        container = get_blob_container()
        blob_name = f"{folder}/{item_id}.json"
        blob_client = container.get_blob_client(blob_name)
        content = blob_client.download_blob().readall()
        return json.loads(content)
    except Exception:
        return None


def delete_from_queue(folder: str, item_id: str) -> bool:
    """Deleta item de uma pasta do blob storage."""
    try:
        container = get_blob_container()
        blob_name = f"{folder}/{item_id}.json"
        blob_client = container.get_blob_client(blob_name)
        blob_client.delete_blob()
        return True
    except Exception:
        return False


def move_in_queue(from_folder: str, to_folder: str, item_id: str, extra_data: dict = None) -> bool:
    """Move item entre pastas, opcionalmente adicionando dados."""
    data = load_from_queue(from_folder, item_id)
    if not data:
        return False
    
    if extra_data:
        data.update(extra_data)
    
    if save_to_queue(to_folder, item_id, data):
        delete_from_queue(from_folder, item_id)
        return True
    return False


# ==============================================================================
# FUNCOES LLM COM RETRY
# ==============================================================================

def call_llm_with_retry(call_func, max_retries: int = MAX_RETRIES, delays: list = None) -> Tuple[Optional[dict], Optional[str]]:
    """Chama LLM com retry e backoff."""
    delays = delays or RETRY_DELAYS
    last_error = None

    for attempt in range(max_retries):
        try:
            result = call_func()
            return (result, None)
        except Exception as e:
            last_error = str(e)
            logging.warning(f"LLM call attempt {attempt + 1} failed: {last_error}")
            if attempt < max_retries - 1:
                delay = delays[min(attempt, len(delays) - 1)]
                time.sleep(delay)

    return (None, f"LLM call failed after {max_retries} attempts: {last_error}")


def call_gpt4o_classifier(text: str, metadata: dict) -> Tuple[Optional[dict], Optional[str]]:
    """Chama GPT-4o para extrair campos de classificacao."""
    import os
    import openai

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return (None, "OPENAI_API_KEY nao configurada")

    client = openai.OpenAI(api_key=api_key)

    prompt = f"""Voce e um especialista em classificacao de jurisprudencia de licitacoes publicas brasileiras.

Analise o texto abaixo e extraia os seguintes campos:

1. secao: Qual secao do acordao? (EMENTA, RELATORIO, FUNDAMENTACAO, DISPOSITIVO, VOTO, NAO_CLARO)
2. chunk_type: Tipo juridico do conteudo (TESE, VITAL, FUNDAMENTO_LEGAL, LIMITES, CONTEXTO_MINIMO, NAO_CLARO)
3. procedural_stage: Fase processual (EDITAL, DISPUTA, JULGAMENTO, HABILITACAO, CONTRATACAO, EXECUCAO, PAGAMENTO, SANCIONAMENTO, NAO_CLARO)
4. holding_outcome: Resultado (MANTEVE, AFASTOU, DETERMINOU_AJUSTE, ANULOU, NAO_CLARO)
5. remedy_type: Tipo de recurso (IMPUGNACAO, RECURSO, CONTRARRAZOES, REPRESENTACAO, DENUNCIA, ORIENTACAO_GERAL, NAO_CLARO)
6. claim_pattern: Padrao da alegacao (texto livre, max 100 chars)
7. effect: Efeito (FLEXIBILIZA, RIGORIZA, CONDICIONAL, NAO_CLARO)
8. vital: Trecho mais importante/citavel (max 500 chars)
9. tese: Tese juridica abstrata (max 200 chars)
10. orgao_julgador: Orgao (PLENARIO, PRIMEIRA_CAMARA, SEGUNDA_CAMARA, OUTRO, NAO_CLARO)
11. acordao_numero: Numero no formato 123/2024 (se encontrar)
12. data_julgamento: Data no formato DD/MM/YYYY (se encontrar)
13. tem_verbo_decisorio: true/false - o vital tem verbo decisorio explicito?
14. e_regra_abstrata: true/false - a tese e uma regra generalizavel?
15. possui_condicionalidade: true/false - tem "desde que", "salvo", "excepcionalmente"?
16. excecao_relevante: true/false - e uma excecao a regra geral?

METADADOS:
- Tribunal: {metadata.get('tribunal', 'NAO_INFORMADO')}
- Ano: {metadata.get('year', 'NAO_INFORMADO')}
- Fonte: {metadata.get('source', 'NAO_INFORMADO')}

TEXTO PARA CLASSIFICAR:
{text[:8000]}

Responda APENAS com JSON valido:
{{"secao": "...", "chunk_type": "...", "procedural_stage": "...", "holding_outcome": "...", "remedy_type": "...", "claim_pattern": "...", "effect": "...", "vital": "...", "tese": "...", "orgao_julgador": "...", "acordao_numero": "...", "data_julgamento": "...", "tem_verbo_decisorio": true/false, "e_regra_abstrata": true/false, "possui_condicionalidade": true/false, "excecao_relevante": true/false, "confidence": 0.0-1.0}}
"""

    def make_call():
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())

    return call_llm_with_retry(make_call)


def call_claude_auditor(classification: dict, original_text: str) -> Tuple[Optional[dict], Optional[str]]:
    """Chama Claude para auditar classificacao."""
    import os
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return (None, "ANTHROPIC_API_KEY nao configurada")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Voce e um auditor de classificacao de jurisprudencia.

O classificador GPT-4o gerou a seguinte classificacao:
{json.dumps(classification, indent=2, ensure_ascii=False)}

Texto original (primeiros 4000 chars):
{original_text[:4000]}

Sua tarefa:
1. Verificar se a classificacao esta CORRETA
2. Focar especialmente em:
   - O "effect" (FLEXIBILIZA/RIGORIZA/CONDICIONAL) esta correto?
   - O "chunk_type" esta correto? (TESE vs VITAL especialmente)
   - O "vital" realmente representa o trecho mais importante?
   - A "tese" e abstrata e generalizavel?
   - tem_verbo_decisorio e e_regra_abstrata estao corretos?

Responda APENAS com JSON:
{{"result": "CONCORDO" ou "DISCORDO", "justificativa": "breve explicacao", "sugestoes": {{"campo": "valor_corrigido"}} ou null}}
"""

    def make_call():
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.content[0].text.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content.strip())

    return call_llm_with_retry(make_call)


# ==============================================================================
# FUNCAO DE CLAMP DE CLASSIFICACAO
# ==============================================================================

def clamp_classification(classification: dict) -> dict:
    """Aplica clamp em todos os campos enum da classificacao."""
    if not classification:
        return {
            "secao": "NAO_CLARO",
            "chunk_type": "NAO_CLARO",
            "procedural_stage": "NAO_CLARO",
            "holding_outcome": "NAO_CLARO",
            "remedy_type": "ORIENTACAO_GERAL",
            "effect": "CONDICIONAL",
            "orgao_julgador": "NAO_CLARO",
            "claim_pattern": "",
            "vital": "",
            "tese": "",
            "acordao_numero": None,
            "data_julgamento": None,
            "tem_verbo_decisorio": False,
            "e_regra_abstrata": False,
            "possui_condicionalidade": False,
            "excecao_relevante": False,
            "potencial_mau_uso_em_rag": False,
            "confidence": 0.0
        }

    clamped = dict(classification)

    # Enums
    clamped["secao"] = clamp_secao(clamped.get("secao"))
    clamped["chunk_type"] = clamp_chunk_type(clamped.get("chunk_type"))
    clamped["procedural_stage"] = clamp_procedural_stage(clamped.get("procedural_stage"))
    clamped["holding_outcome"] = clamp_holding_outcome(clamped.get("holding_outcome"))
    clamped["remedy_type"] = clamp_remedy_type(clamped.get("remedy_type"))
    clamped["effect"] = clamp_effect(clamped.get("effect"))
    clamped["orgao_julgador"] = clamp_orgao_julgador(clamped.get("orgao_julgador"))

    # Textos
    clamped["claim_pattern"] = (clamped.get("claim_pattern") or "")[:200]
    clamped["vital"] = (clamped.get("vital") or "")[:1000]
    clamped["tese"] = (clamped.get("tese") or "")[:500]

    # Citabilidade
    clamped["acordao_numero"] = clamped.get("acordao_numero") or None
    clamped["data_julgamento"] = clamped.get("data_julgamento") or None

    # Booleans
    clamped["tem_verbo_decisorio"] = bool(clamped.get("tem_verbo_decisorio"))
    clamped["e_regra_abstrata"] = bool(clamped.get("e_regra_abstrata"))
    clamped["possui_condicionalidade"] = bool(clamped.get("possui_condicionalidade"))
    clamped["excecao_relevante"] = bool(clamped.get("excecao_relevante"))
    clamped["potencial_mau_uso_em_rag"] = bool(clamped.get("potencial_mau_uso_em_rag", False))

    # Confidence
    try:
        clamped["confidence"] = float(clamped.get("confidence", 0.0))
    except (ValueError, TypeError):
        clamped["confidence"] = 0.0
    clamped["confidence"] = max(0.0, min(1.0, clamped["confidence"]))

    return clamped


# ==============================================================================
# VALIDACAO DE CITABILIDADE
# ==============================================================================

def validate_citabilidade(data: dict) -> Tuple[bool, Optional[str]]:
    """
    Valida se item tem citabilidade minima para indexacao.
    
    Returns:
        (citavel, motivo_nao_citavel)
    """
    classification = data.get("classification", {})
    metadata = data.get("metadata", {})
    
    # Precisa ter acordao_numero OU citation valida
    acordao = classification.get("acordao_numero") or parse_acordao_numero(metadata.get("citation", ""))
    if not acordao:
        return (False, "SEM_LASTRO")
    
    # Precisa ter tribunal
    tribunal = metadata.get("tribunal")
    if not tribunal:
        return (False, "SEM_LASTRO")
    
    # Precisa ter ano ou data
    year = metadata.get("year")
    data_julg = classification.get("data_julgamento")
    if not year and not data_julg:
        return (False, "SEM_LASTRO")
    
    return (True, None)


def validate_checklist_semantico(data: dict) -> Tuple[bool, list]:
    """
    Valida checklist semantico obrigatorio.
    
    Returns:
        (valido, erros)
    """
    classification = data.get("classification", {})
    chunk_type = classification.get("chunk_type", "NAO_CLARO")
    erros = []
    
    # VITAL exige verbo decisorio
    if chunk_type == "VITAL" and not classification.get("tem_verbo_decisorio"):
        erros.append("VITAL requer tem_verbo_decisorio=true")
    
    # TESE exige regra abstrata
    if chunk_type == "TESE" and not classification.get("e_regra_abstrata"):
        erros.append("TESE requer e_regra_abstrata=true")
    
    return (len(erros) == 0, erros)


# ==============================================================================
# FUNCAO PRINCIPAL DE BUILD CHUNK
# ==============================================================================

def build_chunk(text: str, classification: dict, metadata: dict) -> dict:
    """Constroi chunk completo para indexacao."""
    tribunal = metadata.get("tribunal", "TCU").upper()
    uf = metadata.get("uf")

    if tribunal == "TCU":
        uf = None
        region = None
    elif tribunal == "TCE" and uf:
        uf = uf.upper()
        region = UF_TO_REGION.get(uf)
    else:
        region = None

    chunk = {
        "chunk_id": str(uuid.uuid4()),
        "doc_type": "jurisprudencia",
        "source": metadata.get("source", tribunal),
        "tribunal": tribunal,
        "uf": uf,
        "region": region,
        "title": metadata.get("title", f"{tribunal} - Classificacao Automatica"),
        "content": classification.get("vital") or text[:1000],
        "citation": metadata.get("citation", ""),
        "year": metadata.get("year"),
        "authority_score": AUTHORITY_SCORES.get(tribunal, 0.80),
        "is_current": True,

        # Campos SPEC 1.2
        "secao": classification.get("secao"),
        "chunk_type": classification.get("chunk_type"),
        "procedural_stage": classification.get("procedural_stage"),
        "holding_outcome": classification.get("holding_outcome"),
        "remedy_type": classification.get("remedy_type"),
        "claim_pattern": classification.get("claim_pattern"),
        "effect": classification.get("effect"),
        
        # Citabilidade estruturada
        "acordao_numero": classification.get("acordao_numero"),
        "orgao_julgador": classification.get("orgao_julgador"),
        "data_julgamento": classification.get("data_julgamento"),
        
        # Flags de risco
        "possui_condicionalidade": classification.get("possui_condicionalidade", False),
        "excecao_relevante": classification.get("excecao_relevante", False),
        "potencial_mau_uso_em_rag": classification.get("potencial_mau_uso_em_rag", False),

        # Debug
        "_tese": classification.get("tese"),
        "_confidence": classification.get("confidence"),
    }

    return chunk


# ==============================================================================
# HANDLER PRINCIPAL - EXTRACT ALL
# ==============================================================================

def handle_kb_juris_extract_all(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/kb/juris/extract_all"""
    try:
        try:
            body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "JSON invalido"}),
                status_code=400,
                mimetype="application/json"
            )

        text = (body.get("full_text") or body.get("text") or "").strip()
        metadata = body.get("doc_meta") or body.get("metadata") or {}
        logging.info(f"extract_all received: text_len={len(text)}, keys={list(body.keys())}")

        if len(text) < MIN_TEXT_LENGTH:
            return func.HttpResponse(
                json.dumps({
                    "status": "skipped",
                    "reason": "TEXT_TOO_SHORT",
                    "message": f"Texto muito curto ({len(text)} chars, minimo {MIN_TEXT_LENGTH})"
                }),
                status_code=200,
                mimetype="application/json"
            )

        tribunal = metadata.get("tribunal", "TCU").upper()
        if tribunal not in ["TCU", "TCE"]:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": f"tribunal invalido: {tribunal}"}),
                status_code=400,
                mimetype="application/json"
            )

        if tribunal == "TCU":
            metadata["uf"] = None

        # PASSO 1: GPT-4o classifica
        classification_raw, classifier_error = call_gpt4o_classifier(text, metadata)

        if classifier_error:
            logging.error(f"Classificador falhou: {classifier_error}")
            return func.HttpResponse(
                json.dumps({
                    "status": "failed",
                    "action": "queued_for_review",
                    "reason": "LLM_CLASSIFIER_FAILED",
                    "error": classifier_error
                }),
                status_code=200,
                mimetype="application/json"
            )

        # APLICAR CLAMP
        classification = clamp_classification(classification_raw)
        logging.info(f"Classificacao clamped: {classification}")

        # PASSO 2: Claude audita
        audit_result, audit_error = call_claude_auditor(classification, text)

        if audit_error:
            logging.warning(f"Auditor falhou: {audit_error}")
            audit_result = {"result": "SKIP", "justificativa": f"Auditor indisponivel: {audit_error}"}

        # Aplicar sugestoes
        if audit_result and audit_result.get("sugestoes"):
            for campo, valor in audit_result["sugestoes"].items():
                if campo in classification:
                    classification[campo] = valor
            classification = clamp_classification(classification)

        # DECISAO
        confidence = classification.get("confidence", 0.0)
        auditor_concorda = audit_result and audit_result.get("result") == "CONCORDO"
        should_auto_approve = confidence >= CONFIDENCE_THRESHOLD and auditor_concorda

        # Construir chunk
        chunk = build_chunk(text, classification, metadata)
        chunk_clean = {k: v for k, v in chunk.items() if not k.startswith("_")}

        if should_auto_approve:
            action = "auto_indexed"
            logging.info(f"Auto-approved chunk: {chunk['chunk_id']}")
        else:
            action = "queued_for_review"
            reason = []
            if confidence < CONFIDENCE_THRESHOLD:
                reason.append(f"confidence={confidence:.2f}<{CONFIDENCE_THRESHOLD}")
            if not auditor_concorda:
                reason.append(f"auditor={audit_result.get('result', 'N/A')}")

            logging.info(f"Queued for review: {chunk['chunk_id']}, reasons: {reason}")
            chunk_clean["_review_reason"] = "; ".join(reason)
            
            # PERSISTIR NA FILA
            queue_data = {
                "chunk": chunk_clean,
                "classification": classification,
                "audit": audit_result,
                "original_text": text,  # Texto completo para popup
                "metadata": metadata,
                "_queue_status": "pending",
                "_queued_at": datetime.utcnow().isoformat() + "Z"
            }
            save_to_queue("pending", chunk["chunk_id"], queue_data)

        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "action": action,
                "chunk_id": chunk["chunk_id"],
                "classification": classification,
                "audit": audit_result,
                "chunk": chunk_clean
            }, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logging.error(f"Erro inesperado em extract_all: {str(e)}")
        logging.error(traceback.format_exc())
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "Erro interno", "action": "queued_for_review"}),
            status_code=500,
            mimetype="application/json"
        )


# ==============================================================================
# HANDLERS REVIEW QUEUE
# ==============================================================================

def list_review_queue(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/kb/juris/review_queue - Lista itens pendentes."""
    try:
        container = get_blob_container()
        items = []
        
        for blob in container.list_blobs(name_starts_with="pending/"):
            try:
                blob_client = container.get_blob_client(blob.name)
                content = blob_client.download_blob().readall()
                data = json.loads(content)
                
                item_id = blob.name.replace("pending/", "").replace(".json", "")
                classification = data.get("classification", {})
                
                items.append({
                    "item_id": item_id,
                    "title": data.get("chunk", {}).get("title", "Sem titulo"),
                    "tribunal": data.get("metadata", {}).get("tribunal", "N/A"),
                    "acordao_numero": classification.get("acordao_numero", ""),
                    "chunk_type": classification.get("chunk_type", "NAO_CLARO"),
                    "claim_pattern": classification.get("claim_pattern", ""),
                    "confidence": classification.get("confidence", 0),
                    "queued_at": data.get("_queued_at", ""),
                    "review_reason": data.get("chunk", {}).get("_review_reason", "")
                })
            except Exception as e:
                logging.warning(f"Error reading blob {blob.name}: {e}")

        items.sort(key=lambda x: x.get("queued_at", ""))

        return func.HttpResponse(
            json.dumps({"status": "success", "total": len(items), "items": items}, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )

    except Exception as e:
        logging.error(f"Error listing review queue: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )


def get_review_item(req: func.HttpRequest) -> func.HttpResponse:
    """GET /api/kb/juris/review_queue/{item_id} - Obtem item para revisao."""
    try:
        item_id = req.route_params.get("item_id")
        if not item_id:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "item_id obrigatorio"}),
                status_code=400,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        data = load_from_queue("pending", item_id)
        if not data:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": f"Item nao encontrado: {item_id}"}),
                status_code=404,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        return func.HttpResponse(
            json.dumps({"status": "success", "item_id": item_id, "data": data}, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )

    except Exception as e:
        logging.error(f"Error getting review item: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )


def approve_review_item(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/kb/juris/review_queue/{item_id}/approve - Aprova item."""
    try:
        item_id = req.route_params.get("item_id")
        if not item_id:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "item_id obrigatorio"}),
                status_code=400,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        try:
            body = req.get_json() or {}
        except:
            body = {}

        data = load_from_queue("pending", item_id)
        if not data:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": f"Item nao encontrado: {item_id}"}),
                status_code=404,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        # Aplicar edicoes
        if body.get("edited_classification"):
            data["classification"] = {**data.get("classification", {}), **body["edited_classification"]}
            data["classification"] = clamp_classification(data["classification"])

        if body.get("edited_chunk"):
            data["chunk"] = {**data.get("chunk", {}), **body["edited_chunk"]}

        # VALIDACAO DE CITABILIDADE (bloqueante)
        citavel, motivo = validate_citabilidade(data)
        if not citavel:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "code": "CITABILIDADE_INVALIDA",
                    "message": f"Item nao citavel: {motivo}",
                    "action": "Use BLOQUEAR ou preencha campos obrigatorios"
                }),
                status_code=422,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        # VALIDACAO DE CHECKLIST SEMANTICO (bloqueante)
        checklist_ok, erros = validate_checklist_semantico(data)
        if not checklist_ok:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "code": "CHECKLIST_INVALIDO",
                    "message": "Checklist semantico falhou",
                    "erros": erros,
                    "action": "Corrija os campos ou use BLOQUEAR"
                }),
                status_code=422,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        # Atualizar chunk com classification final
        chunk = data.get("chunk", {})
        classification = data.get("classification", {})
        
        for field in ["secao", "chunk_type", "procedural_stage", "holding_outcome", 
                      "remedy_type", "claim_pattern", "effect", "acordao_numero",
                      "orgao_julgador", "data_julgamento", "possui_condicionalidade",
                      "excecao_relevante", "potencial_mau_uso_em_rag"]:
            if field in classification:
                chunk[field] = classification[field]
        
        chunk["content"] = classification.get("vital") or chunk.get("content", "")
        chunk["citavel"] = True
        chunk["indexable"] = True
        
        chunk_clean = {k: v for k, v in chunk.items() if not k.startswith("_")}

        # Indexar via kb_index_upsert
        indexed = False
        try:
            from govy.api.kb_index_upsert import upsert_chunks
            result = upsert_chunks([chunk_clean])
            indexed = result.get("success", False)
        except Exception as e:
            logging.error(f"Upsert failed: {e}")

        # Determinar status
        status = "APROVADO_COM_EDICAO" if body.get("edited_classification") or body.get("edited_chunk") else "APROVADO"

        # Mover para approved/
        data["_queue_status"] = status
        data["_approved_at"] = datetime.utcnow().isoformat() + "Z"
        data["_reviewer_notes"] = body.get("reviewer_notes", "")
        data["_indexed"] = indexed
        data["chunk"] = chunk_clean

        move_in_queue("pending", "approved", item_id, {
            "_queue_status": status,
            "_approved_at": datetime.utcnow().isoformat() + "Z",
            "_reviewer_notes": body.get("reviewer_notes", ""),
            "_indexed": indexed
        })

        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "message": f"Item {status}" + (" e indexado" if indexed else " (indexacao pendente)"),
                "item_id": item_id,
                "indexed": indexed,
                "review_status": status
            }, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )

    except Exception as e:
        logging.error(f"Error approving item: {e}")
        logging.error(traceback.format_exc())
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )


def reject_review_item(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/kb/juris/review_queue/{item_id}/reject - Rejeita item."""
    try:
        item_id = req.route_params.get("item_id")
        if not item_id:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "item_id obrigatorio"}),
                status_code=400,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        try:
            body = req.get_json() or {}
        except:
            body = {}

        rejection_reason = body.get("rejection_reason", "").strip()
        if not rejection_reason or len(rejection_reason) < 10:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "rejection_reason obrigatorio (min 10 chars)"}),
                status_code=400,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        data = load_from_queue("pending", item_id)
        if not data:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": f"Item nao encontrado: {item_id}"}),
                status_code=404,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        move_in_queue("pending", "rejected", item_id, {
            "_queue_status": "REJEITADO",
            "_rejected_at": datetime.utcnow().isoformat() + "Z",
            "_rejection_reason": rejection_reason
        })

        return func.HttpResponse(
            json.dumps({"status": "success", "message": "Item rejeitado", "item_id": item_id}, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )

    except Exception as e:
        logging.error(f"Error rejecting item: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )


def block_review_item(req: func.HttpRequest) -> func.HttpResponse:
    """POST /api/kb/juris/review_queue/{item_id}/block - Bloqueia item para reprocessamento."""
    try:
        item_id = req.route_params.get("item_id")
        if not item_id:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "item_id obrigatorio"}),
                status_code=400,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        try:
            body = req.get_json() or {}
        except:
            body = {}

        blocked_reason = body.get("blocked_reason", "OUTRO")
        if blocked_reason not in BLOCKED_REASONS:
            blocked_reason = "OUTRO"

        data = load_from_queue("pending", item_id)
        if not data:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": f"Item nao encontrado: {item_id}"}),
                status_code=404,
                mimetype="application/json",
                headers={"Access-Control-Allow-Origin": "*"}
            )

        move_in_queue("pending", "blocked", item_id, {
            "_queue_status": "BLOQUEADO",
            "_blocked_at": datetime.utcnow().isoformat() + "Z",
            "_blocked_reason": blocked_reason,
            "_blocked_notes": body.get("blocked_notes", ""),
            "_needs_rechunk": body.get("needs_rechunk", False),
            "_needs_reextract": body.get("needs_reextract", False)
        })

        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "message": "Item bloqueado para reprocessamento",
                "item_id": item_id,
                "blocked_reason": blocked_reason
            }, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )

    except Exception as e:
        logging.error(f"Error blocking item: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )


# Alias para function_app.py
main = handle_kb_juris_extract_all


# ==============================================================================
# EXPORTS
# ==============================================================================


# ==============================================================================
# LIST/ STATS ENDPOINTS (ROBUST)
# ==============================================================================

def list_approved_items(req: func.HttpRequest) -> func.HttpResponse:
    return _safe_handler("list_approved_items", lambda: _json_response({
        "status": "success",
        "total": len(list_queue_items("approved")),
        "items": list_queue_items("approved"),
    }))

def list_blocked_items(req: func.HttpRequest) -> func.HttpResponse:
    return _safe_handler("list_blocked_items", lambda: _json_response({
        "status": "success",
        "total": len(list_queue_items("blocked")),
        "items": list_queue_items("blocked"),
    }))

def list_rejected_items(req: func.HttpRequest) -> func.HttpResponse:
    return _safe_handler("list_rejected_items", lambda: _json_response({
        "status": "success",
        "total": len(list_queue_items("rejected")),
        "items": list_queue_items("rejected"),
    }))

def get_queue_stats(req: func.HttpRequest) -> func.HttpResponse:
    def _run():
        pending = len(list_queue_items("pending", limit=1000))
        approved = len(list_queue_items("approved", limit=1000))
        rejected = len(list_queue_items("rejected", limit=1000))
        blocked = len(list_queue_items("blocked", limit=1000))
        return _json_response({
            "status": "success",
            "stats": {
                "pending": pending,
                "approved": approved,
                "rejected": rejected,
                "blocked": blocked,
                "total": pending + approved + rejected + blocked
            }
        })
    return _safe_handler("get_queue_stats", _run)

__all__ = [
    "handle_kb_juris_extract_all",
    "main",
    "clamp_classification",
    "build_chunk",
    "call_gpt4o_classifier",
    "call_claude_auditor",
    "list_review_queue",
    "get_review_item",
    "approve_review_item",
    "reject_review_item",
    "block_review_item",
    "save_to_queue",
    "validate_citabilidade",
    "validate_checklist_semantico",
]





