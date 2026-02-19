from __future__ import annotations

import json
import logging
import os
import re
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from govy.doctrine.chunker import DoctrineChunk

logger = logging.getLogger(__name__)

# Stub mode: True quando OPENAI_API_KEY ausente (seguro para CI)
STUB_MODE = not os.getenv("OPENAI_API_KEY")

# Catálogo global v1 (fixo)
ARGUMENT_ROLE_V1 = {
    "DEFINICAO",
    "FINALIDADE",
    "DISTINCAO",
    "LIMITE",
    "RISCO",
    "CRITERIO",
    "PASSO_A_PASSO",
}


@dataclass(frozen=True)
class DoctrineSemanticChunk:
    id: str
    doc_type: str
    procedural_stage: str
    tema_principal: str
    pergunta_ancora: str
    tese_neutra: str
    explicacao_conceitual: str
    limites_e_cuidados: List[str]
    tags_semanticas: List[str]
    nivel_abstracao: str
    coverage_status: str
    argument_role: Optional[str]
    review_status: str
    scope_assertions: Dict[str, bool]
    compatibility_keys: List[str]
    red_flags: List[str]
    source_refs: Dict[str, str]


_FORBIDDEN_DOCTRINE_MENTIONS = [
    (r"\bmajorit[aá]ri[ao]\b", "CONSENSO_REMOVIDO"),
    (r"\bpac[ií]fic[ao]\b", "CONSENSO_REMOVIDO"),
    (r"\bconsolidado\b", "CONSENSO_REMOVIDO"),
]

_FORBIDDEN_TRIBUNAL_MENTIONS = [
    (r"\btcu\b", "MENCAO_TRIBUNAL_REMOVIDA"),
    (r"\bstj\b", "MENCAO_TRIBUNAL_REMOVIDA"),
    (r"\bstf\b", "MENCAO_TRIBUNAL_REMOVIDA"),
    (r"\btj[a-z]{1,3}\b", "MENCAO_TRIBUNAL_REMOVIDA"),
    (r"\bac[oó]rd[aã]o\b", "MENCAO_TRIBUNAL_REMOVIDA"),
    (r"\bementa\b", "MENCAO_TRIBUNAL_REMOVIDA"),
    (r"\brelator\b", "MENCAO_TRIBUNAL_REMOVIDA"),
    (r"\bdesembargador\b|\bju[ií]z\b|\bministro\b", "MENCAO_TRIBUNAL_REMOVIDA"),
]

_FORBIDDEN_AUTHORSHIP = [
    (r"\bautor\b", "AUTORIA_REMOVIDA"),
    (r"\bobra\b", "AUTORIA_REMOVIDA"),
    (r"\bjurista\b", "AUTORIA_REMOVIDA"),
    (r"\bed i[cç][aã]o\b", "AUTORIA_REMOVIDA"),
    (r"\bed itora\b", "AUTORIA_REMOVIDA"),
]


