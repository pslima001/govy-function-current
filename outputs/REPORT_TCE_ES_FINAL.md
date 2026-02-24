# REPORT TCE-ES FINAL

**Data**: 2026-02-24
**Status**: TCE-ES FECHADO (baseline — 7.861/7.862 processados)
**Commit registry**: 193563b `feat: add TCE-ES to tribunal registry`
**Deploy**: `func azure functionapp publish func-govy-parse-test --build remote --python` (remote build OK, 20:51 UTC 2026-02-23)
**Parse batch**: 7.861 docs via `batch_parse_tce_es.py`, complete 22:07 UTC (41.9 min, ~187/min)
**Audit script**: `audit_tce_es_final.py` — executado 2026-02-24T11:22:00Z, seed=42

---

## 1. Inventario (Fonte vs Saida)

### Source: sttcejurisprudencia/juris-raw

| Prefixo | Tipo | Contagem |
|---------|------|----------|
| `tce-es/acordaos/*.pdf` | PDFs acordaos | **7.862** |
| `tce-es/acordaos/*.json` | Scraper metadata JSONs | **7.865** |

**Nota**: 7.865 JSONs vs 7.862 PDFs = 3 JSONs sem PDF (no_pdf — documentos sem `documento_id` no Diario).

### Output: stgovyparsetestsponsor/kb-raw

| Prefixo | Contagem |
|---------|----------|
| `tce-es--acordaos--*.json` | **7.861** |

### Diff

| Metrica | Valor |
|---------|-------|
| PDFs fonte (esperados) | 7.862 |
| JSONs em kb-raw (obtidos) | 7.861 |
| **Diff (missing)** | **1** |
| Extra (em kb-raw sem PDF) | 0 |

**Item missing**: `tce-es--acordaos--tce-es--diario--19366--3351191.json`
**Motivo**: `terminal_skip` — parser retornou `non_decision_attachment` (PDF com 688 bytes de texto, nao e acordao). Documentado e terminal.

---

## 2. Auditoria de 30 Amostras

### Asserts aplicados (6 por doc)

1. `kb_doc.tribunal == "TCE"`
2. `kb_doc.uf == "ES"`
3. `kb_doc.region == "SUDESTE"`
4. `kb_doc.authority_score == 0.80`
5. `metadata.parser_version == "tce_parser_v3"`
6. `kb_doc.content` nao vazio e `len(content) >= 50`

### Random 15 (seed=42)

| Blob | processed_at | content_len | Result |
|------|-------------|-------------|--------|
| tce-es--...--10702--2974700.json | 2026-02-23T21:25:53Z | 1436 | PASS 6/6 |
| tce-es--...--13388--3070192.json | 2026-02-23T21:26:55Z | 2361 | PASS 6/6 |
| tce-es--...--14275--3116475.json | 2026-02-23T21:27:13Z | 1073 | PASS 6/6 |
| tce-es--...--14715--3136652.json | 2026-02-23T21:29:52Z | 1553 | PASS 6/6 |
| tce-es--...--16209--3207618.json | 2026-02-23T21:30:57Z | 620 | PASS 6/6 |
| tce-es--...--30717--3378033.json | 2026-02-23T21:35:07Z | 2293 | PASS 6/6 |
| tce-es--...--31470--3415244.json | 2026-02-23T21:35:47Z | 513 | PASS 6/6 |
| tce-es--...--32906--3466836.json | 2026-02-23T21:36:37Z | 1034 | PASS 6/6 |
| tce-es--...--49153--4076966.json | 2026-02-23T21:48:38Z | 2158 | PASS 6/6 |
| tce-es--...--53448--4214927.json | 2026-02-23T21:52:39Z | 870 | PASS 6/6 |
| tce-es--...--55411--4281705.json | 2026-02-23T21:56:03Z | 1393 | PASS 6/6 |
| tce-es--...--58393--4357901.json | 2026-02-23T21:57:21Z | 507 | PASS 6/6 |
| tce-es--...--58610--4365270.json | 2026-02-23T21:57:26Z | 2165 | PASS 6/6 |
| tce-es--...--58630--4363779.json | 2026-02-23T21:57:28Z | 4812 | PASS 6/6 |
| tce-es--...--69920--4646712.json | 2026-02-23T22:05:36Z | 2610 | PASS 6/6 |

### Stratified 15 (5 first + 5 median + 5 last by doc_id order)

