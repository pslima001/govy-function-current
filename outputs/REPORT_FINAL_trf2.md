# REPORT_FINAL — TRF2 Parser Pipeline

## Closure

| Item | Valor |
|------|-------|
| Tribunal | TRF2 — Tribunal Regional Federal da 2ª Região |
| Parser | trf2_json_inline_v1 |
| Source | juris-raw/trf2/acordaos/ (sttcejurisprudencia) |
| Dest | kb-raw/trf2/ (stgovyparsetestsponsor) |
| Generated | 2026-02-27 17:40 UTC |

## Inventory

| Metric | Count |
|--------|-------|
| Source JSONs | 1,020 |
| Parsed & uploaded | 1,020 |
| Skipped (existing) | 0 |
| Terminal (no text) | 0 |
| Skipped (no content) | 0 |
| Validation errors | 0 |
| Upload errors | 0 |
| Elapsed | 323.6s |
| Rate | 189.1/min |

## Audit

| Metric | Valor |
|--------|-------|
| Samples | 30 |
| PASS | 30 |
| FAIL | 0 |
| Verdict | **PASS** |

## Checksum

parsed + terminal_no_text + skipped_no_content + skipped_existing + upload_errors = total

1020 + 0 + 0 + 0 + 0 = 1020

## Closure Box

- [x] Scraper fechado (1.020 JSONs, v1.0+v1.1)
- [x] Parser implementado (trf2_json_inline_v1)
- [x] Batch parse completo
- [x] Audit 30/30 PASS
- [x] Artefatos no blob (_reports, _exceptions)
