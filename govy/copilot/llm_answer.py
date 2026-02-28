# govy/copilot/llm_answer.py
"""
Answer Builder — gera resposta via LLM usando SOMENTE evidência interna.

Fluxo:
1. Monta system prompt com regras da policy
2. Monta user prompt com query + evidências
3. Chama LLM (Anthropic Claude)
4. Parseia resposta JSON
5. Valida contra policy (sem doutrina, sem externo, sem defesa)
"""
import os
import json
import logging
import re
import time
from typing import List, Optional

import requests

from govy.copilot.contracts import Evidence, Tone

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("COPILOT_LLM_MODEL", "claude-sonnet-4-20250514")


# ─── System Prompts por tom ──────────────────────────────────────────

_SYSTEM_BASE = """Você é o Copiloto Jurídico GOVY, assistente especializado em licitações públicas brasileiras.

REGRAS ABSOLUTAS (nunca violar):
1. NUNCA citar doutrina (livros, autores, professores, obras acadêmicas).
2. NUNCA usar fontes externas (internet, Wikipedia, sites de terceiros).
3. NUNCA gerar peças de defesa (recursos, impugnações, contrarrazões, petições).
4. Responder SOMENTE com base nas evidências internas fornecidas abaixo.
5. Se não houver evidência suficiente, dizer "não encontrei no material analisado" e sugerir documentos que o usuário pode fornecer.
6. Se houver entendimentos divergentes, explicar ambos os lados com base em evidência e indicar o risco — sem aconselhar como peça de defesa.

Responda SEMPRE em JSON com este formato exato:
{
  "answer": "sua resposta aqui",
  "uncertainty": "explicação de incerteza, se houver" ou null,
  "followup_questions": ["pergunta 1", "pergunta 2"],
  "evidence_used": ["id_evidencia_1", "id_evidencia_2"]
}"""

_TONE_INSTRUCTIONS = {
    "simples": "\nTOM: Use linguagem simples, clara, acessível. Evite juridiquês. Explique termos técnicos quando necessário.",
    "tecnico": "\nTOM: Use linguagem técnica de licitações. Pode referenciar artigos, incisos, acórdãos diretamente. Presuma familiaridade com a legislação.",
    "juridico": "\nTOM: Linguagem jurídica precisa. Pode usar terminologia processual, referenciar precedentes, distinguir entendimentos. O interlocutor é especialista.",
}


def _build_system_prompt(tone: Tone) -> str:
    return _SYSTEM_BASE + _TONE_INSTRUCTIONS.get(tone, _TONE_INSTRUCTIONS["simples"])


def _build_user_prompt(query: str, evidence: List[Evidence]) -> str:
    parts = [f"PERGUNTA DO USUÁRIO: {query}\n"]

    if evidence:
        parts.append("EVIDÊNCIAS INTERNAS DISPONÍVEIS:")
        for i, ev in enumerate(evidence, 1):
            header = f"\n[{i}] ID={ev.id}"
            if ev.title:
                header += f" | {ev.title}"
            if ev.doc_type:
                header += f" | tipo={ev.doc_type}"
            if ev.tribunal:
                header += f" | tribunal={ev.tribunal}"
            parts.append(header)
            parts.append(f"    {ev.snippet}")
        parts.append("")
    else:
        parts.append("EVIDÊNCIAS INTERNAS: Nenhuma encontrada.\n")

    parts.append("Responda em JSON conforme instruído no system prompt.")
    return "\n".join(parts)


def _parse_llm_json(content: str) -> dict:
    """Extrai JSON da resposta do LLM, tolerante a markdown."""
    # Tenta extrair de code block
    cb = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if cb:
        content = cb.group(1)
    else:
        # Tenta encontrar o JSON diretamente
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            content = match.group(0)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"Falha ao parsear JSON do LLM: {content[:200]}")
        return {}


def generate_answer(
    query: str,
    evidence: List[Evidence],
    tone: Tone,
    timeout: int = 45,
) -> dict:
    """
    Chama o LLM para gerar resposta baseada nas evidências.

    Retorna dict com:
      answer, uncertainty, followup_questions, evidence_used, llm_time_ms, llm_model
    """
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY não configurada")
        return {
            "answer": "Serviço de IA indisponível no momento. Tente novamente.",
            "uncertainty": "API key não configurada",
            "followup_questions": [],
            "evidence_used": [],
            "llm_time_ms": 0,
            "llm_model": None,
        }

    system_prompt = _build_system_prompt(tone)
    user_prompt = _build_user_prompt(query, evidence)

    start = time.time()
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 1500,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        content = resp.json()["content"][0]["text"]
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        logger.exception("Erro ao chamar LLM para copilot")
        return {
            "answer": "Erro ao processar sua pergunta. Tente novamente.",
            "uncertainty": str(e),
            "followup_questions": [],
            "evidence_used": [],
            "llm_time_ms": elapsed,
            "llm_model": ANTHROPIC_MODEL,
        }

    elapsed = int((time.time() - start) * 1000)
    parsed = _parse_llm_json(content)

    return {
        "answer": parsed.get("answer", content),
        "uncertainty": parsed.get("uncertainty"),
        "followup_questions": parsed.get("followup_questions", [])[:3],
        "evidence_used": parsed.get("evidence_used", []),
        "llm_time_ms": elapsed,
        "llm_model": ANTHROPIC_MODEL,
    }