| Blob | Group | content_len | Result |
|------|-------|-------------|--------|
| tce-es--...--10045--2957160.json | FIRST | 1414 | PASS 6/6 |
| tce-es--...--10046--2957310.json | FIRST | 991 | PASS 6/6 |
| tce-es--...--10047--2909056.json | FIRST | 2114 | PASS 6/6 |
| tce-es--...--10048--2909092.json | FIRST | 1919 | PASS 6/6 |
| tce-es--...--10049--2909099.json | FIRST | 3670 | PASS 6/6 |
| tce-es--...--44823--3923434.json | MEDIAN | 914 | PASS 6/6 |
| tce-es--...--44824--3923445.json | MEDIAN | 1982 | PASS 6/6 |
| tce-es--...--44825--3923457.json | MEDIAN | 2349 | PASS 6/6 |
| tce-es--...--44826--3923461.json | MEDIAN | 1057 | PASS 6/6 |
| tce-es--...--44827--3923462.json | MEDIAN | 2356 | PASS 6/6 |
| tce-es--...--9905--2953782.json | LAST | 574 | PASS 6/6 |
| tce-es--...--9907--2955929.json | LAST | 1596 | PASS 6/6 |
| tce-es--...--9908--2955940.json | LAST | 1345 | PASS 6/6 |
| tce-es--...--9909--2955942.json | LAST | 1015 | PASS 6/6 |
| tce-es--...--9910--2955945.json | LAST | 1123 | PASS 6/6 |

### Resultado consolidado

| Metrica | Valor |
|---------|-------|
| Total amostras | 30 (15 random + 15 stratified) |
| Total asserts | **180** |
| PASS | **180** |
| FAIL | **0** |
| **PASS rate** | **100%** |

---

## 3. Scan de Conteudo (vazio/curto)

| Metrica | Valor |
|---------|-------|
| Amostras escaneadas | 200 (random) |
| Content vazio | **0** |
| Content curto (<50 chars) | **0** |

Nenhum problema de conteudo detectado.

---

## 4. Config-Source (5 verificacoes)

| Blob | kb.tribunal | kb.uf | parser.type | parser.name | Config-driven |
|------|-------------|-------|-------------|-------------|---------------|
| ...--48002--4051626.json | TCE | ES | TCE | TCE-ES | OK |
| ...--17150--3243931.json | TCE | ES | TCE | TCE-ES | OK |
| ...--12395--3036733.json | TCE | ES | TCE | TCE-ES | OK |
| ...--46857--4000277.json | TCE | ES | TCE | TCE-ES | OK |
| ...--13119--3061055.json | TCE | ES | TCE | TCE-ES | OK |

**5/5 config-driven**: tribunal/uf/region/authority_score vem do `tribunal_registry.py`, nao inferido do texto.

---

## 5. Filas

| Fila | Total msgs | TCE-ES msgs |
|------|-----------|-------------|
| parse-tce-queue | **0** | **0** |
| parse-tce-queue-poison | **0** | **0** |

**IMPORTANTE — Queue trigger inoperante (ver secao 8).**

---

## 6. Terminal Skip + no_pdf

### Terminal skip (parser)

| doc_id | Motivo | Status |
|--------|--------|--------|
| tce-es--diario--19366--3351191 | `non_decision_attachment` (688 bytes texto) | TERMINAL |

### no_pdf (scraper — sem documento_id)

| doc_id | Data publicacao | Acordao | Secao |
|--------|----------------|---------|-------|
| tce-es--diario--40171 | 2023-02-13 | 00027/2023-1 | — |
| tce-es--diario--60182 | 2024 | 01266/2024-5 | Conselho Superior |
| tce-es--diario--74803 | 2026-02-12 | 00076/2026-8 | Plenario |

Todos documentados em `juris-raw/tce-es/_runs/2026-02-23/no_pdf_registry.json` com `terminal: true`.

---

## 7. Idempotencia (preparacao agente diario)

### doc_id estavel

O `doc_id` segue formato deterministico: `tce-es--diario--{noticia_id}--{documento_id}`
- `noticia_id`: ID unico da noticia no Diario Oficial de Contas (monotonicamente crescente)
- `documento_id`: ID unico do documento/PDF no sistema

5/5 amostras confirmam estabilidade:

| raw_json | doc_id | Estavel |
|----------|--------|---------|
| tce-es--diario--10289--2966650 | tce-es--diario--10289--2966650 | Sim |
| tce-es--diario--10075--2957339 | tce-es--diario--10075--2957339 | Sim |
| tce-es--diario--10096--2958867 | tce-es--diario--10096--2958867 | Sim |
| tce-es--diario--10060--2957256 | tce-es--diario--10060--2957256 | Sim |
| tce-es--diario--10119--2958929 | tce-es--diario--10119--2958929 | Sim |

### blob_exists evita duplicacao

O scraper checa `blob_exists(container_client, json_blob)` antes de processar cada item (linha 379 de `scraper_tce_es.py`). Se o JSON ja existe, incrementa `skipped` e nao re-baixa/re-uploada.

### Parser nao sobrescreve JSON valido

O batch parser (`batch_parse_tce_es.py`) usa checkpoint — items ja processados nao sao re-enviados. O endpoint `test/parse-one` usa `overwrite=True` no `upload_blob`, mas isso so e chamado se o item ainda nao esta no checkpoint.

