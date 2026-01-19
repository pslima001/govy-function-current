import os
import json
import logging
import time
import requests
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

@dataclass
class LLMResponse:
    provider: str
    escolha: int
    valor_normalizado: Optional[str]
    justificativa: str
    confianca: float
    erro: Optional[str] = None
    tempo_ms: int = 0

@dataclass
class ConsensusResult:
    candidato_vencedor: int
    valor_final: str
    votos: Dict[str, int]
    confianca_media: float
    respostas: List[LLMResponse] = field(default_factory=list)
    justificativa_consolidada: str = ""

DESCRICOES_PARAMETROS = {
    "e001": "Prazo de Entrega: tempo para entrega dos produtos/servicos apos assinatura do contrato",
    "pg001": "Prazo de Pagamento: tempo para pagamento apos recebimento e atesto da nota fiscal",
    "o001": "Objeto da Licitacao: descricao resumida do que esta sendo licitado",
    "l001": "Local de Entrega: endereco(s) onde os produtos devem ser entregues",
}

def obter_api_keys() -> Dict[str, str]:
    return {
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", ""),
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", ""),
        "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY", ""),
        "XAI_API_KEY": os.environ.get("XAI_API_KEY", ""),
        "GROQ_API_KEY": os.environ.get("GROQ_API_KEY", ""),
    }

def formatar_candidatos(candidatos: List[dict]) -> str:
    partes = []
    for i, c in enumerate(candidatos, 1):
        valor = c.get('value', 'N/A')
        score = c.get('score', 0)
        contexto = c.get('context') or c.get('evidence') or 'Sem contexto'
        if len(contexto) > 500:
            contexto = contexto[:500] + "..."
        partes.append(f"Candidato {i}: Valor={valor}, Score={score}, Contexto={contexto}")
    return "\n".join(partes)

def _parse_json_response(content: str) -> dict:
    import re
    json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
    if json_match:
        content = json_match.group(0)
    try:
        return json.loads(content)
    except:
        return {}

def _criar_prompt(parametro: str, candidatos: List[dict]) -> str:
    descricao = DESCRICOES_PARAMETROS.get(parametro, f"Parametro {parametro}")
    candidatos_fmt = formatar_candidatos(candidatos)
    return f'''Voce e um especialista em licitacoes. Analise os candidatos para "{parametro}".

PARAMETRO: {descricao}

CANDIDATOS:
{candidatos_fmt}

Escolha o MELHOR candidato (1-{len(candidatos)}) ou 0 se nenhum for adequado.
Responda APENAS com JSON: {{"escolha": N, "valor_normalizado": "valor", "justificativa": "motivo", "confianca": 0.0-1.0}}'''

def chamar_openai(prompt: str, api_key: str) -> LLMResponse:
    start = time.time()
    try:
        response = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 500},
            timeout=30)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        r = _parse_json_response(content)
        return LLMResponse(provider="openai", escolha=r.get("escolha", 0), valor_normalizado=r.get("valor_normalizado"),
            justificativa=r.get("justificativa", ""), confianca=r.get("confianca", 0.5), tempo_ms=int((time.time() - start) * 1000))
    except Exception as e:
        return LLMResponse(provider="openai", escolha=0, valor_normalizado=None, justificativa="", confianca=0.0, erro=str(e), tempo_ms=int((time.time() - start) * 1000))

def chamar_anthropic(prompt: str, api_key: str) -> LLMResponse:
    start = time.time()
    try:
        response = requests.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"},
            json={"model": "claude-3-5-haiku-20241022", "max_tokens": 500, "messages": [{"role": "user", "content": prompt}]},
            timeout=30)
        response.raise_for_status()
        content = response.json()["content"][0]["text"]
        r = _parse_json_response(content)
        return LLMResponse(provider="anthropic", escolha=r.get("escolha", 0), valor_normalizado=r.get("valor_normalizado"),
            justificativa=r.get("justificativa", ""), confianca=r.get("confianca", 0.5), tempo_ms=int((time.time() - start) * 1000))
    except Exception as e:
        return LLMResponse(provider="anthropic", escolha=0, valor_normalizado=None, justificativa="", confianca=0.0, erro=str(e), tempo_ms=int((time.time() - start) * 1000))

