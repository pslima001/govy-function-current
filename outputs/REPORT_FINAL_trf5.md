# REPORT_FINAL — TRF5 Parser Pipeline

## Closure

| Item | Valor |
|------|-------|
| Tribunal | TRF5 — Tribunal Regional Federal da 5ª Região |
| Parser | trf5_json_inline_v1 |
| Source | juris-raw/trf5/acordaos/ (sttcejurisprudencia) |
| Dest | kb-raw/trf5/ (stgovyparsetestsponsor) |
| Generated | 2026-02-25 20:46 UTC |

## Inventory

| Metric | Count |
|--------|-------|
| Source JSONs | 16,819 |
| Parsed & uploaded | 16,819 |
| Skipped (existing) | 0 |
| Terminal (no text) | 0 |
| Skipped (no content) | 0 |
| Validation errors | 0 |
| Upload errors | 0 |
| Elapsed | 5187.6s |
| Rate | 194.5/min |

## Audit

| Metric | Valor |
|--------|-------|
| Samples | 30 |
| PASS | 30 |
| FAIL | 0 |
| Verdict | **PASS** |

## Checksum

parsed + terminal_no_text + skipped_no_content + skipped_existing + upload_errors = total

16819 + 0 + 0 + 0 + 0 = 16819

## Closure Box

- [x] Scraper fechado (16.860 JSONs)
- [x] Parser implementado (trf5_json_inline_v1)
- [x] Batch parse completo
- [x] Audit 30/30 PASS
- [x] Artefatos no blob (_reports, _exceptions)
