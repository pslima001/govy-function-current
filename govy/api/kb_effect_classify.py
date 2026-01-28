# govy/api/kb_effect_classify.py
"""
Endpoint para classificacao automatica de efeito juridico
2-PASS: GPT-4o (classificador) + Claude Sonnet (auditor)
Versao: 1.0
"""
import os
import json
import logging
import azure.functions as func
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ============================================================
# SCHEMAS PARA FUNCTION CALLING
# ============================================================

CLASSIFY_EFFECT_SCHEMA = {
    "name": "classify_effect",
    "description": "Classifica o efeito juridico de um texto de jurisprudencia",
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "effect": {
                "type": "string",
                "enum": ["FLEXIBILIZA", "RIGORIZA", "CONDICIONAL"],
                "description": "Efeito juridico do texto"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Nivel de confianca na classificacao (0-1)"
            },
            "rationale": {
                "type": "string",
                "maxLength": 240,
                "description": "Justificativa breve da classificacao"
            },
            "evidence_quote": {
                "type": "string",
                "maxLength": 260,
                "description": "Trecho do texto que evidencia a classificacao"
            }
        },
        "required": ["effect", "confidence", "rationale", "evidence_quote"]
    }
}

AUDIT_EFFECT_SCHEMA = {
    "name": "audit_effect",
    "description": "Audita a classificacao de efeito juridico feita por outro modelo",
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "agree": {
                "type": "boolean",
                "description": "Se concorda com a classificacao original"
            },
            "final_effect": {
                "type": "string",
                "enum": ["FLEXIBILIZA", "RIGORIZA", "CONDICIONAL"],
                "description": "Efeito juridico final (pode ser diferente do original)"
            },
            "final_confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Nivel de confianca final"
            },
            "reason": {
                "type": "string",
                "maxLength": 240,
                "description": "Razao da concordancia ou discordancia"
            },
            "evidence_quote": {
                "type": "string",
                "maxLength": 260,
                "description": "Trecho que evidencia a decisao final"
            }
        },
        "required": ["agree", "final_effect", "final_confidence", "reason", "evidence_quote"]
    }
}

# ============================================================
# PROMPTS
# ============================================================

CLASSIFY_SYSTEM_PROMPT = """Voce e um especialista em direito administrativo brasileiro, especialmente licitacoes e contratos publicos.

Sua tarefa e classificar o EFEITO JURIDICO de um texto de jurisprudencia (acordao, sumula, decisao).

CRITERIOS DE CLASSIFICACAO:

FLEXIBILIZA:
- Afasta exigencia do edital
- Permite saneamento de falha formal
- Adota formalismo moderado
- Privilegia ampla participacao
- Relativiza descumprimento menor

RIGORIZA:
- Mantem exigencia do edital
- Confirma inabilitacao/desclassificacao
- Restringe possibilidade de saneamento
- Exige cumprimento estrito
- Confirma penalidade

CONDICIONAL:
- Usa expressoes como "desde que", "se houver justificativa"
- Depende do caso concreto
- Estabelece condicoes para aplicacao
- Nao e categorico em nenhuma direcao

Analise o texto e classifique usando a funcao classify_effect."""

AUDIT_SYSTEM_PROMPT = """Voce e um auditor juridico senior especializado em licitacoes.

Sua tarefa e AUDITAR a classificacao de efeito juridico feita por outro modelo.

O classificador original analisou um texto de jurisprudencia e chegou a uma conclusao.
Voce deve:
1. Reler o texto original
2. Avaliar se a classificacao esta CORRETA
3. Se discordar, fornecer a classificacao correta

CRITERIOS:
- FLEXIBILIZA: afasta exigencia, saneamento, formalismo moderado
- RIGORIZA: mantem exigencia, inabilitacao, restringe saneamento
- CONDICIONAL: "desde que", depende do caso

Seja rigoroso. A acuracia e mais importante que concordar com o classificador."""


def call_openai_classifier(content: str) -> Dict[str, Any]:
    """Passo A: Chama GPT-4o para classificar."""
    import openai
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY nao configurada")
    
    client = openai.OpenAI(api_key=api_key)
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": CLASSIFY_SYSTEM_PROMPT},
            {"role": "user", "content": f"Classifique o efeito juridico do seguinte texto:\n\n{content}"}
        ],
        tools=[{
            "type": "function",
            "function": CLASSIFY_EFFECT_SCHEMA
        }],
        tool_choice={"type": "function", "function": {"name": "classify_effect"}}
    )
    
    # Extrair resultado do function call
    tool_call = response.choices[0].message.tool_calls[0]
    result = json.loads(tool_call.function.arguments)
    
    return {
        "effect": result.get("effect"),
        "confidence": result.get("confidence"),
        "rationale": result.get("rationale"),
        "evidence_quote": result.get("evidence_quote")
    }


