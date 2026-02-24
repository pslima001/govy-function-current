# govy/legal/legal_chunker.py
"""
Chunker estrutural para legislacao brasileira.

Granularidade: 1 chunk = 1 artigo (com paragrafos, incisos, alineas).
Artigos >5000 chars: sub-chunk por paragrafo.
Texto antes de Art. 1: provision 'preambulo'.
Fallback: se <3 artigos detectados, usa chunker por paragrafos.

Detecta: Art. Xo, Par. Xo, Paragrafo unico, I - (incisos), a) (alineas),
         TITULO, CAPITULO, SECAO, ANEXO.

provision_key:  art_1, art_1_par_1, art_1_par_1_inc_II, art_1_par_1_inc_II_ali_a
citation_short: "IN 62/2021, Art. 5, Par. 1o"
hierarchy_path: ['Capitulo II', 'Secao I', 'Art. 5', 'Par. 1o']
"""
from __future__ import annotations

import re
import hashlib
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from govy.legal.models import LegalProvision, LegalChunk

logger = logging.getLogger(__name__)

# ── Constantes ───────────────────────────────────────────────────────────────

MAX_CHUNK_CHARS = 5000
FALLBACK_MAX_CHARS = 5000
FALLBACK_MIN_CHARS = 900
MIN_ARTICLES_FOR_STRUCTURAL = 3

# ── Regex patterns ───────────────────────────────────────────────────────────

# Art. 1o, Art. 1º, Art. 10, Art. 100 — início de linha ou após quebra
RE_ARTIGO = re.compile(
    r"^[\s]*Art\.?\s*(\d+)[°ºo]?[\s.\-–—]",
    re.MULTILINE | re.IGNORECASE,
)

# § 1o, § 1º, Par. 1o, Parágrafo único
RE_PARAGRAFO = re.compile(
    r"^[\s]*(?:§\s*(\d+)[°ºo]?|Par(?:ágrafo|agrafo)?\.?\s*(\d+)[°ºo]?|Par[aá]grafo\s+[uú]nico)",
    re.MULTILINE | re.IGNORECASE,
)

# I -, II -, III -, IV -, ...  ou  I – , I — (travessão)
RE_INCISO = re.compile(
    r"^[\s]*(X{0,3}(?:IX|IV|V?I{0,3}))\s*[-–—]",
    re.MULTILINE,
)

# a), b), c) ...
RE_ALINEA = re.compile(
    r"^[\s]*([a-z])\)\s",
    re.MULTILINE,
)

# TITULO I, TITULO II, ...
RE_TITULO = re.compile(
    r"^[\s]*T[IÍ]TULO\s+(X{0,3}(?:IX|IV|V?I{0,3}|[0-9]+))\b",
    re.MULTILINE | re.IGNORECASE,
)

# CAPITULO I, CAPÍTULO II, ...
RE_CAPITULO = re.compile(
    r"^[\s]*CAP[IÍ]TULO\s+(X{0,3}(?:IX|IV|V?I{0,3}|[0-9]+))\b",
    re.MULTILINE | re.IGNORECASE,
)

# Seção I, SEÇÃO II, ...
RE_SECAO = re.compile(
    r"^[\s]*SE[CÇ][AÃ]O\s+(X{0,3}(?:IX|IV|V?I{0,3}|[0-9]+))\b",
    re.MULTILINE | re.IGNORECASE,
)

# ANEXO I, ANEXO II, ANEXO (sem número)
RE_ANEXO = re.compile(
    r"^[\s]*ANEXO\s*(X{0,3}(?:IX|IV|V?I{0,3}|[0-9]+))?\b",
    re.MULTILINE | re.IGNORECASE,
)


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _roman_to_label(roman: str) -> str:
    """Converte match de romano/numero para label padrao."""
    return roman.strip().upper()


# ── Structural splitting ─────────────────────────────────────────────────────

@dataclass
class _RawArticle:
    """Artigo bruto antes de gerar provisions/chunks."""
    art_num: int
    label: str              # 'Art. 5o'
    text: str               # texto completo do artigo (com pars, incisos, etc.)
    start_pos: int
    hierarchy_context: List[str] = field(default_factory=list)


