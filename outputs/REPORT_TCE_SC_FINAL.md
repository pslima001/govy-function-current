# REPORT TCE-SC FINAL

**Data**: 2026-02-23
**Status**: TCE-SC FECHADO (total — 576/576 com novo codigo)
**Commit**: a24aff7 `fix(tce-sc): scraper metadata merge + config-driven tribunal/uf/region`
**Deploy**: `func azure functionapp publish func-govy-parse-test --python` (remote build OK, 01:55 UTC)
**Full reprocess**: 576 docs, enqueue 20:41 UTC, complete 21:15 UTC
**Run summary**: `outputs/run_summary_tce_sc.json`

---

## 1. Inventario (Fonte vs Saida)

### Source: sttcejurisprudencia/juris-raw

| Prefixo | Tipo | Contagem |
|---------|------|----------|
| `tce-sc/acordaos/*.pdf` (excl. .voto.pdf) | PDFs acordaos | **576** |
| `tce-sc/acordaos/*.voto.pdf` | PDFs votos | 576 |
| `tce-sc/acordaos/*.json` | Scraper metadata JSONs | 576 |
| `tce-sc/relatorios_voto/` | Relatorios voto | **0** (nao existe) |

### Output: stgovyparsetestsponsor/kb-raw

| Prefixo | Contagem |
|---------|----------|
| `tce-sc--acordaos--*.json` | **576** |
| `tce-sc--relatorios_voto--*.json` | **0** |

### Diff

| Metrica | Valor |
|---------|-------|
| PDFs esperados | 576 |
| JSONs em kb-raw | 576 |
| **Diff (missing)** | **0** |

Todos os 576 blobs com lastModified >= 2026-02-23T20:44:33Z (novo codigo confirmado).

---

## 2. Auditoria de 33 Amostras (pos full reprocess)

### Asserts aplicados (6 por doc)

1. `kb_doc.tribunal == "TCE"`
2. `kb_doc.uf == "SC"`
3. `kb_doc.region == "SUL"`
4. `kb_doc.authority_score == 0.80`
5. `metadata.parser_version == "tce_parser_v3"`
6. `kb_doc.content` nao vazio e `len(content) >= 50`

### Random 15 (seed=42)

| Blob | processed_at | Result |
|------|-------------|--------|
| tce-sc--acordaos--141924.json | 2026-02-23T20:44:37Z | PASS 6/6 |
| tce-sc--acordaos--140393.json | 2026-02-23T20:44:34Z | PASS 6/6 |
| tce-sc--acordaos--143662.json | 2026-02-23T21:14:44Z | PASS 6/6 |
| tce-sc--acordaos--143297.json | 2026-02-23T20:44:42Z | PASS 6/6 |
| tce-sc--acordaos--142998.json | 2026-02-23T20:44:41Z | PASS 6/6 |
| tce-sc--acordaos--142201.json | 2026-02-23T20:44:38Z | PASS 6/6 |
| tce-sc--acordaos--141710.json | 2026-02-23T20:44:37Z | PASS 6/6 |
| tce-sc--acordaos--149624.json | 2026-02-23T20:45:03Z | PASS 6/6 |
| tce-sc--acordaos--141598.json | 2026-02-23T20:44:36Z | PASS 6/6 |
| tce-sc--acordaos--146107.json | 2026-02-23T20:44:57Z | PASS 6/6 |
| tce-sc--acordaos--140598.json | 2026-02-23T20:44:34Z | PASS 6/6 |
| tce-sc--acordaos--140444.json | 2026-02-23T20:44:34Z | PASS 6/6 |
| tce-sc--acordaos--141672.json | 2026-02-23T20:44:36Z | PASS 6/6 |
| tce-sc--acordaos--142957.json | 2026-02-23T20:44:40Z | PASS 6/6 |
| tce-sc--acordaos--143082.json | 2026-02-23T20:44:41Z | PASS 6/6 |

### Stratified 15 (5 oldest + 5 median + 5 newest by lastModified)

| Blob | lastModified | Group | Result |
|------|-------------|-------|--------|
| tce-sc--acordaos--139282.json | 2026-02-23T20:44:33Z | OLDEST | PASS 6/6 |
| tce-sc--acordaos--139700.json | 2026-02-23T20:44:33Z | OLDEST | PASS 6/6 |
| tce-sc--acordaos--139715.json | 2026-02-23T20:44:33Z | OLDEST | PASS 6/6 |
| tce-sc--acordaos--139717.json | 2026-02-23T20:44:33Z | OLDEST | PASS 6/6 |
| tce-sc--acordaos--139794.json | 2026-02-23T20:44:33Z | OLDEST | PASS 6/6 |
| tce-sc--acordaos--143761.json | 2026-02-23T20:44:50Z | MEDIAN | PASS 6/6 |
| tce-sc--acordaos--143803.json | 2026-02-23T20:44:50Z | MEDIAN | PASS 6/6 |
| tce-sc--acordaos--143793.json | 2026-02-23T20:44:51Z | MEDIAN | PASS 6/6 |
| tce-sc--acordaos--143812.json | 2026-02-23T20:44:51Z | MEDIAN | PASS 6/6 |
| tce-sc--acordaos--143864.json | 2026-02-23T20:44:51Z | MEDIAN | PASS 6/6 |
| tce-sc--acordaos--143664.json | 2026-02-23T21:14:47Z | NEWEST | PASS 6/6 |
| tce-sc--acordaos--143667.json | 2026-02-23T21:14:49Z | NEWEST | PASS 6/6 |
| tce-sc--acordaos--143669.json | 2026-02-23T21:14:51Z | NEWEST | PASS 6/6 |
| tce-sc--acordaos--143670.json | 2026-02-23T21:14:53Z | NEWEST | PASS 6/6 |
| tce-sc--acordaos--143681.json | 2026-02-23T21:14:54Z | NEWEST | PASS 6/6 |

