# REPORT_FINAL — TCE-GO Parser Pipeline

## Closure

| Item | Valor |
|------|-------|
| Tribunal | TCE-GO |
| Parser | tce_json_inline_v1 |
| Source | juris-raw/tce-go/acordaos/ (sttcejurisprudencia) |
| Dest | kb-raw/tce-go/ (stgovyparsetestsponsor) |
| Generated | 2026-02-25 14:09 UTC |

## Inventory

| Metric | Count |
|--------|-------|
| Source JSONs | 16,918 |
| Parsed & uploaded | 16,879 |
| Skipped (existing) | 0 |
| Terminal (no text) | 39 |
| Skipped (no content) | 0 |
| Validation errors | 0 |
| Upload errors | 0 |
| Elapsed | 5016.4s |
| Rate | 201.9/min |

## Audit

| Metric | Valor |
|--------|-------|
| Samples | 30 |
| PASS | 30 |
| FAIL | 0 |
| Verdict | **PASS** |

## Checksum

parsed + terminal_no_text + skipped_no_content + skipped_existing + upload_errors = total

16879 + 39 + 0 + 0 + 0 = 16918

## Closure Box

- [x] Scraper fechado (16.848 JSONs)
- [x] Parser implementado (tce_json_inline_v1)
- [x] Batch parse completo
- [x] Audit 30/30 PASS
- [x] Artefatos no blob (_reports, _exceptions)
