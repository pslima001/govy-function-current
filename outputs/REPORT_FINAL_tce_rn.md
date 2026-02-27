# REPORT TCE-RN FINAL - FECHADO

**Data**: 2026-02-25
**Tribunal**: Tribunal de Contas do Estado do Rio Grande do Norte (TCE-RN)
**Status**: **TCE-RN FECHADO**

---

## Identidade (naming consistency)

| Campo | Valor | Fonte |
|-------|-------|-------|
| `tribunal_id` (machine) | `tce-rn` | `tribunal_registry.py` |
| `display_name` (humano) | `TCE-RN` | `tribunal_registry.py` |
| `tribunal_type` | `TCE` | parser detection |
| `uf` | `RN` | `tribunal_registry.py` |
| `region` | `NORDESTE` | derivado de `uf=RN` via `REGION_MAP` |
| `authority_score` | `0.80` | `tribunal_registry.py` |
| `parser_id` | `tce_rn_json` | `tribunal_registry.py` |
| `text_strategy` | `full_text` | `tribunal_registry.py` |

---

## 1. Inventario (fonte da verdade)

| Metrica | Valor | Evidencia |
|---------|-------|-----------|
| JSONs em `juris-raw/tce-rn/acordaos/` | **41,753** | blob listing (scraper) |
| JSONs em `kb-raw/tce-rn--*` | **40,584** | blob listing |
| Terminal skip (no_text) | **0** | `tce_rn_terminal_exceptions.json` |
| Reprocessavel | **0** | `tce_rn_terminal_exceptions.json` |
| Skipped no_content (parse) | **0** | batch report |
| Upload errors | **0** | batch report |
| Taxa de cobertura | **97.20%** (40584/41753) | |
| Poison queue | **0** | N/A (batch script, no queue) |

### 1.1 Diff reproduzivel

```
Prova: 41,753 raw - 40,584 parsed = 1,169 gap
No content skipped: 0
Terminal exceptions (no_text): 0
Reprocessavel: 0
Arquivo: outputs/tce_rn_terminal_exceptions.json
```

---

## 2. Scraping

| Metrica | Valor |
|---------|-------|
| Scraper | `scraper_tce_rn.py` |
| Arquitetura | 100% REST API (JSON inline, sem PDF) |
| API | `apiconsulta.tce.rn.gov.br` |
| Total records | 41,753 |
| Texto inline | 5 campos: ementa, relatorio, fundamentacaoVoto, conclusao, textoAcordao |
| Failed | 0 |

---

## 3. Parsing

| Metrica | Valor |
|---------|-------|
| Parser | `tce_rn_parser_v1` (dedicado, JSON inline) |
| Mapping | `mapping_tce_to_kblegal_v1` |
| Total processados | 40,584 |
| kb-raw gerados | 40,584 |
| No content skip | 0 |
| Upload errors | 0 |
| Elapsed | 11598.5s |
| Cobertura | 97.20% |

### 3.1 Content enrichment

TCE-RN content inclui 5 blocos (quando presentes):
1. **EMENTA** — resumo do acordao
2. **RELATÓRIO** — relato do processo
3. **FUNDAMENTAÇÃO** — fundamentacao do voto
4. **CONCLUSÃO** — conclusao do voto
5. **DISPOSITIVO** — texto do acordao (decisao)

---

## 4. Auditoria

| Metrica | Valor |
|---------|-------|
| Amostras | 30 |
| Estrategia | 15 random + 15 estratificadas (5 oldest, 5 median, 5 newest) |
| Seed | 42 |
| Resultado | **30/30** |
| Checks por amostra | 12 |

### 4.1 Checks executados

1. `tribunal == TCE`
2. `uf == RN`
3. `region == NORDESTE`
4. `authority_score == 0.8`
5. `parser_version == tce_rn_parser_v1`
6. `content_len > 50`
7. `chunk_id` presente
8. `doc_type == jurisprudencia`
9. `blob_path` presente
10. `processed_at` presente
11. `citation` presente
12. `year` presente

### 4.2 Arquivo de auditoria

`outputs/audit_tce_rn_20260225.json` — 30 samples, 12 asserts each, seed=42

---

## 5. Terminal exceptions

| Tipo | Quantidade | Tratamento |
|------|-----------|------------|
| `no_text_inline` | 0 | Terminal — content < 50 chars |
| `ementa_sem_dispositivo` | 0 | Reprocessavel — pode melhorar com parser update |

Arquivo: `outputs/tce_rn_terminal_exceptions.json`

---

## 6. Artefatos gerados

| Artefato | Path |
|----------|------|
| Registry | `govy/config/tribunal_registry.py` (entry `tce-rn`) |
| Parser | `govy/api/tce_rn_parser.py` |
| Batch script | `scripts/parse_tce_rn_batch.py` |
| Audit | `outputs/audit_tce_rn_20260225.json` |
| Terminal exceptions | `outputs/tce_rn_terminal_exceptions.json` |
| Report | `outputs/REPORT_FINAL_tce_rn.md` |

---

## 7. Decisoes e riscos

### 7.1 raw_prefix fix
Registry `raw_prefix` corrigido de `"tce-rn/"` para `"tce-rn/acordaos/"` — consistente com blobs reais.
Batch script ja usava hardcoded `"tce-rn/acordaos/"`, entao impacto = zero.

### 7.2 Content enrichment
`_build_content()` expandido para incluir RELATÓRIO, FUNDAMENTAÇÃO e CONCLUSÃO.
Impacto em outros tribunais: ZERO — outros parsers nao produzem esses campos.

### 7.3 Dados ricos
TCE-RN tem texto inline em 5 campos (nao depende de PDF parsing).
Expectativa: taxa de cobertura muito alta, poucos terminal exceptions.

---

## Estado final

| Dimensao | Status |
|----------|--------|
| Scraper | 🟢 |
| Parser | 🟢 |
| Operacional | 🔴 |
