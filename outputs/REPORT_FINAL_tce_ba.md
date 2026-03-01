# REPORT_FINAL — TCE-BA Parser Pipeline

## Closure

| Item | Valor |
|------|-------|
| Tribunal | TCE-BA — Tribunal de Contas do Estado da Bahia |
| Parser | tce_parser_v3 (full_text strategy) |
| Source | juris-raw/tce-ba/acordaos/ (sttcejurisprudencia) |
| Dest | kb-raw/tce-ba/ (stgovyparsetestsponsor) |
| Generated | 2026-02-27 13:15 UTC |

## Inventory

| Metric | Count |
|--------|-------|
| Source PDFs | 11,341 |
| Parsed & uploaded | 10,280 (5,715 new + 4,565 existing) |
| Skipped (no content) | 1,061 |
| Terminal (no text) | 0 |
| Validation errors | 0 |
| Upload errors | 0 |
| Elapsed | 4,617s (77 min) |
| Rate | 74.3/min |

## Audit

| Metric | Valor |
|--------|-------|
| Samples | 30 |
| PASS | 28 |
| FAIL | 2 |
| Verdict | **28/30 PASS** |
| Failed check | `year_present` (2 docs antigos sem data no corpo do PDF) |
| Root cause | Data quality — PDFs antigos sem data parseavel, nao bug do parser |

## Checksum

parsed + skipped_existing + terminal_no_text + skipped_no_content + upload_errors = total

5,715 + 4,565 + 0 + 1,061 + 0 = 11,341 ✓

## Notas

- Os 1,061 `skipped_no_content` sao PDFs que o tce_parser_v3 extraiu texto mas o mapping descartou (conteudo vazio apos transform — ex: PDFs de imagem sem OCR).
- Dos ~5,278 "no_pdf" originalmente estimados, o resultado real e mais nuancado: todos os 11,341 tem PDF blob, mas ~1,061 produzem conteudo vazio.
- Cobertura real: **10,280/11,341 = 90.6%** (vs 53% estimado anteriormente).
- As 2 falhas de year_present sao docs antigos (ex: "Acordao 442/2006") onde a data esta no titulo da scraper metadata mas nao no corpo do PDF.

## Closure Box

- [x] Scraper fechado (11,341 PDFs)
- [x] Registry configurado (tce_parser_v3, full_text, BA)
- [x] Batch parse completo (10,280 kb-raw)
- [x] Audit 28/30 PASS (2 year_present — data quality)
- [x] Artefatos no blob (_reports)
- [x] Cobertura real 90.6% (melhor que estimativa de 53%)
