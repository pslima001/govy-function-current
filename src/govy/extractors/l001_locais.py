# src/govy/extractors/l001_locais.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ExtractResultList:
    values: List[str]
    evidence: Optional[str]
    score: int


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
    s = re.sub(r"\s*,\s*", ", ", s)
    return s.strip(" ,;-–—\n\r\t")


def _dedup_key(s: str) -> str:
    s = _norm_spaces(s).lower()
    # remove CEP
    s = re.sub(r"\bcep[:\s]*\d{2}\.?\d{3}[-.]?\d{3}\b", "", s, flags=re.I)
    # remove telefones
    s = re.sub(r"\b(?:\(?\d{2}\)?\s*)?\d{4,5}[-.\s]?\d{4}\b", "", s)
    # remove pontuação
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _has_context(window: str) -> bool:
    w = window.lower()
    return any(g in w for g in GATILHOS)


def _is_negative(window: str) -> bool:
    w = window.lower()
    return any(n in w for n in NEGATIVOS)


def _validate_candidate(cand: str) -> bool:
    c = _norm_spaces(cand)
    low = c.lower()

    # precisa começar com logradouro
    if not re.search(r"^(rua|r\.|avenida|av\.?|rodovia|rod\.?|estrada|travessa|alameda|largo|praça|praca|br)\b", low):
        return False

    # BR precisa ser BR-### ou BR ### (rodovia)
    if low.startswith("br") and not re.search(r"^br[-\s]?\d{2,3}\b", low):
        return False

    # precisa ter número ou s/n ou km
    if not (re.search(r"\b\d{1,5}\b", c) or re.search(r"\bs\s*/?\s*n\b|\bsn\b", low) or "km" in low):
        return False

    # se parece muito cabeçalho institucional, rejeita
    if _is_negative(c) and not any(x in low for x in ["rua", "avenida", "estrada", "rodovia", "travessa", "alameda", "praça", "praca", "br"]):
        return False

    # tamanho mínimo razoável
    return len(c) >= 18


def extract_l001(text: str) -> ExtractResultList:
    """
    L001 — Locais de entrega/recebimento
    Estratégia:
      - procurar “janelas” de contexto com gatilhos (entrega/recebimento)
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
        low = line.lower()
        if any(g in low for g in GATILHOS):
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
            evidences.append(_norm_spaces(window)[:900])

    # dedup
    out: List[str] = []
    seen = set()
    for h in hits:
        k = _dedup_key(h)
        if not k or len(k) < 18:
            continue
        if k in seen:
            continue
        seen.add(k)
        out.append(h)

    # score: baseado em quantos locais encontrados + se teve evidência com gatilho forte
    score = 0
    if out:
        score += 6
        score += min(6, len(out))  # até +6
    if evidences:
        score += 2

    evidence = "\n---\n".join(evidences[:2]) if evidences else None
    return ExtractResultList(values=out, evidence=evidence, score=score)