def _find_hierarchy_context(text: str, pos: int) -> List[str]:
    """Encontra TITULO/CAPITULO/SECAO mais recentes antes de pos."""
    context = []

    for pat, prefix in [
        (RE_TITULO, "Titulo"),
        (RE_CAPITULO, "Capitulo"),
        (RE_SECAO, "Secao"),
    ]:
        last_match = None
        for m in pat.finditer(text):
            if m.start() < pos:
                last_match = m
            else:
                break
        if last_match:
            num = last_match.group(1) if last_match.group(1) else ""
            context.append(f"{prefix} {num}".strip())

    return context


def _split_into_articles(text: str) -> Tuple[str, List[_RawArticle]]:
    """
    Divide texto em preambulo + lista de artigos.

    Returns:
        (preambulo_text, [_RawArticle, ...])
    """
    matches = list(RE_ARTIGO.finditer(text))
    if not matches:
        return text, []

    # Preambulo: tudo antes do primeiro artigo
    preamble = text[:matches[0].start()].strip()

    articles = []
    for i, m in enumerate(matches):
        art_num = int(m.group(1))
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        art_text = text[start:end].strip()
        label = f"Art. {art_num}o"
        hierarchy = _find_hierarchy_context(text, start)

        articles.append(_RawArticle(
            art_num=art_num,
            label=label,
            text=art_text,
            start_pos=start,
            hierarchy_context=hierarchy,
        ))

    return preamble, articles


def _extract_sub_provisions(
    art: _RawArticle,
    doc_id: str,
) -> Tuple[List[LegalProvision], List[str]]:
    """
    Extrai sub-provisions (paragrafos, incisos, alineas) de um artigo.
    Retorna provisions e lista de sub_labels para hierarchy.
    """
    provisions = []
    art_key = f"art_{art.art_num}"
    order_base = art.art_num * 1000  # para ordenacao estavel

    # Paragrafos
    for m in RE_PARAGRAFO.finditer(art.text):
        par_num = m.group(1) or m.group(2)
        if par_num:
            par_key = f"{art_key}_par_{par_num}"
            par_label = f"Par. {par_num}o"
        else:
            par_key = f"{art_key}_par_unico"
            par_label = "Paragrafo unico"

        provisions.append(LegalProvision(
            provision_key=par_key,
            label=par_label,
            provision_type="paragrafo",
            parent_key=art_key,
            hierarchy_path=art.hierarchy_context + [art.label, par_label],
            order_in_doc=order_base + len(provisions) + 1,
            content="",  # content fica no chunk do artigo
        ))

    # Incisos (do artigo)
    for m in RE_INCISO.finditer(art.text):
        inc_roman = m.group(1).upper()
        inc_key = f"{art_key}_inc_{inc_roman}"
        inc_label = f"Inciso {inc_roman}"

        provisions.append(LegalProvision(
            provision_key=inc_key,
            label=inc_label,
            provision_type="inciso",
            parent_key=art_key,
            hierarchy_path=art.hierarchy_context + [art.label, inc_label],
            order_in_doc=order_base + len(provisions) + 1,
            content="",
        ))

    # Alineas
    for m in RE_ALINEA.finditer(art.text):
        ali_letter = m.group(1).lower()
        ali_key = f"{art_key}_ali_{ali_letter}"
        ali_label = f"Alinea {ali_letter})"

        provisions.append(LegalProvision(
            provision_key=ali_key,
            label=ali_label,
            provision_type="alinea",
            parent_key=art_key,
            hierarchy_path=art.hierarchy_context + [art.label, ali_label],
            order_in_doc=order_base + len(provisions) + 1,
            content="",
        ))

    return provisions


def _make_citation(doc_title_short: str, hierarchy: List[str]) -> str:
    """Gera citation_short como 'IN 62/2021, Art. 5, Par. 1o'."""
    parts = [doc_title_short]
    for h in hierarchy:
        if h.startswith("Art.") or h.startswith("Par.") or h == "Paragrafo unico":
            parts.append(h)
    return ", ".join(parts)


# ── Public API ────────────────────────────────────────────────────────────────

