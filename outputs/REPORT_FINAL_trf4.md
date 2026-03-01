# REPORT_FINAL — TRF4 Parser Pipeline

## Closure

| Item | Valor |
|------|-------|
| Tribunal | TRF4 — Tribunal Regional Federal da 4ª Região |
| Parser | trf4_html_v1 |
| Source | juris-raw/trf4/acordaos/ (sttcejurisprudencia) |
| Dest | kb-raw/trf4/ (stgovyparsetestsponsor) |
| Generated | 2026-02-27 12:08 UTC |
| Filtros GOVY | crime/criminal exclusion + date 2016-2026 |

## Inventory

| Metric | Count |
|--------|-------|
| Source docs (metadata.json) | 1,755 |
| Parsed & uploaded | 161 |
| Skipped (existing) | 0 |
| Terminal (no text) | 0 |
| Terminal (excluded) | 183 |
| Terminal (date) | 1,411 |
| Skipped (no content) | 0 |
| Validation errors | 0 |
| Upload errors | 0 |
| HTML read errors | 0 |
| Elapsed | 797.9s |
| Rate | 12.1/min |

## Audit

| Metric | Valor |
|--------|-------|
| Samples | 30 |
| PASS | 30 |
| FAIL | 0 |
| Verdict | **PASS** |

## Checksum

parsed + terminal_no_text + terminal_excluded + terminal_date_excluded + skipped_no_content + skipped_existing + upload_errors = total

161 + 0 + 183 + 1411 + 0 + 0 + 0 = 1755

## Closure Box

| Check | Status |
|-------|--------|
| Filtro crime/criminal | Aplicado no parser |
| Filtro data 2016-2026 | Aplicado no parser |
| Checksum fecha | SIM |
| Audit 30/30 | PASS |