def _sanitize_text(s: str) -> tuple[str, List[str]]:
    red_flags: List[str] = []
    out = s or ""
    for pat, flag in _FORBIDDEN_DOCTRINE_MENTIONS + _FORBIDDEN_TRIBUNAL_MENTIONS + _FORBIDDEN_AUTHORSHIP:
        if re.search(pat, out, flags=re.IGNORECASE):
            red_flags.append(flag)
            out = re.sub(pat, "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out, sorted(set(red_flags))


def _looks_neutral(s: str) -> bool:
    s = (s or "").strip().lower()
    return (
        s.startswith("há visões doutrinárias") or s.startswith("parte da doutrina") or s.startswith("alguns advogados")
    )


def _default_scope_assertions() -> Dict[str, bool]:
    return {
        "decide_caso_concreto": False,
        "substitui_jurisprudencia": False,
        "afirma_consenso": False,
        "revela_autoria": False,
    }


def _openai_api_key() -> Optional[str]:
    return os.getenv("OPENAI_API_KEY")


def _openai_model() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def _call_openai_json(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    api_key = _openai_api_key()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada")
    url = "https://api.openai.com/v1/chat/completions"
    payload = {
        "model": _openai_model(),
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode("utf-8")
    out = json.loads(raw)
    content = out["choices"][0]["message"]["content"]
    return json.loads(content)


def _build_system_prompt() -> str:
    return """Você é um extrator de CHUNKS SEMÂNTICOS de DOUTRINA (com autoria) para a plataforma GOVY.

REGRAS INEGOCIÁVEIS (DOUTRINA COM AUTORIA):
- Nunca revelar autor, obra, jurista, editora, página, capítulo. (sigilo)
- Nunca usar nem citar jurisprudência, acórdãos, tribunais, juízes, desembargadores.
- Nunca afirmar consenso ("majoritário", "pacífico", "consolidado").
- Nunca decidir caso concreto, nunca recomendar conduta.
- Nunca inventar nem inferir: se o texto não sustentar, marque coverage_status="INCERTO".

LINGUAGEM OBRIGATÓRIA:
- tese_neutra deve começar com: "Há visões doutrinárias que..." ou "Parte da doutrina entende que..." ou "Alguns advogados descrevem..."

ARGUMENT_ROLE (catálogo v1):
- Escolha UM dentre: DEFINICAO, FINALIDADE, DISTINCAO, LIMITE, RISCO, CRITERIO, PASSO_A_PASSO
- Se coverage_status="INCERTO", retorne argument_role como null.

SAÍDA:
- Retorne APENAS JSON válido, sem markdown.""".strip()


def _build_user_prompt(
    *,
    procedural_stage: str,
    tema_principal: str,
    source_sha: str,
    raw_chunk_id: str,
    raw_content_hash: str,
    raw_text: str,
) -> str:
    roles = ", ".join(sorted(ARGUMENT_ROLE_V1))
    return f"""Extraia de forma fiel (sem inventar) 1 a 4 CHUNKS SEMÂNTICOS de DOUTRINA para o texto abaixo.
Cada chunk deve ser UMA ideia jurídica e responder UMA pergunta âncora.

Campos obrigatórios por chunk:
- tema_principal: "{tema_principal}"
- procedural_stage: "{procedural_stage}"
- pergunta_ancora (curta)
- tese_neutra (1-3 frases, linguagem obrigatória)
- explicacao_conceitual (1 parágrafo)
- limites_e_cuidados (2-6 itens)
- tags_semanticas (3-12 termos)
- nivel_abstracao: INTRODUTORIO|INTERMEDIARIO|AVANCADO
- coverage_status: COMPLETO|PARCIAL|INCERTO
- argument_role: um dentre [{roles}] ou null se coverage_status="INCERTO"

Importante:
- NÃO citar tribunais/jurisprudência.
- NÃO citar autor/obra.
- NÃO usar termos de consenso.
- Se o texto não sustentar: coverage_status=INCERTO e argument_role=null.

Retorne JSON no formato:
{{"chunks": [{{"tema_principal": "...", "procedural_stage": "...", "pergunta_ancora": "...", "tese_neutra": "...", "explicacao_conceitual": "...", "limites_e_cuidados": ["...", "..."], "tags_semanticas": ["...", "...", "..."], "nivel_abstracao": "INTRODUTORIO", "coverage_status": "COMPLETO", "argument_role": "DEFINICAO"}}]}}

METADADOS INTERNOS (não mencionar em nenhum campo de texto):
- source_sha: {source_sha}
- raw_chunk_id: {raw_chunk_id}
- raw_content_hash: {raw_content_hash}

TEXTO:
\"\"\"{raw_text}\"\"\"""".strip()


def _coerce_argument_role(role: Any) -> Optional[str]:
    if role is None:
        return None
    r = str(role).strip().upper()
    return r if r in ARGUMENT_ROLE_V1 else None


def extract_semantic_chunks_for_raw_chunks(
    *,
    raw_chunks: List[DoctrineChunk],
    procedural_stage: str,
    tema_principal: str,
    source_sha: str,
    review_status_default: str = "PENDING",
) -> List[Dict[str, Any]]:
    if not raw_chunks:
        return []
    if not _openai_api_key():
        logger.warning("OPENAI_API_KEY ausente: semantic_chunks será vazio.")
        return []
    system_prompt = _build_system_prompt()
    out: List[Dict[str, Any]] = []
    for ch in raw_chunks:
        user_prompt = _build_user_prompt(
            procedural_stage=procedural_stage,
            tema_principal=tema_principal,
            source_sha=source_sha,
            raw_chunk_id=ch.chunk_id,
            raw_content_hash=ch.content_hash,
            raw_text=ch.content_raw,
        )
        try:
            raw_json = _call_openai_json(system_prompt, user_prompt)
        except Exception as e:
            logger.error(f"Falha OpenAI no raw_chunk={ch.chunk_id}: {e}")
            continue
        items = raw_json.get("chunks") or []
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            pergunta = (item.get("pergunta_ancora") or "").strip()
            tese = (item.get("tese_neutra") or "").strip()
            explic = (item.get("explicacao_conceitual") or "").strip()
            limites = item.get("limites_e_cuidados") or []
            tags = item.get("tags_semanticas") or []
            nivel = (item.get("nivel_abstracao") or "INTRODUTORIO").strip().upper()
            coverage = (item.get("coverage_status") or "INCERTO").strip().upper()
            arg_role = _coerce_argument_role(item.get("argument_role"))
            pergunta, rf1 = _sanitize_text(pergunta)
            tese, rf2 = _sanitize_text(tese)
            explic, rf3 = _sanitize_text(explic)
            red_flags = sorted(set(rf1 + rf2 + rf3))
            if not _looks_neutral(tese):
                red_flags.append("LINGUAGEM_NAO_NEUTRA")
                coverage = "INCERTO"
            if not pergunta or not tese or not explic:
                coverage = "INCERTO"
            if not isinstance(limites, list) or len(limites) < 2:
                coverage = "INCERTO"
                limites = [item for item in limites] if isinstance(limites, list) else []
            if not isinstance(tags, list) or len(tags) < 3:
                coverage = "INCERTO"
                tags = [t for t in tags] if isinstance(tags, list) else []
            if nivel not in ("INTRODUTORIO", "INTERMEDIARIO", "AVANCADO"):
                nivel = "INTRODUTORIO"
            if coverage not in ("COMPLETO", "PARCIAL", "INCERTO"):
                coverage = "INCERTO"
            if coverage == "INCERTO":
                arg_role = None
            semantic_id = f"{ch.chunk_id}::{i}"
            sem = DoctrineSemanticChunk(
                id=f"doutrina_sem::{source_sha}::{semantic_id}",
                doc_type="doutrina",
                procedural_stage=procedural_stage,
                tema_principal=tema_principal,
                pergunta_ancora=pergunta,
                tese_neutra=tese,
                explicacao_conceitual=explic,
                limites_e_cuidados=[str(x).strip() for x in limites if str(x).strip()],
                tags_semanticas=[str(x).strip() for x in tags if str(x).strip()],
                nivel_abstracao=nivel,
                coverage_status=coverage,
                argument_role=arg_role,
                review_status=review_status_default,
                scope_assertions=_default_scope_assertions(),
                compatibility_keys=[f"{procedural_stage}:{tema_principal}"],
                red_flags=sorted(set(red_flags)),
                source_refs={
                    "source_sha": source_sha,
                    "raw_chunk_id": ch.chunk_id,
                    "raw_content_hash": ch.content_hash,
                },
            )
            out.append(sem.__dict__)
    return out
