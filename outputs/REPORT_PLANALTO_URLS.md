# REPORT: Planalto URL Validation — Core Federal Laws

**Data**: 2026-02-23
**Script**: `scripts/validate_planalto_urls.py`
**Manifest**: `normas-juridicas-registry/federal/planalto_core_manifest.json`

---

## Resumo

| Metrica | Valor |
|---------|-------|
| Total URLs | 9 |
| HTTP 200 | **9/9 (100%)** |
| Title match | **9/9 (100%)** |
| Status geral | **ALL OK** |

---

## Validacao por doc_id

| # | doc_id | URL | HTTP | Title | Size | Status |
|---|--------|-----|------|-------|------|--------|
| 1 | `lei_14133_2021_federal_br` | [l14133.htm](https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm) | 200 | LEI N 14.133, DE 1 DE ABRIL DE 2021 | 630 KB | OK |
| 2 | `lei_8666_1993_federal_br` | [l8666cons.htm](https://www.planalto.gov.br/ccivil_03/leis/l8666cons.htm) | 200 | LEI N 8.666, DE 21 DE JUNHO DE 1993 | 428 KB | OK |
| 3 | `lei_10520_2002_federal_br` | [l10520.htm](https://www.planalto.gov.br/ccivil_03/leis/2002/l10520.htm) | 200 | LEI N\<sup\>o\</sup\> 10.520, DE 17 DE JULHO DE 2002 | 25 KB | OK* |
| 4 | `lei_12462_2011_federal_br` | [l12462.htm](https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12462.htm) | 200 | LEI N 12.462, DE 4 DE AGOSTO DE 2011 | 270 KB | OK |
| 5 | `lc_123_2006_federal_br` | [lcp123.htm](https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp123.htm) | 200 | LEI COMPLEMENTAR N 123, DE 14 DE DEZEMBRO DE 2006 | 1.6 MB | OK |
| 6 | `decreto_10024_2019_federal_br` | [d10024.htm](https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2019/decreto/d10024.htm) | 200 | DECRETO N 10.024, DE 20 DE SETEMBRO DE 2019 | 125 KB | OK |
| 7 | `decreto_7892_2013_federal_br` | [d7892.htm](https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/decreto/d7892.htm) | 200 | Decreto n 7892 | 96 KB | OK |
| 8 | `lei_12527_2011_federal_br` | [l12527.htm](https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2011/lei/l12527.htm) | 200 | LEI N 12.527, DE 18 DE NOVEMBRO DE 2011 | 107 KB | OK |
| 9 | `lei_13303_2016_federal_br` | [l13303.htm](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2016/lei/l13303.htm) | 200 | LEI N 13.303, DE 30 DE JUNHO DE 2016 | 243 KB | OK |

\* Lei 10.520: titulo usa `<sup>o</sup>` no HTML (superscript), confirmado manualmente via byte inspection.

---

## Detalhes de Encoding

O Planalto usa encoding **latin-1** (ISO-8859-1) na maioria das paginas. Caracteres como `Nº` aparecem como:
- `N�` em UTF-8 sem conversao
- `Nº` decodificado corretamente em latin-1

O ingestor HTML deve decodificar com `latin-1` ou detectar encoding via `<meta charset>` / HTTP `Content-Type`.

---

## Composicao por Tipo

| Tipo | Qtd | Size total |
|------|-----|------------|
| Lei ordinaria | 6 | ~1.55 MB |
| Lei complementar | 1 | ~1.6 MB |
| Decreto | 2 | ~221 KB |
| **Total** | **9** | **~3.37 MB** |

---

## Campos do Manifest

Cada entrada contem:

| Campo | Descricao |
|-------|-----------|
| `doc_id` | ID unico padrao GOVY (`{tipo}_{numero}_{ano}_federal_br`) |
| `doc_type` | Tipo normativo (`lei`, `lei_complementar`, `decreto`) |
| `jurisdicao` | `federal/BR` |
| `source_of_truth` | `planalto_html` — Planalto como fonte primaria |
| `source_url` | URL da versao consolidada no Planalto |
| `ingest_mode` | `html` — ingestao direta do HTML (sem PDF) |
| `version_policy` | `consolidada` — texto com todas as alteracoes incorporadas |
| `status` | `present` (ja no DB) ou `missing` (a ingerir) |

---

## Status no DB

| doc_id | No DB? | Fonte atual | Acao |
|--------|--------|-------------|------|
| `lei_14133_2021_federal_br` | SIM | PDF OCR | Re-ingerir via HTML (melhor qualidade) |
| `lei_8666_1993_federal_br` | NAO | - | Ingerir via HTML |
| `lei_10520_2002_federal_br` | NAO | - | Ingerir via HTML |
| `lei_12462_2011_federal_br` | NAO | - | Ingerir via HTML |
| `lc_123_2006_federal_br` | NAO | - | Ingerir via HTML |
| `decreto_10024_2019_federal_br` | NAO | - | Ingerir via HTML |
| `decreto_7892_2013_federal_br` | NAO | - | Ingerir via HTML |
| `lei_12527_2011_federal_br` | NAO | - | Ingerir via HTML |
| `lei_13303_2016_federal_br` | NAO | - | Ingerir via HTML |

**1 presente, 8 missing** — proximo passo: implementar HTML ingestor (`ingest_mode=html`).

---

## Proximos Passos

1. **Passo 10.2**: Implementar `govy/legal/html_extractor.py` — download + parse do HTML do Planalto
2. **Passo 10.3**: Criar `scripts/ingest_planalto_core.py` — batch ingest das 8 leis missing
3. **Passo 10.4**: Re-ingerir Lei 14.133 via HTML (substituir texto OCR por HTML limpo)
4. **Passo 10.5**: Re-rodar extractors e gerar report v3
