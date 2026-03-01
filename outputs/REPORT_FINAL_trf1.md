# REPORT_FINAL — TRF1 Parser Pipeline

## Closure

| Item | Valor |
|------|-------|
| Tribunal | TRF1 |
| Parser | trf1_cjf_metadata_v1 |
| Source | juris-raw/cjf/acordaos/cjf--TRF1--* (sttcejurisprudencia) |
| Dest | kb-raw/trf1/ (stgovyparsetestsponsor) |
| Generated | 2026-02-27 11:40 UTC |
| Nota | Somente metadata + ementa curta (CJF). Inteiro teor pendente (reCAPTCHA/Cloudflare). |

## Inventory

| Metric | Count |
|--------|-------|
| Source JSONs | 1,830 |
| Parsed & uploaded | 77 |
| Skipped (existing) | 1,750 |
| Terminal (no text) | 0 |
| Terminal (excluded) | 3 |
| Skipped (no content) | 0 |
| Validation errors | 0 |
| Upload errors | 0 |
| Elapsed | 21.8s |
| Rate | 211.8/min |

## Audit

| Metric | Valor |
|--------|-------|
| Samples | 30 |
| PASS | 30 |
| FAIL | 0 |
| Verdict | **PASS** |

## Checksum

parsed + terminal_no_text + terminal_excluded + skipped_no_content + skipped_existing + upload_errors = total

77 + 0 + 3 + 0 + 1750 + 0 = 1830

## Closure Box

- [x] Scraper fechado via CJF (1.830 metadata JSONs)
- [x] Parser implementado (trf1_cjf_metadata_v1)
- [x] Batch parse completo
- [x] Audit 30/30 PASS
- [x] Artefatos no blob (_reports, _exceptions)
- [ ] Inteiro teor pendente (pje2g reCAPTCHA + arquivo Cloudflare)