def chunk_legal_text(
    text: str,
    doc_id: str,
    doc_title_short: str,
) -> Tuple[List[LegalProvision], List[LegalChunk]]:
    """
    Chunka texto de legislacao em provisions + chunks estruturais.

    Args:
        text: texto completo normalizado
        doc_id: ID do documento (ex: 'lei_14133_2021_federal_br')
        doc_title_short: titulo curto para citacao (ex: 'Lei 14.133/2021')

    Returns:
        (provisions, chunks)
    """
    if not text or not text.strip():
        return [], []

    preamble, articles = _split_into_articles(text)

    # Fallback: se poucos artigos, usar chunker por paragrafos
    if len(articles) < MIN_ARTICLES_FOR_STRUCTURAL:
        logger.info(
            "doc_id=%s: apenas %d artigos detectados, usando fallback por paragrafos",
            doc_id, len(articles),
        )
        return _fallback_paragraph_chunks(text, doc_id, doc_title_short)

    logger.info(
        "doc_id=%s: %d artigos detectados, chunking estrutural",
        doc_id, len(articles),
    )

    all_provisions: List[LegalProvision] = []
    all_chunks: List[LegalChunk] = []
    order = 0

    # Preambulo
    if preamble and len(preamble.strip()) > 50:
        prov = LegalProvision(
            provision_key="preambulo",
            label="Preambulo",
            provision_type="preambulo",
            parent_key=None,
            hierarchy_path=["Preambulo"],
            order_in_doc=0,
            content=preamble,
        )
        all_provisions.append(prov)

        chunk = LegalChunk(
            chunk_id=f"{doc_id}__preambulo__0",
            doc_id=doc_id,
            provision_key="preambulo",
            order_in_doc=order,
            content=preamble,
            content_hash=_sha256(preamble),
            char_count=len(preamble),
            citation_short=f"{doc_title_short}, Preambulo",
            hierarchy_path=["Preambulo"],
        )
        all_chunks.append(chunk)
        order += 1

    # Artigos
    for art in articles:
        art_key = f"art_{art.art_num}"
        hierarchy = art.hierarchy_context + [art.label]

        # Provision do artigo
        art_prov = LegalProvision(
            provision_key=art_key,
            label=art.label,
            provision_type="artigo",
            parent_key=None,
            hierarchy_path=hierarchy,
            order_in_doc=art.art_num,
            content=art.text,
        )
        all_provisions.append(art_prov)

        # Sub-provisions (paragrafos, incisos, alineas)
        sub_provisions = _extract_sub_provisions(art, doc_id)
        all_provisions.extend(sub_provisions)

        # Chunks: se artigo grande, sub-chunk por paragrafo
        if len(art.text) > MAX_CHUNK_CHARS:
            sub_chunks = _sub_chunk_article(art, doc_id, doc_title_short, order)
            all_chunks.extend(sub_chunks)
            order += len(sub_chunks)
        else:
            citation = _make_citation(doc_title_short, hierarchy)
            chunk = LegalChunk(
                chunk_id=f"{doc_id}__{art_key}__0",
                doc_id=doc_id,
                provision_key=art_key,
                order_in_doc=order,
                content=art.text,
                content_hash=_sha256(art.text),
                char_count=len(art.text),
                citation_short=citation,
                hierarchy_path=hierarchy,
            )
            all_chunks.append(chunk)
            order += 1

    logger.info(
        "doc_id=%s: %d provisions, %d chunks gerados",
        doc_id, len(all_provisions), len(all_chunks),
    )
    return all_provisions, all_chunks


