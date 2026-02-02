from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import List

from docx import Document


@dataclass(frozen=True)
class DoctrineRawText:
    paragraphs: List[str]
    text: str


def read_docx_bytes(docx_bytes: bytes) -> DoctrineRawText:
    """
    Extrai texto de DOCX.

    Regras:
      - NÃO usa LLM
      - NÃO interpreta
      - NÃO infere
      - NÃO altera sentido
      - apenas extrai + normaliza whitespace
    """
    doc = Document(BytesIO(docx_bytes))

    paras: List[str] = []
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if not t:
            continue
        t = " ".join(t.split())
        paras.append(t)

    text = "\n".join(paras).strip()
    return DoctrineRawText(paragraphs=paras, text=text)
