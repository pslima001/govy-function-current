# src/govy/extractors/l001_locais.py
from __future__ import annotations

import re
import unicodedata

from govy.extractors.config.loader import get_extractor_config
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ExtractResultList:
    values: List[str]
    evidence: Optional[str]
    score: int


def _norm(s: str) -> str:
    s = s.lower()
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))


# gatilhos de contexto (entrega/recebimento)
GATILHOS = [
    "local de entrega", "locais de entrega", "endereço de entrega", "endereços de entrega",
    "local de recebimento", "locais de recebimento", "recebimento", "entrega", "entregar",
    "fornecimento", "ponto de entrega", "ponto a ponto"
]

# negativos para evitar pegar cabeçalho/rodapé/contato institucional
NEGATIVOS = [
    "prefeitura", "câmara", "camara", "cnpj", "telefone", "tel.", "fax",
    "e-mail", "email", "www", ".gov", "ouvidoria", "secretaria", "gabinete"
]

# --- Config via patterns.json (com fallback) ---
_cfg = get_extractor_config("l001_locais")
if isinstance(_cfg, dict):
    GATILHOS = _cfg.get("gatilhos", GATILHOS)
    NEGATIVOS = _cfg.get("negativos", NEGATIVOS)

# Pré-normaliza listas para casar texto com/sem acento
GATILHOS_N = [_norm(g) for g in GATILHOS]
NEGATIVOS_N = [_norm(n) for n in NEGATIVOS]

# padrão de início de logradouro
LOGRADOURO_RE = re.compile(
    r"\b(rua|r\.|avenida|av\.?|rodovia|rod\.?|estrada|travessa|alameda|largo|praça|praca|br)\b",
    re.IGNORECASE
)

# captura um candidato relativamente longo após o logradouro
CAND_RE = re.compile(
    r"\b(?:Rua|R\.|Avenida|Av\.?|Rodovia|Rod\.?|Estrada|Travessa|Alameda|Largo|Praça|Praca|BR)"
    r"\s+[^\n;]{10,220}",
    re.IGNORECASE
)


def _norm_spaces(s: str) -> str:
    s = (s or "").replace("\uFFFD", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _has_context(window: str) -> bool:
    w = _norm(window)
    return any(g and g in w for g in GATILHOS_N)


def _is_negative(window: str) -> bool:
    w = _norm(window)
    return any(n and n in w for n in NEGATIVOS_N)


def _validate_candidate(cand: str) -> bool:
    c = _norm_spaces(cand)
    low = c.lower()

    # precisa começar com logradouro
    if not re.search(r"^(rua|r\.|avenida|av\.?|rodovia|rod\.?|estrada|travessa|alameda|largo|praça|praca|br)\b", low):
        return False

    # heurísticas mínimas: número ou km ou s/n
    if not re.search(r"(\b\d{1,6}\b|\bkm\b|\bs\/n\b|\bsn\b)", low):
        return False

    # evita candidatos curtos demais
    if len(c) < 15:
        return False

    return True


def extract_l001(text: str) -> ExtractResultList:
    """
    L001 — Locais de entrega/recebimento
    Estratégia:
      - procurar "janelas" de contexto com gatilhos (entrega/recebimento)
      - dentro dessas janelas, extrair candidatos de endereço por regex
      - validar estrutura mínima (logradouro + número/s/n/km)
      - deduplicar

    Observação: como Textract atual não tem tabelas (0 cells), aqui usamos só texto.
    """
    if not text:
        return ExtractResultList(values=[], evidence=None, score=0)

    lines = text.splitlines()
    hits: List[str] = []
    evidences: List[str] = []

    # varre linhas e cria janelas de 8 linhas antes/depois quando achar gatilho
    for i, line in enumerate(lines):
        if any(g and g in _norm(line) for g in GATILHOS_N):
            ini = max(0, i - 8)
            fim = min(len(lines), i + 12)
            window = "\n".join(lines[ini:fim])

            # evita janelas claramente de cabeçalho
            if _is_negative(window) and not _has_context(window):
                continue

            # busca endereços na janela
            for m in CAND_RE.finditer(window):
                cand = _norm_spaces(m.group(0))
                if _validate_candidate(cand):
                    hits.append(cand)

            # guarda evidência (primeira janela já ajuda)
            if window and not evidences:
                evidences.append(window[:800])

    # dedup preservando ordem
    seen = set()
    uniq: List[str] = []
    for h in hits:
        k = _norm(h)
        if k not in seen:
            seen.add(k)
            uniq.append(h)

    if not uniq:
        return ExtractResultList(values=[], evidence=None, score=0)

    score = 5 + min(10, len(uniq) * 2)
    evidence = evidences[0] if evidences else None
    return ExtractResultList(values=uniq, evidence=evidence, score=int(score))