def _sub_chunk_article(
    art: _RawArticle,
    doc_id: str,
    doc_title_short: str,
    start_order: int,
) -> List[LegalChunk]:
    """Sub-divide artigo grande em chunks menores (por paragrafo/bloco)."""
    art_key = f"art_{art.art_num}"
    base_hierarchy = art.hierarchy_context + [art.label]
    chunks = []

    # Tenta dividir por paragrafos (§)
    par_splits = list(RE_PARAGRAFO.finditer(art.text))

    if par_splits:
        # Caput: texto antes do primeiro paragrafo
        caput_text = art.text[:par_splits[0].start()].strip()
        if caput_text:
            citation = _make_citation(doc_title_short, base_hierarchy)
            chunks.append(LegalChunk(
                chunk_id=f"{doc_id}__{art_key}__caput",
                doc_id=doc_id,
                provision_key=art_key,
                order_in_doc=start_order + len(chunks),
                content=caput_text,
                content_hash=_sha256(caput_text),
                char_count=len(caput_text),
                citation_short=citation,
                hierarchy_path=base_hierarchy,
            ))

        # Cada paragrafo como chunk
        for i, m in enumerate(par_splits):
            start = m.start()
            end = par_splits[i + 1].start() if i + 1 < len(par_splits) else len(art.text)
            par_text = art.text[start:end].strip()

            par_num = m.group(1) or m.group(2) or "unico"
            par_key = f"{art_key}_par_{par_num}"
            par_label = f"Par. {par_num}o" if par_num != "unico" else "Paragrafo unico"
            par_hierarchy = base_hierarchy + [par_label]

            citation = _make_citation(doc_title_short, par_hierarchy)
            chunks.append(LegalChunk(
                chunk_id=f"{doc_id}__{par_key}__0",
                doc_id=doc_id,
                provision_key=par_key,
                order_in_doc=start_order + len(chunks),
                content=par_text,
                content_hash=_sha256(par_text),
                char_count=len(par_text),
                citation_short=citation,
                hierarchy_path=par_hierarchy,
            ))
    else:
        # Sem paragrafos — divide por tamanho fixo
        _sub_chunk_by_size(art.text, art_key, doc_id, doc_title_short,
                           base_hierarchy, start_order, chunks)

    return chunks


def _sub_chunk_by_size(
    text: str,
    provision_key: str,
    doc_id: str,
    doc_title_short: str,
    hierarchy: List[str],
    start_order: int,
    chunks: List[LegalChunk],
    max_chars: int = MAX_CHUNK_CHARS,
):
    """Divide texto em chunks por tamanho fixo (fallback)."""
    lines = text.split("\n")
    buf = []
    buf_len = 0
    sub_idx = 0

    def flush_buf():
        nonlocal sub_idx, buf, buf_len
        if not buf:
            return
        content = "\n".join(buf).strip()
        if not content:
            buf, buf_len = [], 0
            return
        citation = _make_citation(doc_title_short, hierarchy)
        chunks.append(LegalChunk(
            chunk_id=f"{doc_id}__{provision_key}__{sub_idx}",
            doc_id=doc_id,
            provision_key=provision_key,
            order_in_doc=start_order + len(chunks),
            content=content,
            content_hash=_sha256(content),
            char_count=len(content),
            citation_short=citation,
            hierarchy_path=hierarchy,
        ))
        sub_idx += 1
        buf, buf_len = [], 0

    for line in lines:
        add = len(line) + 1
        if buf_len + add > max_chars and buf:
            flush_buf()
        buf.append(line)
        buf_len += add

    flush_buf()


def _fallback_paragraph_chunks(
    text: str,
    doc_id: str,
    doc_title_short: str,
) -> Tuple[List[LegalProvision], List[LegalChunk]]:
    """Fallback: chunker por paragrafos (para docs sem estrutura Art/Par clara)."""
    provisions = []
    chunks = []

    # Um unico provision "corpo"
    prov = LegalProvision(
        provision_key="corpo",
        label="Corpo do documento",
        provision_type="preambulo",
        parent_key=None,
        hierarchy_path=["Corpo"],
        order_in_doc=0,
        content=text,
    )
    provisions.append(prov)

    # Chunkar por tamanho
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    buf = []
    buf_len = 0
    order = 0

    def flush():
        nonlocal order, buf, buf_len
        if not buf:
            return
        content = "\n".join(buf).strip()
        if not content:
            buf, buf_len = [], 0
            return
        chunk = LegalChunk(
            chunk_id=f"{doc_id}__corpo__{order}",
            doc_id=doc_id,
            provision_key="corpo",
            order_in_doc=order,
            content=content,
            content_hash=_sha256(content),
            char_count=len(content),
            citation_short=doc_title_short,
            hierarchy_path=["Corpo"],
        )
        chunks.append(chunk)
        order += 1
        buf, buf_len = [], 0

    for p in paragraphs:
        add = len(p) + 1
        if buf_len + add > FALLBACK_MAX_CHARS and buf_len >= FALLBACK_MIN_CHARS:
            flush()
        buf.append(p)
        buf_len += add

    flush()

    return provisions, chunks