Para o agente diario, a dedup deve ser feita em duas camadas:
1. **Scraper**: `blob_exists()` no blob JSON em juris-raw (evita re-download)
2. **Parser**: `skip_existing` no enqueue (checa kb-raw antes de enfileirar)

### Campo delta para agente diario

**Campo recomendado**: `data_publicacao` (data da edicao do Diario Oficial)
- O scraper navega por data de edicao: `diario.tcees.tc.br/edicao/{year}/{month}/{day}`
- Para delta diario: consultar o calendario API com `year_start=year_end=ano_atual, month=mes_atual`
- `noticia_id` tambem e monotonicamente crescente, mas a API nao suporta filtro por ID — apenas por data

**Estrategia delta sugerida**:
```
1. Obter data de ultima edicao processada (do checkpoint)
2. Consultar calendario: GET /api/calendario/{year}/{month}
3. Para cada data > ultima processada: scrape_date()
4. blob_exists() evita duplicacao natural
```

---

## 8. Queue Trigger — Problema Documentado

### Sintoma

O queue trigger `parse_tce_pdf` (fila `parse-tce-queue`) **nao esta processando mensagens**. Observado em 2026-02-23:

- Mensagens com `dequeueCount = 0` (nunca foram dequeued pelo trigger)
- Afeta TODAS as mensagens, nao apenas TCE-ES (TCE-PR tambem com dequeueCount=0)
- Function App responde OK a HTTP requests (ping=200, test/parse-one=200)
- Queue trigger binding esta correto (`connection="AzureWebJobsStorage"`)
- `AzureWebJobsStorage` configurado com connection string valida

### Motivo provavel

Azure Functions Consumption Plan com **queue scaling inativo**:
- Apos deploy com `--build remote`, o host reinicia e o scale controller pode nao re-ativar o queue listener
- O runtime detecta a fila mas nao inicia o polling (possivel bug de cold start do scale controller)
- Alternativa: conflito entre `messageEncoding: "none"` no host.json e o encoding padrao do SDK

### Workaround aplicado

Full batch processado via endpoint HTTP direto `/api/test/parse-one`:
- Script local `batch_parse_tce_es.py` com concurrency=3
- 7.861 docs processados em 41.9 min (~187/min)
- Resultado identico ao que o queue trigger produziria

### Plano de correcao (separado do baseline)

1. Investigar `host.json` — testar com `messageEncoding: "base64"` (padrao)
2. Verificar se `az functionapp restart` resolve o polling
3. Se persistir: criar Function App dedicada para queue triggers (Premium Plan)
4. Issue a ser criada pelo arquiteto se necessario

---

## 9. Comandos Usados

```bash
# Deploy (com TCE-ES no registry)
func azure functionapp publish func-govy-parse-test --build remote --python

# Smoke test ping
curl -s "https://func-govy-parse-test-exabasfqgsfgexhd.eastus-01.azurewebsites.net/api/ping?code=..."

# Smoke parse (10 docs via HTTP direto)
curl -s -X POST ".../api/test/parse-one?code=..." \
  -H "Content-Type: application/json" \
  -d '{"tribunal_id":"tce-es","blob_path":"tce-es/acordaos/tce-es--diario--10045--2957160.pdf","json_key":"tce-es--acordaos--tce-es--diario--10045--2957160.json"}'

# Full batch (7.862 PDFs via script local)
python batch_parse_tce_es.py --concurrency 3

# Auditoria formal (reprodutivel, seed=42)
python audit_tce_es_final.py

# Contagens (reprodutiveis)
# PDFs fonte
az storage blob list --account-name sttcejurisprudencia --container-name juris-raw \
  --prefix "tce-es/acordaos/" --query "length([?ends_with(name, '.pdf')])" -o tsv

# JSONs kb-raw
az storage blob list --account-name stgovyparsetestsponsor --container-name kb-raw \
  --prefix "tce-es--" --query "length(@)" -o tsv

# Filas
az storage message peek --account-name stgovyparsetestsponsor \
  --queue-name parse-tce-queue --num-messages 32
az storage message peek --account-name stgovyparsetestsponsor \
  --queue-name parse-tce-queue-poison --num-messages 32
```

---

## TCE-ES FECHADO

- **7.861/7.862 docs** processados (1 terminal_skip documentado)
- **180/180 asserts** PASS (0 FAIL) em 30 amostras (15 random seed=42 + 15 estratificada)
- **200/200** content scan OK (0 vazio, 0 curto)
- **5/5** config-source OK (config-driven, nao inferido)
- **5/5** doc_id estavel (deterministico, monotonicamente crescente)
- **0 poison**, **0 pending** em filas
- **3 no_pdf** documentados e terminais
- Queue trigger inoperante — workaround via HTTP direto, plano de correcao documentado
- Scraper metadata merge parcial (relator, data_publicacao OK; campos com nomes diferentes nao mapeados — melhoria futura)
- Campo delta diario: `data_publicacao` via API calendario
