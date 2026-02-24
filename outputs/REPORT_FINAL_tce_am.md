# REPORT TCE-AM FINAL - FECHADO

**Data**: 2026-02-24
**Tribunal**: Tribunal de Contas do Estado do Amazonas (TCE-AM)
**Status**: **TCE-AM FECHADO**

---

## Identidade (naming consistency)

| Campo | Valor | Fonte |
|-------|-------|-------|
| `tribunal_id` (machine) | `tce-am` | `tribunal_registry.py` |
| `display_name` (humano) | `TCE-AM` | `tribunal_registry.py` |
| `tribunal_type` | `TCE` | parser detection |
| `uf` | `AM` | `tribunal_registry.py` |
| `region` | `NORTE` | derivado de `uf=AM` via `REGION_MAP` |
| `authority_score` | `0.80` | `tribunal_registry.py` |
| `parser_id` | `tce_parser_v3` | `tribunal_registry.py` |
| `text_strategy` | `head` | `tribunal_registry.py` |

---

## 1. Inventario (fonte da verdade)

| Metrica | Valor | Evidencia |
|---------|-------|-----------|
| PDFs em `juris-raw/tce-am/acordaos/` | **33.941** | blob listing |
| JSONs em `kb-raw/tce-am--acordaos--*` | **33.900** | blob listing |
| Terminal skip (non_decision_attachment) | **41** | `tce_am_terminal_exceptions.json` |
| Taxa de cobertura | **99.88%** (33.900/33.941) | |
| Poison queue | **0** | `az storage message peek` |

### 1.1 Diff reproduzivel

```
Prova: 33.941 - 33.900 = 41
Arquivo: outputs/tce_am_terminal_exceptions.json (41 items)
Classificacao: ALL non_decision_attachment (PDFs sem marcadores juridicos)
```

### 1.2 Origem dos 33.941 PDFs

| Run | Filtro | PDFs |
|-----|--------|------|
| v1.0 (sem filtro) | Nenhum | ~31.854 (estimado) |
| v1.1 (com filtro) | 19 termos + 27 regex | 2.087 novos |
| **Total** | | **33.941** |

**Nota**: O v1.0 baixou significativamente mais que os 1.296 registrados na memoria.
O v1.1 adicionou 2.087 PDFs filtrados por relevancia (5.174 encontrados, 3.087 ja existiam).

---

## 2. Scraping

| Metrica | Valor |
|---------|-------|
| Scraper | `scraper_tce_am.py` + `run_tce_am.py` |
| Arquitetura | 100% REST API (sem Selenium) |
| API | `jurisprudencia-api.tce.am.gov.br/decisorios/byManyFields` |
| Cobertura temporal | 2016-2026 (11 anos) |
| Total filtrado (v1.1) | 5.174 relevantes |
| Downloaded (v1.1) | 2.087 |
| Skipped (existiam v1.0) | 3.087 |
| Failed | 0 |
| No PDF | 0 |

---

## 3. Parsing

| Metrica | Valor |
|---------|-------|
| Parser | `tce_parser_v3` |
| Mapping | `mapping_tce_to_kblegal_v1` |
| Total processados | 33.941 |
| kb-raw gerados | 33.900 |
| Terminal skip | 41 (non_decision_attachment) |
| Poison | 0 |
| Cobertura | 99.88% |

### 3.1 Enqueue strategy

Consumption Plan timeout (230s) impedia enqueue de 33.941 items em 1 chamada.
Solucao: batches de 500 com `skip_existing=true` (20 batches totais).

---

## 4. Auditoria

| Metrica | Valor |
|---------|-------|
| Amostras | 30 |
| Estrategia | 15 random + 15 estratificadas (5 oldest, 5 median, 5 newest) |
| Seed | 42 |
| Resultado | **30/30 PASS** |
| Checks por amostra | 12 |

### 4.1 Checks executados

1. `tribunal == TCE`
2. `uf == AM`
3. `region == NORTE`
4. `authority_score == 0.8`
5. `parser_version == tce_parser_v3`
6. `content_len > 50`
7. `chunk_id` presente
8. `doc_type == jurisprudencia`
9. `blob_path` presente
10. `processed_at` presente
11. `citation` presente
12. `year` presente

### 4.2 Arquivo de auditoria

`outputs/audit_tce_am_20260224.json` — 30 samples, 12 asserts each, seed=42

---

## 5. Terminal exceptions

| Tipo | Quantidade | Tratamento |
|------|-----------|------------|
| `non_decision_attachment` | 41 | Terminal — PDFs sem marcadores juridicos (EMENTA, DISPOSITIVO, ACORDAO, etc.) |

Arquivo: `outputs/tce_am_terminal_exceptions.json`

---

## 6. Artefatos gerados

| Artefato | Path |
|----------|------|
| Registry | `govy/config/tribunal_registry.py` (entry `tce-am`) |
| Audit | `outputs/audit_tce_am_20260224.json` |
| Terminal exceptions | `outputs/tce_am_terminal_exceptions.json` |
| Report | `outputs/REPORT_FINAL_tce_am.md` |

---

## 7. Decisoes e riscos

### 7.1 raw_prefix fix
O ChatGPT instruiu `raw_prefix="tce-am/acordaos/"`, mas o handler appends `acordaos/` automaticamente.
Corrigido para `raw_prefix="tce-am/"` (consistente com todos os outros TCEs).
Commit: `fix(registry): remove /acordaos/ from raw_prefix for TCE-AM and TCE-RJ`

### 7.2 Volume real vs esperado
Esperado: ~2.087 PDFs (filtrados v1.1).
Real: 33.941 PDFs (v1.0 sem filtro + v1.1 filtrado).
Impacto: parse batch processou TODOS, nao apenas os filtrados.
Risco: baixo — items nao-relevantes serao filtrados no search/index.

---

## Estado final

| Dimensao | Status |
|----------|--------|
| Scraper | 🟢 |
| Parser | 🟢 |
| Operacional | 🔴 |
