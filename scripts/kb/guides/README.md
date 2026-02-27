# KB Guides — TCU Manual de Licitações

Pipeline de ingestão, chunking e indexação de guias orientativos no `kb-legal`.

## Primeiro guia: Manual TCU

**Fonte**: [Licitações e Contratos: Orientações e Jurisprudência do TCU](https://licitacoesecontratos.tcu.gov.br/manual/)
**Tipo**: Guia orientativo (não-normativo)
**Citável em defesa**: NÃO (`is_citable=false`)
**doc_type no index**: `guia_tcu`
**authority_score**: 0.50

## Stage Tags (enum congelado 2026-02-27)

| stage_tag | procedural_stage | Capítulos TCU | Chunks |
|---|---|---|---|
| `planejamento` | PLANEJAMENTO | 1, 3, 4 | 1.168 |
| `edital` | EDITAL | 5.1-5.2 | 124 |
| `seleção` | SELECAO | 5.3-5.11 | 722 |
| `contrato` | CONTRATO | 5.11 | 163 |
| `gestão` | GESTAO | 6 | 374 |
| `governança` | GOVERNANCA | 2 | 225 |

**Total**: 2.776 chunks indexados.

> AVISO: Alterar este enum requer reindex. Usar `validate_stage_tags.py` para verificar.

## Scripts

### 1. Ingestão (`ingest_tcu_manual.py`)
```bash
python scripts/kb/guides/ingest_tcu_manual.py \
  --run-id tcu_manual_2026-02-27 \
  --date-prefix 2026-02-27
```
Scrape HTML do site TCU (209 seções) + PDF fallback → Blob `kb-content/guia_tcu/raw/`.

### 2. Chunking (`chunk_tcu_manual.py`)
```bash
python scripts/kb/guides/chunk_tcu_manual.py \
  --run-id tcu_manual_2026-02-27 \
  --date-prefix 2026-02-27
```
Hierarquia + stage_tags determinísticos → Blob `kb-content/guia_tcu/processed/`.

### 3. Indexação (`index_guides_to_kblegal.py`)
```bash
AZURE_SEARCH_API_KEY=... AZURE_SEARCH_ENDPOINT=... OPENAI_API_KEY=... \
python scripts/kb/guides/index_guides_to_kblegal.py \
  --run-id tcu_manual_2026-02-27 \
  --date-prefix 2026-02-27 \
  --generate-embeddings true
```
Chunks → kb-legal (Azure AI Search) com embeddings + validação.

### 4. Validação (`validate_stage_tags.py`)
```bash
AZURE_SEARCH_API_KEY=... AZURE_SEARCH_ENDPOINT=... \
python scripts/kb/guides/validate_stage_tags.py
```
Verifica que todos os `procedural_stage` no index batem com o enum congelado.

## Env Vars Necessárias
| Var | Usado por |
|---|---|
| `AZURE_STORAGE_CONNECTION_STRING` | Scripts 1, 2, 3 |
| `AZURE_SEARCH_API_KEY` | Scripts 3, 4 |
| `AZURE_SEARCH_ENDPOINT` | Scripts 3, 4 |
| `OPENAI_API_KEY` | Script 3 (embeddings) |

## Blobs
```
kb-content/
  guia_tcu/
    raw/{date}/manual_tcu_pages.json       # HTML extraído (209 páginas)
    raw/{date}/manual_tcu.pdf              # PDF versionado
    metadata/{date}/manual_tcu.metadata.json
    processed/{date}/manual_tcu.semantic_chunks.json
    logs/{date}/index_log.json
```

## Governança
- `doc_type="guia_tcu"` forçado em runtime (não confia no arquivo)
- `is_citable=false` forçado em runtime
- `citable_reason="GUIA_ORIENTATIVO_NAO_NORMATIVO_USO_CHECKLIST"`
- Enum `stage_tags.py`: source of truth para valores permitidos
