# govy/legal/models.py
"""
Data models para o pipeline de legislacao.
Dataclasses puras, sem dependencia de DB.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ExtractionResult:
    """Resultado da extracao de texto de um documento."""
    text: str
    source_format: str          # 'pdf' | 'docx'
    extractor: str              # 'pymupdf' | 'pdfplumber' | 'python-docx'
    char_count: int
    sha256: str


@dataclass
class LegalProvision:
    """Um dispositivo legal (artigo, paragrafo, inciso, etc.)."""
    provision_key: str          # 'art_1', 'art_1_par_1', 'art_1_par_1_inc_II'
    label: str                  # 'Art. 1o', 'Par. 1o do Art. 1o'
    provision_type: str         # 'artigo', 'paragrafo', 'inciso', 'alinea', 'preambulo', 'anexo'
    parent_key: Optional[str]   # provision_key do pai
    hierarchy_path: List[str]   # ['Capitulo II', 'Secao I', 'Art. 5', 'Par. 1o']
    order_in_doc: int
    content: str                # texto completo do dispositivo


@dataclass
class LegalChunk:
    """Um chunk de texto para indexacao/busca."""
    chunk_id: str               # '{doc_id}__{provision_key}__{sub_idx}'
    doc_id: str
    provision_key: str
    order_in_doc: int
    content: str
    content_hash: str           # sha256
    char_count: int
    citation_short: str         # 'Lei 14.133/2021, Art. 5, Par. 1o'
    hierarchy_path: List[str]


@dataclass
class LegalDocumentRow:
    """Dados para upsert na tabela legal_document."""
    doc_id: str
    jurisdiction_id: str
    doc_type: str               # 'lei', 'decreto', 'instrucao_normativa', etc.
    number: Optional[str]
    year: Optional[int]
    title: str
    source_blob_path: Optional[str]
    source_format: str          # 'pdf' | 'docx'
    text_sha256: Optional[str]
    char_count: Optional[int]
    provisions: List[LegalProvision] = field(default_factory=list)
    chunks: List[LegalChunk] = field(default_factory=list)
