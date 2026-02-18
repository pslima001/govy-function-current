from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List

# ── Constantes ────────────────────────────────────────────────────────────────
MAX_CHARS_PER_CHUNK = 3500
MIN_CHARS_PER_CHUNK = 900


@dataclass(frozen=True)
class DoctrineChunk:
    chunk_id: str
    order: int
    content_raw: str
    content_hash: str


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8", errors="ignore")).hexdigest()


def chunk_paragraphs(
    paragraphs: List[str],
    max_chars: int = 3500,
    min_chars: int = 900,
) -> List[DoctrineChunk]:
    """
    Agrupa parágrafos em chunks de tamanho controlado.

    Regras:
      - NÃO cria resumo
      - NÃO detecta seções
      - NÃO infere nada
      - apenas agrupa texto bruto
    """
    chunks: List[DoctrineChunk] = []
    buf: List[str] = []
    buf_len = 0
    order = 0

    def flush() -> None:
        nonlocal order, buf, buf_len
        if not buf:
            return

        content = "\n".join(buf).strip()
        if not content:
            buf, buf_len = [], 0
            return

        h = _sha256(content)
        chunk_id = f"doctrine_{order}_{h[:16]}"

        chunks.append(
            DoctrineChunk(
                chunk_id=chunk_id,
                order=order,
                content_raw=content,
                content_hash=h,
            )
        )

        order += 1
        buf, buf_len = [], 0

    for p in paragraphs:
        p = (p or "").strip()
        if not p:
            continue

        add = len(p) + 1
        if buf_len + add > max_chars and buf_len >= min_chars:
            flush()

        buf.append(p)
        buf_len += add

    flush()

    # Dedupe: remove chunks com content_hash identico
    seen_hashes: set[str] = set()
    deduped: List[DoctrineChunk] = []
    for ch in chunks:
        if ch.content_hash not in seen_hashes:
            seen_hashes.add(ch.content_hash)
            deduped.append(ch)

    return deduped


def chunk_text(text: str, doc_id: str = "") -> List[DoctrineChunk]:
    """Convenience: split texto em paragrafos e chunka.

    Args:
        text: texto bruto completo
        doc_id: prefixo opcional para chunk_id (nao usado no hash, apenas log)
    """
    if not text or not text.strip():
        return []
    paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
    return chunk_paragraphs(paragraphs)