### Legacy 3 (anteriormente falhando — retestados pos reprocess)

| Doc | Antes (old code) | Depois (new code) | Result |
|-----|------------------|--------------------|--------|
| **141672** | tribunal=STF, score=1.0 | tribunal=TCE, uf=SC, score=0.80, relator=WILSON ROGERIO WAN-DALL | PASS 6/6 |
| **140063** | uf=RS | uf=SC, relator=JOSE NEI ALBERTON ASCARI | PASS 6/6 |
| **143313** | tribunal=STF, uf=DF, region=CENTRO_OESTE, score=1.0 | tribunal=TCE, uf=SC, region=SUL, score=0.80, relator=CESAR FILOMENO FONTES | PASS 6/6 |

### Resultado consolidado

| Metrica | Valor |
|---------|-------|
| Total amostras | 33 (15 random + 15 stratified + 3 legacy) |
| Total asserts | **198** |
| PASS | **198** |
| FAIL | **0** |
| **PASS rate** | **100%** |
| Todos 576 com novo codigo | **Sim** (lastModified >= 2026-02-23T20:44:33Z) |

---

## 3. Skips Legitimos

| Metrica | Valor |
|---------|-------|
| skipped_count | **0** |
| no_content | 0 |
| pdf_too_small | 0 |
| missing JSONs | 0 |

Todos os 576 PDFs geraram JSONs validos. Nenhum skip.

---

## 4. Filas

| Fila | Contagem |
|------|----------|
| parse-tce-queue (tce-sc) | **0** |
| parse-tce-queue-poison (tce-sc) | **0** |

Nenhuma mensagem pendente ou envenenada para TCE-SC. Filas limpas.

---

## 5. Container Legado

| Container | Prefixo | Contagem | Status |
|-----------|---------|----------|--------|
| stgovyparsetestsponsor/juris-parsed | tce-sc/ | **0** | Nao usado/legado (vazio) |

---

## 6. Stragglers (12 docs)

12 docs nao foram atualizados pelo queue trigger (concorrencia com mensagens TCE-PR na mesma fila).
Reprocessados com sucesso via HTTP endpoint `/api/test/parse-one`.

Doc IDs: 143588, 143605, 143608, 143637, 143657, 143662, 143663, 143664, 143667, 143669, 143670, 143681

Todos passam 6/6 asserts apos reprocessamento.

---

## 7. Mudancas de Codigo (commit a24aff7)

### tce_queue_handler.py
- Fix voto filter: `.endswith(".voto.pdf")` (era substring `.voto.`)
- Nova funcao `_normalize_scraper_fields()`: mapeia campos scraper → parser
- Apos parser: le scraper JSON do blob storage, normaliza, merge via `merge_with_scraper_metadata()`
- Passa `config=cfg` ao mapping

### mapping_tce_to_kblegal.py
- `transform_parser_to_kblegal()`: aceita `config` param
- Quando config presente: usa registry para tribunal/uf/authority_score/region (nunca infere do texto)
- `_build_title()` e `_build_source()`: aceitam `display_name` do config
- Skips de inferencia para campos ja setados pelo config

### kb_index_upsert.py
- `NAO_CLARO` adicionado a VALID_EFFECTS

---

## 8. Comandos Usados

```bash
# Deploy
func azure functionapp publish func-govy-parse-test --python

# Smoke test (10 docs)
curl -X POST ".../api/kb/juris/enqueue-tce?code=..." \
  -d '{"tribunal_id": "tce-sc", "skip_existing": false, "limit": 10}'

# Full reprocess (576 docs)
curl -X POST ".../api/kb/juris/enqueue-tce?code=..." \
  -d '{"tribunal_id": "tce-sc", "skip_existing": false, "limit": 0}'

# Stragglers via HTTP
curl -X POST ".../api/test/parse-one?code=..." \
  -d '{"tribunal_id": "tce-sc", "blob_path": "tce-sc/acordaos/{id}.pdf", "json_key": "tce-sc--acordaos--{id}.json"}'

# Contagens
az storage blob list --account-name sttcejurisprudencia --container-name juris-raw \
  --prefix "tce-sc/acordaos/" --num-results 5000 --query "length([?ends_with(name, '.pdf')])"

az storage blob list --account-name stgovyparsetestsponsor --container-name kb-raw \
  --prefix "tce-sc--acordaos--" --num-results 5000 --query "length(@)"

# Filas
az storage message peek --account-name stgovyparsetestsponsor \
  --queue-name parse-tce-queue-poison --num-messages 32
```

---

## TCE-SC FECHADO

- **576/576 docs** processados com novo codigo
- **198/198 asserts** PASS (0 FAIL)
- **0 poison**, **0 missing**, **0 skips**
- **3 legacy failures corrigidos** (STF/RS/DF → TCE/SC/SUL)
- Scraper metadata merge ativo (relator, processo, datas preenchidos)
- Config-driven identity (tribunal/uf/score/region do registry)
