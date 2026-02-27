# REPORT_FINAL — TRF3 Parser Pipeline

## Closure

| Item | Valor |
|------|-------|
| Tribunal | TRF3 — Tribunal Regional Federal da 3ª Região |
| Parser | trf3_json_inline_v1 |
| Source | juris-raw/trf3/acordaos/ (sttcejurisprudencia) |
| Dest | kb-raw/trf3/ (stgovyparsetestsponsor) |
| Generated | 2026-02-26 20:58 UTC |

## Inventory

| Metric | Count |
|--------|-------|
| Source JSONs | 9,470 |
| Parsed & uploaded | 9,470 |
| Skipped (existing) | 0 |
| Terminal (no text) | 0 |
| Skipped (no content) | 0 |
| Validation errors | 0 |
| Upload errors | 0 |
| Elapsed | 3601.4s |
| Rate | 157.8/min |

## Audit

| Metric | Valor |
|--------|-------|
| Samples | 30 |
| PASS | 30 |
| FAIL | 0 |
| Verdict | **PASS** |

## Checksum

parsed + terminal_no_text + skipped_no_content + skipped_existing + upload_errors = total

9470 + 0 + 0 + 0 + 0 = 9470

## Closure Box

- [x] Scraper fechado (9.470 JSONs)
- [x] Parser implementado (trf3_json_inline_v1)
- [x] Batch parse completo
- [x] Audit 30/30 PASS
- [x] Artefatos no blob (_reports, _exceptions)
