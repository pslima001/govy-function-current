# govy/copilot/llm_answer.py
"""
Answer Builder — gera resposta via LLM usando SOMENTE evidência interna.

Fluxo:
1. Monta system prompt com regras da policy
2. Monta user prompt com query + evidências
3. Chama LLM (Anthropic Claude ou OpenAI GPT)
4. Parseia resposta JSON
5. Valida contra policy (sem doutrina, sem externo, sem defesa)

Providers suportados:
- anthropic: Anthropic Claude (api.anthropic.com)
- openai: OpenAI GPT (api.openai.com) — compatível com Azure OpenAI futuro
"""
import json
import logging
import re
import time
from typing import List

import requests

from govy.copilot.contracts import Evidence, Tone
from govy.copilot.config import (
    LLM_PROVIDER,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_MAX_OUTPUT_TOKENS,
    LLM_TIMEOUT_SECONDS,
    LLM_MAX_RETRIES,
    get_active_model,
    get_active_api_key,
)

logger = logging.getLogger(__name__)


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


# ─── Chamadas por provider ───────────────────────────────────────────


def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    """Chama Anthropic Claude. Retorna conteúdo texto ou levanta exceção."""
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
        timeout=LLM_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]


def _call_openai(system_prompt: str, user_prompt: str) -> str:
    """Chama OpenAI GPT. Retorna conteúdo texto ou levanta exceção."""
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "temperature": OPENAI_TEMPERATURE,
            "max_tokens": OPENAI_MAX_OUTPUT_TOKENS,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=LLM_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _call_llm_with_retry(system_prompt: str, user_prompt: str) -> str:
    """Chama o LLM ativo com retry controlado."""
    call_fn = _call_openai if LLM_PROVIDER == "openai" else _call_anthropic
    last_error = None

    for attempt in range(1, LLM_MAX_RETRIES + 1):
        try:
            return call_fn(system_prompt, user_prompt)
        except requests.exceptions.Timeout:
            last_error = f"Timeout ({LLM_TIMEOUT_SECONDS}s) na tentativa {attempt}"
            logger.warning(f"copilot LLM: {last_error}")
        except requests.exceptions.HTTPError as e:
            # Não fazer retry em erros 4xx (auth, bad request)
            if e.response is not None and 400 <= e.response.status_code < 500:
                raise
            last_error = f"HTTP {e.response.status_code if e.response else '?'} na tentativa {attempt}"
            logger.warning(f"copilot LLM: {last_error}")
        except Exception:
            raise

    raise RuntimeError(last_error or "LLM call failed after retries")


# ─── Função pública ──────────────────────────────────────────────────


def generate_answer(
    query: str,
    evidence: List[Evidence],
    tone: Tone,
    request_id: str = "",
    history_context: str = None,
) -> dict:
    """
    Chama o LLM para gerar resposta baseada nas evidências.

    Retorna dict com:
      answer, uncertainty, followup_questions, evidence_used,
      llm_time_ms, llm_model, llm_provider
    """
    api_key = get_active_api_key()
    model = get_active_model()

    if not api_key:
        logger.error(f"[{request_id}] API key do provider '{LLM_PROVIDER}' não configurada")
        return {
            "answer": "Serviço de IA indisponível no momento. Tente novamente.",
            "uncertainty": "API key não configurada",
            "followup_questions": [],
            "evidence_used": [],
            "llm_time_ms": 0,
            "llm_model": None,
            "llm_provider": LLM_PROVIDER,
            "llm_error": True,
        }

    system_prompt = _build_system_prompt(tone)
    user_prompt = _build_user_prompt(query, evidence)

    # Injetar histórico de conversa antes da pergunta atual
    if history_context:
        user_prompt = history_context + "\n" + user_prompt

    start = time.time()
    try:
        content = _call_llm_with_retry(system_prompt, user_prompt)
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        logger.exception(f"[{request_id}] Erro ao chamar LLM ({LLM_PROVIDER}/{model})")
        return {
            "answer": "Erro ao processar sua pergunta. Tente novamente.",
            "uncertainty": str(e),
            "followup_questions": [],
            "evidence_used": [],
            "llm_time_ms": elapsed,
            "llm_model": model,
            "llm_provider": LLM_PROVIDER,
            "llm_error": True,
        }

    elapsed = int((time.time() - start) * 1000)
    parsed = _parse_llm_json(content)

    return {
        "answer": parsed.get("answer", content),
        "uncertainty": parsed.get("uncertainty"),
        "followup_questions": parsed.get("followup_questions", [])[:3],
        "evidence_used": parsed.get("evidence_used", []),
        "llm_time_ms": elapsed,
        "llm_model": model,
        "llm_provider": LLM_PROVIDER,
        "llm_error": False,
    }
