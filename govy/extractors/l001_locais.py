# govy/extractors/l001_locais.py
"""
L001 - Extrator de Locais de Entrega via Texto
VERSAO 2.0 - Retorna TOP 3 candidatos distintos para avaliacao por LLMs
Ultima atualizacao: 19/01/2026
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class ExtractResultList:
    values: List[str]
    evidence: Optional[str]
    score: int

@dataclass
class CandidateResult:
    value: str
    score: int
    context: str
    evidence: str

def _normalizar_texto(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))

def _limpar_encoding(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def _norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

GATILHOS = [
    "local de entrega", "locais de entrega", "endereco de entrega",
    "enderecos de entrega", "local de recebimento", "locais de recebimento",
    "recebimento", "entrega", "entregar", "fornecimento", "ponto de entrega",
]

TERMOS_NEGATIVOS = [
    "prefeitura", "camara", "cnpj", "telefone", "tel.", "fax", "e-mail",
    "email", "site", "www.", "http", "cep:", "inscricao", "secretaria municipal",
]

_GATILHOS_NORM = [_normalizar_texto(g) for g in GATILHOS]
_NEGATIVOS_NORM = [_normalizar_texto(n) for n in TERMOS_NEGATIVOS]

CANDIDATO_RE = re.compile(
    r"((?:rua|avenida|av\.|travessa|alameda|rodovia|estrada|praca|largo|"
    r"br[\s\-]?\d+|sc[\s\-]?\d+|rs[\s\-]?\d+|mg[\s\-]?\d+|sp[\s\-]?\d+|pr[\s\-]?\d+)"
    r"[^,\n]{5,120}(?:,\s*n[\.o]?\s*\d+|\d+|s\/n|sn|km\s*\d+)?)",
    re.IGNORECASE
)

def _is_negative(window: str) -> bool:
    low = _normalizar_texto(window)
    count = sum(1 for n in _NEGATIVOS_NORM if n and n in low)
    return count >= 2

def _has_context(window: str) -> bool:
    low = _normalizar_texto(window)
    return any(g and g in low for g in _GATILHOS_NORM)

def _validate_candidate(c: str) -> bool:
    low = _normalizar_texto(c)
    if any(n and n in low for n in _NEGATIVOS_NORM):
        return False
    if not re.search(r"(\b\d{1,6}\b|\bkm\b|\bs\/n\b|\bsn\b)", low):
        return False
    if len(c) < 15:
        return False
    return True

def _calcular_similaridade(texto1: str, texto2: str) -> float:
    norm1 = set(_normalizar_texto(texto1).split())
    norm2 = set(_normalizar_texto(texto2).split())
    if not norm1 or not norm2:
        return 0.0
    return len(norm1 & norm2) / len(norm1 | norm2)

def extract_l001_multi(text: str, max_candidatos: int = 3) -> List[CandidateResult]:
    if not text:
        return []
    text = _limpar_encoding(text)
    lines = text.splitlines()
    todos_candidatos = []
    for i, line in enumerate(lines):
        if any(g and g in _normalizar_texto(line) for g in _GATILHOS_NORM):
            ini = max(0, i - 8)
            fim = min(len(lines), i + 12)
            window = "\n".join(lines[ini:fim])
            if _is_negative(window) and not _has_context(window):
                continue
            for match in CANDIDATO_RE.finditer(window):
                cand = _norm_spaces(match.group(0))
                if _validate_candidate(cand):
                    score = 5 + (3 if "entrega" in _normalizar_texto(window) else 0)
                    todos_candidatos.append(CandidateResult(
                        value=cand, score=score,
                        context=_norm_spaces(window[:300]),
                        evidence=_norm_spaces(window[:150])
                    ))
    todos_candidatos.sort(key=lambda x: x.score, reverse=True)
    selecionados = []
    for c in todos_candidatos:
        eh_similar = any(_calcular_similaridade(c.value, s.value) >= 0.75 for s in selecionados)
        if not eh_similar:
            selecionados.append(c)
        if len(selecionados) >= max_candidatos:
            break
    return selecionados

def extract_l001(text: str) -> ExtractResultList:
    if not text:
        return ExtractResultList(values=[], evidence=None, score=0)
    text = _limpar_encoding(text)
    lines = text.splitlines()
    hits = []
    evidences = []
    for i, line in enumerate(lines):
        if any(g and g in _normalizar_texto(line) for g in _GATILHOS_NORM):
            ini = max(0, i - 8)
            fim = min(len(lines), i + 12)
            window = "\n".join(lines[ini:fim])
            if _is_negative(window) and not _has_context(window):
                continue
            for match in CANDIDATO_RE.finditer(window):
                cand = _norm_spaces(match.group(0))
                if _validate_candidate(cand):
                    hits.append(cand)
            if window and not evidences:
                evidences.append(window[:800])
    seen = set()
    unique = []
    for h in hits:
        key = _normalizar_texto(h)
        if key not in seen:
            seen.add(key)
            unique.append(h)
    if not unique:
        return ExtractResultList(values=[], evidence=None, score=0)
    score = 5 + min(10, len(unique) * 2)
    evidence = evidences[0] if evidences else None
    return ExtractResultList(values=unique, evidence=evidence, score=int(score))
