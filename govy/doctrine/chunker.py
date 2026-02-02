from __future__ import annotations

from dataclasses import dataclass
from typing import List
import hashlib


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
    return chunks
