# src/govy/extractors/l001_anexo_texto.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class ExtractResultList:
    values: List[str]
    evidence: Optional[str]
    score: int


LOGRADOURO_RE = re.compile(
    r"\b(rua|r\.|avenida|av\.?|rodovia|rod\.?|estrada|travessa|tv\.?|Condominio|Con\.?||alameda|largo|praça|praca)\b",
    re.IGNORECASE,
)
BR_RODOVIA_RE = re.compile(r"\bBR[-\s]?\d{2,3}\b", re.IGNORECASE)
PR_RODOVIA_RE = re.compile(r"\bPR[-\s]?\d{2,3}\b", re.IGNORECASE)

NUM_RE = re.compile(r"\b(\d{1,5}|SN|S/N)\b", re.IGNORECASE)
CEP_RE = re.compile(r"\bCEP[:\s]*\d{2}\.?\d{3}[-.]?\d{3}\b", re.IGNORECASE)
TEL_RE = re.compile(r"\b(\d{8,12})\b")  # telefone “colado” (ex: 4334232577)

NEGATIVE_CONTEXT = [
    "assinatura do contrato", "assinar o contrato", "assinatura da ata",
    "retirada de empenho", "retirada da nota de empenho", "retirar a nota de empenho",
    "retirada do edital", "retirar o edital", "retirada de edital",
    "envio de amostra", "envio de amostras", "entrega de amostra", "entrega de amostras",
    "envio de proposta", "apresentação da proposta", "apresentacao da proposta",
    "proposta comercial", "enviar proposta", "envio da proposta",
    "credenciamento", "chave de acesso", "senha",
    "sessão pública", "sessao publica", "disputa", "lances",
    "esclarecimentos", "impugnação", "impugnacao", "recursos", "contrarrazões", "contrarrazoes",
]

NEGATIVE_INSTITUTIONAL = [
    "cnpj", "fundepar", "comissão de contratação", "comissao de contratacao",
    "e-mail", "email", "ouvidoria",
    "rua dos funcionários", "rua dos funcionarios",
]


def _norm(s: str) -> str:
    s = (s or "").replace("\uFFFD", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*,\s*", ", ", s)
    return s.strip(" \n\r\t,;-–—")


def _dedup_key(s: str) -> str:
    s = _norm(s).lower()
    s = CEP_RE.sub("", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _has_negative_context(window: str) -> bool:
    w = _norm(window).lower()
    return any(k in w for k in NEGATIVE_CONTEXT)


def _is_institutional(window: str) -> bool:
    w = _norm(window).lower()
    return any(k in w for k in NEGATIVE_INSTITUTIONAL)


def _looks_like_address_line(line: str) -> bool:
    s = _norm(line)
    if not s:
        return False
    low = s.lower()

    has_street = LOGRADOURO_RE.search(s) is not None
    has_rodovia = (BR_RODOVIA_RE.search(s) is not None) or (PR_RODOVIA_RE.search(s) is not None)

    if not (has_street or has_rodovia):
        return False
    if not (NUM_RE.search(s) or " km" in low):
        return False
    return True


def _find_best_dense_block(lines: List[str], window: int = 260, stride: int = 40) -> Tuple[int, int, int]:
    best = (0, 0, 0)
    n = len(lines)
    for start in range(0, n, stride):
        end = min(n, start + window)
        chunk = lines[start:end]
        chunk_text = "\n".join(chunk)

        if _is_institutional(chunk_text):
            continue

        hits = sum(1 for ln in chunk if _looks_like_address_line(ln))
        if hits > best[2]:
            best = (start, end, hits)
    return best


def _expand_block(lines: List[str], start: int, end: int) -> Tuple[int, int]:
    n = len(lines)

    s = start
    misses = 0
    while s > 0 and misses < 60:
        s -= 1
        if _looks_like_address_line(lines[s]):
            misses = 0
        else:
            misses += 1

    e = end
    misses = 0
    while e < n and misses < 120:
        if _looks_like_address_line(lines[e]):
            misses = 0
        else:
            misses += 1
        e += 1

    return max(0, s), min(n, e)


def _split_records_by_phone(block_lines: List[str]) -> List[str]:
    """
    Junta várias linhas até encontrar um telefone (8-12 dígitos),
    o que normalmente marca o fim de uma linha/registro tabular.
    """
    records: List[str] = []
    buf: List[str] = []

    for ln in block_lines:
        ln = _norm(ln)
        if not ln:
            continue

        buf.append(ln)

        # fecha registro se aparecer telefone
        if TEL_RE.search(ln):
            records.append(_norm(" ".join(buf)))
            buf = []

    # se sobrou algo, guarda também
    if buf:
        records.append(_norm(" ".join(buf)))

    return records


def _extract_address_from_record(rec: str) -> Optional[str]:
    """
    Extrai o endereço do registro completo, mantendo bairro/cidade se estiverem juntos.
    Remove CEP e telefone do final.
    """
    r = _norm(rec)
    if not r:
        return None

    # remove CEP
    r = CEP_RE.sub("", r)
    r = _norm(r)

    # remove telefone final (se houver)
    m_tel = TEL_RE.search(r)
    if m_tel:
        r = _norm(r[:m_tel.start()])

    # localizar início do logradouro/rodovia
    m = LOGRADOURO_RE.search(r)
    if not m:
        # rodovia
        m2 = BR_RODOVIA_RE.search(r) or PR_RODOVIA_RE.search(r)
        if not m2:
            return None
        start = m2.start()
    else:
        start = m.start()

    addr = _norm(r[start:])

    # precisa ter número/s/n/km
    low = addr.lower()
    if not (NUM_RE.search(addr) or " km" in low):
        return None

    # normaliza SN
    addr = re.sub(r"\bS/N\b", "SN", addr, flags=re.IGNORECASE)
    return _norm(addr)


def extract_l001_many_locations_from_text(text: str) -> ExtractResultList:
    """
    L001-B: lista grande (tabela achatada), sem depender de anexo/códigos.
    - acha bloco denso de endereços
    - junta registros por “telefone”
    - extrai endereço mais completo por registro
    """
    if not text:
        return ExtractResultList(values=[], evidence=None, score=0)

    lines = text.splitlines()

    start, end, hits = _find_best_dense_block(lines)
    if hits < 10:
        return ExtractResultList(values=[], evidence=None, score=0)

    s2, e2 = _expand_block(lines, start, end)
    block_lines = lines[s2:e2]

    # separa em registros
    records = _split_records_by_phone(block_lines)

    found: List[str] = []
    seen = set()

    for rec in records:
        # filtros por contexto negativo/institucional no registro
        if _has_negative_context(rec) or _is_institutional(rec):
            continue

        addr = _extract_address_from_record(rec)
        if not addr:
            continue

        k = _dedup_key(addr)
        if not k or k in seen:
            continue
        seen.add(k)
        found.append(addr)

    score = 0
    if found:
        if len(found) < 20:
            score = 8
        elif len(found) < 100:
            score = 12
        else:
            score = 16 + min(10, len(found) // 200)

    evidence = None
    if found:
        evidence = (
            f"Bloco denso detectado: linhas {s2}–{e2} (hits={hits})\n"
            f"Total extraído: {len(found)}\n"
            "Amostra (20 primeiros):\n" + "\n".join(found[:20])
        )

    return ExtractResultList(values=found, evidence=evidence, score=score)
