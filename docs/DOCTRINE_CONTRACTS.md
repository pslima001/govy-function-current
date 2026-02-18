# Contracts — Doctrine Pipeline (Phase 3)

> Regra de ouro: melhor `null` / `NAO_CLARO` do que valor inventado.

## 1. Input Document

```python
@dataclass
class DoctrineInput:
    doc_id: str               # identificador unico
    source_path: str          # blob name ou path local
    title: str                # titulo da obra/capitulo
    author: str               # autor (sigilo: nao expor nos chunks)
    year: int                 # ano da edicao
    raw_text: str             # texto bruto extraido
    meta: dict                # metadados extras (etapa_processo, tema_principal, etc.)
```

## 2. Chunk Output (obrigatorio)

```python
{
    "chunk_id": str,           # deterministic: hash(doc_id + index + prefix)
    "doc_type": "doutrina",    # fixo
    "secao": str,              # tese | vital | fundamento_legal | limites | contexto_minimo
    "content": str,            # texto do chunk
    "citation": str | None,    # referencia bibliografica ou None
    "confidence": float,       # 0.0 a 1.0
    "approved": bool,          # auto-aprovado ou pendente revisao
    "title": str,
    "author": str,
    "year": int,
    "source": str,             # source_path
    "doc_id": str,
}
```

## 3. Interfaces (assinaturas)

### reader_docx

```python
def read_docx_bytes(docx_bytes: bytes) -> DoctrineRawText:
    """Extrai texto do DOCX. Retorna DoctrineRawText(paragraphs, text)."""

def read(source: str | bytes) -> tuple[str, dict]:
    """Convenience: aceita path (str) ou bytes.
    Retorna (text, {"paragraphs": [...], "source_type": "path"|"bytes"})."""
```

### chunker

```python
MAX_CHARS_PER_CHUNK: int = 3500
MIN_CHARS_PER_CHUNK: int = 900

def chunk_paragraphs(paragraphs: list[str], max_chars=3500, min_chars=900) -> list[DoctrineChunk]:
    """Agrupa paragrafos em chunks. Retorna DoctrineChunk(chunk_id, order, content_raw, content_hash)."""

def chunk_text(text: str, doc_id: str = "") -> list[DoctrineChunk]:
    """Convenience: split em paragrafos e chunka."""
```

### citation_extractor

```python
def extract_citation_meta(text: str) -> dict:
    """Extrai metadados de citacao (tribunal, tipo_decisao, numero, relator, etc.)."""

def extract(text: str, meta: dict | None = None) -> dict:
    """Contract wrapper. Retorna {found: bool, citation_base: str|None, evidence: str|None, confidence: float}."""
```

### verbatim_classifier

```python
def is_verbatim_legal_text(text: str) -> bool:
    """Detecta conteudo literal de tribunal."""

def classify(chunk_content: str, source_text: str = "") -> dict:
    """Contract wrapper. Retorna {verbatim: bool, score: float}."""
```

### pipeline

```python
class DoctrinePipeline:
    def process(self, raw_text: str, meta: dict) -> dict:
        """
        Pipeline local (sem LLM):
        1. Chunking
        2. Citation extraction
        3. Verbatim classification
        4. Monta chunks com contrato

        Retorna:
        {
            "status": "approved",
            "doc_type": "doutrina",
            "chunks": [...],
            "meta": {...},
            "stats": {...},
        }
        """
```

### semantic (modo stub para CI)

```python
STUB_MODE: bool  # True quando OPENAI_API_KEY ausente

def extract_semantic_chunks_for_raw_chunks(...) -> list[dict]:
    """Se STUB_MODE, retorna [] sem chamar API."""
```

## 4. Batch Guardrails

```
run_batch.py / run_microbatch_report.py:
    --max-docs     (default 50)
    --max-workers  (default 2)
    --max-chars    (default 500000)
    log em arquivo: logs/doctrine_batch_YYYYMMDD.log
```

## 5. Regras de Validacao

- `chunk_id` deve ser deterministico (mesma entrada = mesmo id)
- `doc_type` deve ser exatamente `"doutrina"` para chunks de doutrina
- `confidence` entre 0.0 e 1.0
- `citation` = `null` se nao houver referencia (nunca inventar)
- Autor nunca aparece no `content` dos chunks (sigilo)
