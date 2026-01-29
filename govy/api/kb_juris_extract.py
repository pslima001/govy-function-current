# kb_juris_extract.py - Pipeline 2-pass para classificacao de jurisprudencia
# Versao: 2.0 | Data: 29/01/2026
# FIX: Enum clamp + robustez contra 500

"""
Pipeline de extracao e classificacao de jurisprudencia:
1. GPT-4o extrai campos (classificador)
2. Claude Sonnet audita (auditor)
3. Auto-approve se confidence >= 0.90 e auditor concorda
4. Senao, envia para review_queue

NOVIDADE v2.0:
- ENUM CLAMP obrigatorio antes de qualquer resposta
- Retry com backoff para chamadas LLM
- Validacao de payload antes de retornar
- Nunca retorna 500 por erro tratavel
"""

import azure.functions as func
import json
import logging
import time
import uuid
import traceback
from typing import Optional, Tuple

# Importar constantes e funcoes de clamp
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
    # Fallback se modulo nao existir ainda
    logging.warning("juris_constants nao encontrado, usando funcoes inline")
    
    def clamp_procedural_stage(v): return v or "NAO_CLARO"
    def clamp_holding_outcome(v): return v or "NAO_CLARO"
    def clamp_remedy_type(v): return v or "ORIENTACAO_GERAL"
    def clamp_effect(v): return v or "CONDICIONAL"
    def clamp_secao(v): return v or "NAO_CLARO"
    
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
# CONFIGURACOES
# ==============================================================================

MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Backoff exponencial
CONFIDENCE_THRESHOLD = 0.90
MIN_TEXT_LENGTH = 500  # Texto muito curto = skip


# ==============================================================================
# FUNCOES DE CHAMADA LLM COM RETRY
# ==============================================================================

def call_llm_with_retry(
    call_func,
    max_retries: int = MAX_RETRIES,
    delays: list = None
) -> Tuple[Optional[dict], Optional[str]]:
    """
    Chama LLM com retry e backoff.
    
    Args:
        call_func: Funcao que faz a chamada (deve retornar dict ou raise)
        max_retries: Numero maximo de tentativas
        delays: Lista de delays entre tentativas
    
    Returns:
        (result, error_message)
    """
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
    """
    Chama GPT-4o para extrair campos de classificacao.
    
    Returns:
        (classification_dict, error_message)
    """
    import os
    import openai
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return (None, "OPENAI_API_KEY nao configurada")
    
    client = openai.OpenAI(api_key=api_key)
    
    prompt = f"""Voce e um especialista em classificacao de jurisprudencia de licitacoes publicas brasileiras.

Analise o texto abaixo e extraia os seguintes campos:

1. secao: Qual secao do acordao? (EMENTA, RELATORIO, FUNDAMENTACAO, DISPOSITIVO, VOTO, NAO_CLARO)
2. procedural_stage: Fase processual discutida (EDITAL, DISPUTA, JULGAMENTO, HABILITACAO, CONTRATACAO, EXECUCAO, PAGAMENTO, SANCIONAMENTO, NAO_CLARO)
3. holding_outcome: Resultado da decisao (MANTEVE, AFASTOU, DETERMINOU_AJUSTE, ANULOU, NAO_CLARO)
4. remedy_type: Tipo de recurso/acao (IMPUGNACAO, RECURSO, CONTRARRAZOES, REPRESENTACAO, DENUNCIA, ORIENTACAO_GERAL, NAO_CLARO)
5. claim_pattern: Padrao da alegacao discutida (texto livre, max 100 chars)
6. effect: Efeito da decisao para licitantes (FLEXIBILIZA, RIGORIZA, CONDICIONAL)
7. vital: O trecho mais importante do texto que fundamenta a decisao (max 500 chars)
8. tese: A tese juridica aplicada (max 200 chars)

METADADOS:
- Tribunal: {metadata.get('tribunal', 'NAO_INFORMADO')}
- Ano: {metadata.get('year', 'NAO_INFORMADO')}
- Fonte: {metadata.get('source', 'NAO_INFORMADO')}

TEXTO PARA CLASSIFICAR:
{text[:8000]}

IMPORTANTE:
- Use APENAS os valores listados para cada campo
- Se nao conseguir determinar com certeza, use NAO_CLARO ou ORIENTACAO_GERAL
- O campo "vital" deve conter o trecho mais citavel do texto
- O campo "tese" deve sintetizar a posicao do tribunal

Responda APENAS com JSON valido:
{{"secao": "...", "procedural_stage": "...", "holding_outcome": "...", "remedy_type": "...", "claim_pattern": "...", "effect": "...", "vital": "...", "tese": "...", "confidence": 0.0-1.0}}
"""

    def make_call():
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        
        # Limpar markdown se presente
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        return json.loads(content)
    
    return call_llm_with_retry(make_call)


