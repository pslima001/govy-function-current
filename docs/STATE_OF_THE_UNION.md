# GOVY Platform — State of the Union

**Data**: 2026-02-19
**Repo**: `pslima001/govy-function-current`
**Function App**: `func-govy-parse-test` (Linux Consumption, Python 3.11, East US)

---

## 1. Arquitetura Atual

### Storage Accounts

| Account | Papel | Autenticacao |
|---------|-------|-------------|
| `stgovyparsetestsponsor` | Principal — blobs, queues, tables do app | **Managed Identity** (app code) + conn string (runtime) |
| `sttcejurisprudencia` | Jurisprudencia RAW (PDFs tribunais) | Connection string (`TCE_STORAGE_CONNECTION`) |

### Containers

```
stgovyparsetestsponsor
  ├── doutrina/              ← DOCX de doutrina (fonte)
  ├── doutrina-processed/    ← JSONs processados pelo doctrine pipeline
  ├── juris-parsed/          ← Outputs processados de jurisprudencia
  ├── kb-raw/                ← [LEGADO] imports antigos
  └── kb-processed/          ← [LEGADO] parsed antigos

sttcejurisprudencia
  ├── juris-raw/             ← Fonte da verdade (PDFs multi-tribunal)
  │     └── tce-sp/          ← 44.741 PDFs migrados
  │           ├── acordaos/
  │           ├── relatorios_voto/
  │           └── metadata/
  └── tce-jurisprudencia/    ← [LEGADO read-only] origem dos PDFs TCE-SP
```

### Path Pattern (juris-raw)

```
juris-raw/{tribunal}/acordaos/{doc_id}_acordao.pdf
juris-raw/{tribunal}/relatorios_voto/{doc_id}_voto.pdf
juris-raw/{tribunal}/metadata/{doc_id}.json
```

### Endpoints Ativos

| Endpoint | Metodo | Funcao |
|----------|--------|--------|
| `/api/ping` | GET | Health check |
| `/api/dicionario` | GET/POST/DELETE | CRUD dicionario juridico |
| `/api/ingest_doctrine` | POST | Pipeline de doutrina (DOCX → chunks → JSON) |
| `/api/tce_parser_v3` | POST | Parser TCE |
| `/api/juris_buscar` | POST | Busca jurisprudencia |
| `/api/kb_search` | POST | Busca Knowledge Base |
| + 15 outros | — | Extractors, uploads, classificadores |

---

## 2. Decisoes Arquiteturais

### Option 3: Hybrid Auth (MI + conn string)

**Contexto**: Precisavamos eliminar secrets (connection strings) do app code.

**O que testamos**:
- Phase 4 tentou migrar `AzureWebJobsStorage` para identity-based (`__accountName` + URIs)
- **Resultado**: 404 em todos os endpoints. Linux Consumption Plan nao consegue montar o pacote squashfs via MI.
- Rollback imediato, zero downtime.

**Decisao final**:
- **App code** (17 arquivos): `DefaultAzureCredential` via `govy/utils/azure_clients.py` (singleton)
- **Runtime** (`AzureWebJobsStorage`): connection string (obrigatorio no Consumption Plan)
- **TCE storage**: connection string (storage account separado, MI nao configurada la ainda)
- **`AZURE_STORAGE_CONNECTION_STRING`**: removido dos App Settings (era redundante)

**Por que nao desabilitar shared keys**: quebraria `AzureWebJobsStorage`. Tracked em GOV-29.

### Juris Storage Standard

Padrao multi-tribunal com separacao clara:
- **`juris-raw`**: fonte da verdade (PDFs originais, 1 container, prefixo por tribunal)
- **`juris-parsed`**: outputs processados (JSONs, prefixo por tribunal/ano)
- Container legado `tce-jurisprudencia` congelado como read-only

### Doctrine Pipeline: Contracts + Guardrails

- Input validation com `DoctrineIngestRequest` (dataclass tipada)
- Chunking com dedup por `content_hash` (SHA-256)
- Batch scripts com `--max-docs` e `--max-chars` (guardrails contra runaway)
- Semantic + verbatim classification no pipeline

---

## 3. PRs e Commits Relevantes