def chamar_google(prompt: str, api_key: str) -> LLMResponse:
    start = time.time()
    try:
        response = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}",
            headers={"Content-Type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500}},
            timeout=30)
        response.raise_for_status()
        content = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        r = _parse_json_response(content)
        return LLMResponse(provider="google", escolha=r.get("escolha", 0), valor_normalizado=r.get("valor_normalizado"),
            justificativa=r.get("justificativa", ""), confianca=r.get("confianca", 0.5), tempo_ms=int((time.time() - start) * 1000))
    except Exception as e:
        return LLMResponse(provider="google", escolha=0, valor_normalizado=None, justificativa="", confianca=0.0, erro=str(e), tempo_ms=int((time.time() - start) * 1000))

def chamar_xai(prompt: str, api_key: str) -> LLMResponse:
    start = time.time()
    try:
        response = requests.post("https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "grok-2-latest", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 500},
            timeout=30)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        r = _parse_json_response(content)
        return LLMResponse(provider="xai", escolha=r.get("escolha", 0), valor_normalizado=r.get("valor_normalizado"),
            justificativa=r.get("justificativa", ""), confianca=r.get("confianca", 0.5), tempo_ms=int((time.time() - start) * 1000))
    except Exception as e:
        return LLMResponse(provider="xai", escolha=0, valor_normalizado=None, justificativa="", confianca=0.0, erro=str(e), tempo_ms=int((time.time() - start) * 1000))

def chamar_groq(prompt: str, api_key: str) -> LLMResponse:
    start = time.time()
    try:
        response = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 500},
            timeout=30)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        r = _parse_json_response(content)
        return LLMResponse(provider="groq", escolha=r.get("escolha", 0), valor_normalizado=r.get("valor_normalizado"),
            justificativa=r.get("justificativa", ""), confianca=r.get("confianca", 0.5), tempo_ms=int((time.time() - start) * 1000))
    except Exception as e:
        return LLMResponse(provider="groq", escolha=0, valor_normalizado=None, justificativa="", confianca=0.0, erro=str(e), tempo_ms=int((time.time() - start) * 1000))

def consultar_llms(parametro: str, candidatos: List[dict], api_keys: Dict[str, str], providers: Optional[List[str]] = None) -> ConsensusResult:
    if not candidatos:
        return ConsensusResult(candidato_vencedor=0, valor_final="", votos={}, confianca_media=0.0, justificativa_consolidada="Nenhum candidato")
    provider_funcs = {"openai": (chamar_openai, api_keys.get("OPENAI_API_KEY")), "anthropic": (chamar_anthropic, api_keys.get("ANTHROPIC_API_KEY")),
        "google": (chamar_google, api_keys.get("GOOGLE_API_KEY")), "xai": (chamar_xai, api_keys.get("XAI_API_KEY")), "groq": (chamar_groq, api_keys.get("GROQ_API_KEY"))}
    if providers:
        providers_ativos = [(p, provider_funcs[p]) for p in providers if p in provider_funcs and provider_funcs[p][1]]
    else:
        providers_ativos = [(p, v) for p, v in provider_funcs.items() if v[1]]
    if not providers_ativos:
        return ConsensusResult(candidato_vencedor=0, valor_final="", votos={}, confianca_media=0.0, justificativa_consolidada="Nenhuma API configurada")
    prompt = _criar_prompt(parametro, candidatos)
    respostas = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(func, prompt, key): name for name, (func, key) in providers_ativos}
        for future in as_completed(futures):
            try:
                respostas.append(future.result())
            except Exception as e:
                logger.error(f"Erro: {e}")
    votos, contagem, confiancas = {}, {}, []
    for r in respostas:
        if not r.erro:
            votos[r.provider] = r.escolha
            contagem[r.escolha] = contagem.get(r.escolha, 0) + 1
            confiancas.append(r.confianca)
    if not contagem:
        return ConsensusResult(candidato_vencedor=0, valor_final="", votos=votos, confianca_media=0.0, respostas=respostas, justificativa_consolidada="Sem respostas validas")
    vencedor = max(contagem, key=contagem.get)
    valor_final = candidatos[vencedor - 1].get('value', '') if 0 < vencedor <= len(candidatos) else ""
    return ConsensusResult(candidato_vencedor=vencedor, valor_final=valor_final, votos=votos, confianca_media=sum(confiancas)/len(confiancas) if confiancas else 0.0, respostas=respostas, justificativa_consolidada="; ".join([f"{r.provider}: {r.justificativa}" for r in respostas if r.justificativa]))