def call_claude_auditor(content: str, classifier_result: Dict[str, Any]) -> Dict[str, Any]:
    """Passo B: Chama Claude Sonnet para auditar."""
    import anthropic
    
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY nao configurada")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    audit_prompt = f"""Texto original da jurisprudencia:
---
{content}
---

Classificacao do modelo anterior:
- Efeito: {classifier_result['effect']}
- Confianca: {classifier_result['confidence']}
- Justificativa: {classifier_result['rationale']}
- Evidencia: {classifier_result['evidence_quote']}

Audite esta classificacao usando a funcao audit_effect."""
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=AUDIT_SYSTEM_PROMPT,
        tools=[{
            "name": "audit_effect",
            "description": AUDIT_EFFECT_SCHEMA["description"],
            "input_schema": AUDIT_EFFECT_SCHEMA["parameters"]
        }],
        tool_choice={"type": "tool", "name": "audit_effect"},
        messages=[
            {"role": "user", "content": audit_prompt}
        ]
    )
    
    # Extrair resultado do tool use
    for block in response.content:
        if block.type == "tool_use" and block.name == "audit_effect":
            result = block.input
            return {
                "agree": result.get("agree"),
                "final_effect": result.get("final_effect"),
                "final_confidence": result.get("final_confidence"),
                "reason": result.get("reason"),
                "evidence_quote": result.get("evidence_quote")
            }
    
    raise ValueError("Claude nao retornou tool_use esperado")


def main(req: func.HttpRequest) -> func.HttpResponse:
    """Handler principal do endpoint classify."""
    
    # CORS
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type"
            }
        )
    
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "JSON invalido"}),
            status_code=400,
            mimetype="application/json"
        )
    
    content = body.get("content")
    chunk_id = body.get("chunk_id")
    
    if not content:
        return func.HttpResponse(
            json.dumps({"status": "error", "message": "Campo 'content' obrigatorio"}),
            status_code=400,
            mimetype="application/json"
        )
    
    # Limitar tamanho do content para evitar custos excessivos
    max_chars = 8000
    if len(content) > max_chars:
        content = content[:max_chars] + "..."
    
    try:
        # ============================================================
        # PASSO A: CLASSIFICADOR (GPT-4o)
        # ============================================================
        logger.info(f"Classificando chunk {chunk_id} com GPT-4o")
        classifier_result = call_openai_classifier(content)
        logger.info(f"GPT-4o: {classifier_result['effect']} ({classifier_result['confidence']})")
        
        # ============================================================
        # PASSO B: AUDITOR (Claude Sonnet)
        # ============================================================
        logger.info(f"Auditando com Claude Sonnet")
        auditor_result = call_claude_auditor(content, classifier_result)
        logger.info(f"Claude: agree={auditor_result['agree']}, final={auditor_result['final_effect']} ({auditor_result['final_confidence']})")
        
        # ============================================================
        # DECISAO FINAL
        # ============================================================
        auto_approve = (
            auditor_result["agree"] == True and 
            auditor_result["final_confidence"] >= 0.90
        )
        
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "chunk_id": chunk_id,
                "classifier": {
                    "model": "gpt-4o",
                    "effect": classifier_result["effect"],
                    "confidence": classifier_result["confidence"],
                    "rationale": classifier_result["rationale"],
                    "evidence_quote": classifier_result["evidence_quote"]
                },
                "auditor": {
                    "model": "claude-sonnet-4",
                    "agree": auditor_result["agree"],
                    "final_effect": auditor_result["final_effect"],
                    "final_confidence": auditor_result["final_confidence"],
                    "reason": auditor_result["reason"],
                    "evidence_quote": auditor_result["evidence_quote"]
                },
                "decision": {
                    "effect": auditor_result["final_effect"],
                    "confidence": auditor_result["final_confidence"],
                    "auto_approve": auto_approve,
                    "requires_human_review": not auto_approve
                }
            }),
            status_code=200,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
        
    except Exception as e:
        logger.error(f"Erro na classificacao: {e}")
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(e)}),
            status_code=500,
            mimetype="application/json",
            headers={"Access-Control-Allow-Origin": "*"}
        )