| PR | Titulo | Merged | Scope |
|----|--------|--------|-------|
| [#1](https://github.com/pslima001/govy-function-current/pull/1) | KB Pipeline Phase 2 — governance + corrections | 2026-02-18 | +697/-271, 8 files |
| [#2](https://github.com/pslima001/govy-function-current/pull/2) | Governance docs, dev env guide, sanity check | 2026-02-18 | +394/-7, 7 files |
| [#3](https://github.com/pslima001/govy-function-current/pull/3) | **Security: Option 3 storage auth hardening** | 2026-02-19 | +1259/-166, 37 files |
| [#4](https://github.com/pslima001/govy-function-current/pull/4) | Doctrine: phase 3 governance + batch guardrails | 2026-02-19 | +637/-54, 14 files |

**Commits relevantes pos-PR**:

| Hash | Descricao |
|------|-----------|
| `6909cd5` | TCE-SP migration report + docs update (pushed to main) |

### O que cada PR entregou

**PR #3 (auth hardening)** — o maior em scope:
- Criou `govy/utils/azure_clients.py` (singleton MI)
- Migrou 17 arquivos de `from_connection_string` para `DefaultAzureCredential`
- Removeu `AZURE_STORAGE_CONNECTION_STRING` dos App Settings
- Documentou arquitetura em `docs/security/storage-auth.md`
- Criou scripts de migracao/inventario de jurisprudencia
- Criou `docs/juris-storage-standard.md`
- Criou Linear GOV-29 para hardening futuro

**PR #4 (doctrine governance)**:
- `DoctrineIngestRequest` com validacao de campos obrigatorios
- Chunker com dedup por SHA-256
- Citation extractor
- `run_batch.py` e `run_microbatch_report.py` com argparse + guardrails
- Testes unitarios para chunker

---

## 4. Status: Done vs Next

### DONE

| Item | Evidencia |
|------|-----------|
| MI habilitada + RBAC (Blob/Queue/Table Contributor) | `az role assignment list` confirmado |
| 17 arquivos migrados para DefaultAzureCredential | PR #3 merged, CI green |
| `AZURE_STORAGE_CONNECTION_STRING` removido | App Settings verificado |
| Smoke tests (ping, read, write, delete) | HTTP 200 em todos |
| Doctrine ingest end-to-end | DOCX processado, JSON em `doutrina-processed/` |
| Deploy main (`6266762`) com remote build | Endpoints operacionais |
| TCE-SP migration (44.741 blobs) | Validated: count match + 10-blob size sample |
| Juris Storage Standard documentado | `docs/juris-storage-standard.md` |
| CI pipeline (ruff + pytest) cobrindo doctrine | GitHub Actions green |
| Doctrine batch guardrails (max-docs, max-chars) | PR #4 merged |
| 4 PRs merged, branches limpos | Apenas `main` ativo |

### NEXT (backlog)

| Item | Prioridade | Tracking |
|------|-----------|----------|
| Desabilitar shared keys em `stgovyparsetestsponsor` | Low | [GOV-29](https://linear.app/govycom/issue/GOV-29) |
| Migrar `TCE_STORAGE_CONNECTION` para MI | Medium | Requer RBAC em `sttcejurisprudencia` |
| Inventario TCU (scrape_pdf) | Medium | `tcu` em `juris-storage-standard.md` |
| Deprecar container `tce-jurisprudencia` | Low | Apos pipeline 100% em `juris-raw` |
| Deprecar `kb-raw` / `kb-processed` | Low | Apos confirmacao de nao-uso |
| Migrar para Elastic Premium ou separar runtime storage | Low | GOV-29 |
| Doctrine pipeline: timeout no ingest (504 em DOCX grande) | Medium | Observado em teste |
| Metadata generation para blobs em `juris-raw/tce-sp/` | Medium | 44.741 PDFs sem metadata JSON |

---

## 5. Riscos e Atencao

1. **Shared keys ainda habilitadas** — `AzureWebJobsStorage` depende delas. Nao ha workaround no Consumption Plan.
2. **504 timeout no doctrine ingest** — DOCX grandes excedem o timeout do Consumption Plan (~230s). Considerar queue-based processing.
3. **`sttcejurisprudencia` sem MI** — acesso via connection string. Se a key rotar, pipeline quebra.
4. **azure-storage-blob version lock** — 12.24.0 (12.28.0 tem bug de deserializacao em large listings). Monitorar fix upstream.