def call_claude_auditor(classification: dict, original_text: str) -> Tuple[Optional[dict], Optional[str]]:
    """
    Chama Claude para auditar classificacao.
    
    Returns:
        (audit_result, error_message)
    """
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
   - O "vital" realmente representa o trecho mais importante?
   - A "tese" sintetiza bem a posicao do tribunal?

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
        
        # Limpar markdown se presente
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()
        
        return json.loads(content)
    
    return call_llm_with_retry(make_call)


# ==============================================================================
# FUNCAO DE CLAMP DE CLASSIFICACAO
# ==============================================================================

def clamp_classification(classification: dict) -> dict:
    """
    Aplica clamp em todos os campos enum da classificacao.
    OBRIGATORIO antes de qualquer resposta ou upsert.
    
    Returns:
        Classificacao com todos os enums validos
    """
    if not classification:
        return {
            "secao": "NAO_CLARO",
            "procedural_stage": "NAO_CLARO",
            "holding_outcome": "NAO_CLARO",
            "remedy_type": "ORIENTACAO_GERAL",
            "effect": "CONDICIONAL",
            "claim_pattern": "",
            "vital": "",
            "tese": "",
            "confidence": 0.0
        }
    
    clamped = dict(classification)
    
    # Aplicar clamp em cada campo enum
    clamped["secao"] = clamp_secao(clamped.get("secao"))
    clamped["procedural_stage"] = clamp_procedural_stage(clamped.get("procedural_stage"))
    clamped["holding_outcome"] = clamp_holding_outcome(clamped.get("holding_outcome"))
    clamped["remedy_type"] = clamp_remedy_type(clamped.get("remedy_type"))
    clamped["effect"] = clamp_effect(clamped.get("effect"))
    
    # Garantir campos de texto
    clamped["claim_pattern"] = (clamped.get("claim_pattern") or "")[:200]
    clamped["vital"] = (clamped.get("vital") or "")[:1000]
    clamped["tese"] = (clamped.get("tese") or "")[:500]
    
    # Garantir confidence numerico
    try:
        clamped["confidence"] = float(clamped.get("confidence", 0.0))
    except (ValueError, TypeError):
        clamped["confidence"] = 0.0
    
    clamped["confidence"] = max(0.0, min(1.0, clamped["confidence"]))
    
    return clamped


# ==============================================================================
# FUNCAO PRINCIPAL DE BUILD CHUNK
# ==============================================================================

def build_chunk(
    text: str,
    classification: dict,
    metadata: dict
) -> dict:
    """
    Constroi chunk completo para indexacao.
    
    Args:
        text: Texto original
        classification: Classificacao extraida (ja clamped)
        metadata: Metadados (tribunal, year, source, uf)
    
    Returns:
        Chunk pronto para upsert
    """
    tribunal = metadata.get("tribunal", "TCU").upper()
    uf = metadata.get("uf")
    
    # Determinar region baseado em tribunal e uf
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
        "procedural_stage": classification.get("procedural_stage"),
        "holding_outcome": classification.get("holding_outcome"),
        "remedy_type": classification.get("remedy_type"),
        "claim_pattern": classification.get("claim_pattern"),
        "effect": classification.get("effect"),
        
        # Campos extras para debug
        "_tese": classification.get("tese"),
        "_confidence": classification.get("confidence"),
    }
    
    return chunk


# ==============================================================================
# HANDLER PRINCIPAL
# ==============================================================================

def handle_kb_juris_extract_all(req: func.HttpRequest) -> func.HttpResponse:
    """
    Endpoint POST /api/kb/juris/extract_all
    
    Request body:
    {
        "text": "texto do acordao...",
        "metadata": {
            "source": "TCU",
            "tribunal": "TCU",
            "year": 2025,
            "uf": null,  // null para TCU
            "title": "Acordao 123/2025",
            "citation": "TCU, Acordao 123/2025-Plenario"
        }
    }
    
    Response (sucesso):
    {
        "status": "success",
        "action": "auto_indexed" | "queued_for_review",
        "chunk_id": "uuid",
        "classification": {...},
        "audit": {...}
    }
    
    Response (erro tratavel):
    {
        "status": "failed",
        "error": "mensagem",
        "action": "queued_for_review",
        "reason": "LLM_TIMEOUT" | "LLM_INVALID_OUTPUT" | "TEXT_TOO_SHORT"
    }
    """
    try:
        # Parse request
        try:
            body = req.get_json()
        except ValueError:
            return func.HttpResponse(
                json.dumps({"status": "error", "message": "JSON invalido"}),
                status_code=400,
                mimetype="application/json"
            )
        
        text = body.get("text", "").strip()
        metadata = body.get("metadata", {})
        
        # Validar texto minimo
        if len(text) < MIN_TEXT_LENGTH:
            return func.HttpResponse(
                json.dumps({
                    "status": "skipped",
                    "reason": "TEXT_TOO_SHORT",
                    "message": f"Texto muito curto ({len(text)} chars, minimo {MIN_TEXT_LENGTH})"
                }),
                status_code=200,  # Nao e erro, e skip
                mimetype="application/json"
            )
        
        # Validar metadados minimos
        tribunal = metadata.get("tribunal", "TCU").upper()
        if tribunal not in ["TCU", "TCE"]:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "message": f"tribunal invalido: {tribunal}. Use TCU ou TCE."
                }),
                status_code=400,
                mimetype="application/json"
            )
        
        # Forcar uf=null para TCU
        if tribunal == "TCU":
            metadata["uf"] = None
        
        # PASSO 1: GPT-4o classifica
        classification_raw, classifier_error = call_gpt4o_classifier(text, metadata)
        
        if classifier_error:
            logging.error(f"Classificador falhou: {classifier_error}")
            # Nao retornar 500! Criar item para review
            return func.HttpResponse(
                json.dumps({
                    "status": "failed",
                    "action": "queued_for_review",
                    "reason": "LLM_CLASSIFIER_FAILED",
                    "error": classifier_error
                }),
                status_code=200,  # 200 porque foi tratado
                mimetype="application/json"
            )
        
        # APLICAR CLAMP OBRIGATORIO
        classification = clamp_classification(classification_raw)
        logging.info(f"Classificacao clamped: {classification}")
        
        # PASSO 2: Claude audita
        audit_result, audit_error = call_claude_auditor(classification, text)
        
        if audit_error:
            logging.warning(f"Auditor falhou: {audit_error}")
            # Sem auditor, vai para review
            audit_result = {
                "result": "SKIP",
                "justificativa": f"Auditor indisponivel: {audit_error}"
            }
        
        # Aplicar sugestoes do auditor (se houver)
        if audit_result and audit_result.get("sugestoes"):
            for campo, valor in audit_result["sugestoes"].items():
                if campo in classification:
                    classification[campo] = valor
            # Re-aplicar clamp apos sugestoes
            classification = clamp_classification(classification)
        
        # DECISAO: Auto-approve ou Review?
        confidence = classification.get("confidence", 0.0)
        auditor_concorda = audit_result and audit_result.get("result") == "CONCORDO"
        
        should_auto_approve = (
            confidence >= CONFIDENCE_THRESHOLD and
            auditor_concorda
        )
        
        # Construir chunk
        chunk = build_chunk(text, classification, metadata)
        
        # Remover campos com underscore (debug) do chunk final
        chunk_clean = {k: v for k, v in chunk.items() if not k.startswith("_")}
        
        if should_auto_approve:
            # AUTO-INDEXAR
            # TODO: Chamar upsert endpoint ou indexar direto
            action = "auto_indexed"
            logging.info(f"Auto-approved chunk: {chunk['chunk_id']}")
        else:
            # ENVIAR PARA REVIEW
            action = "queued_for_review"
            reason = []
            if confidence < CONFIDENCE_THRESHOLD:
                reason.append(f"confidence={confidence:.2f}<{CONFIDENCE_THRESHOLD}")
            if not auditor_concorda:
                reason.append(f"auditor={audit_result.get('result', 'N/A')}")
            
            logging.info(f"Queued for review: {chunk['chunk_id']}, reasons: {reason}")
            chunk_clean["_review_reason"] = "; ".join(reason)
        
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
        # Log detalhado mas retornar erro generico
        logging.error(f"Erro inesperado em extract_all: {str(e)}")
        logging.error(traceback.format_exc())
        
        # NUNCA retornar 500 com stack trace!
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "message": "Erro interno no processamento",
                "action": "queued_for_review",
                "reason": "INTERNAL_ERROR"
            }),
            status_code=500,
            mimetype="application/json"
        )


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    "handle_kb_juris_extract_all",
    "clamp_classification",
    "build_chunk",
    "call_gpt4o_classifier",
    "call_claude_auditor",
]
