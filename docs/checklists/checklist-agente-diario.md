# Checklist "AGENTE DIÁRIO" — TCE (genérico)

Operação contínua para qualquer tribunal. Independente de código — define regras e evidências esperadas.

---

## 1. ENTRADA — O que o agente lê

### 1a) Delta Strategy (obrigatório por tribunal)

Cada tribunal **deve ter** um `delta_strategy` registrado antes de entrar em operação diária.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `tribunal_id` | string | ID do tribunal (ex.: `tce-mg`) |
| `strategy` | enum | `date_range` \| `last_n_pages` \| `incremental_api` \| `csv_poll` |
| `date_field` | string | Campo usado para filtro de data (ex.: `dt_sessao`, `dt_publicacao`, `ano_sessao`) |
| `safety_window_days` | int | Dias de reprocessamento para capturar atrasos (padrão: 7) |
| `max_pages` | int/null | Limite de páginas por run (null = sem limite) |
| `rate_limit` | object | `{"requests_per_min": N, "backoff_base_sec": N}` |

**Estratégias por tipo de tribunal:**

| Estratégia | Quando usar | Exemplo |
|------------|-------------|---------|
| `date_range` | API aceita filtro por data | TCE-CE, TCE-ES, TCE-BA, TCU |
| `last_n_pages` | Sem filtro de data, mas resultados ordenados por recência | TCE-MG (Selenium), TCE-RJ |
| `incremental_api` | API tem parâmetro `since` ou `offset` estável | TCE-RS (ElasticSearch `search_after`) |
| `csv_poll` | Dados publicados em CSV/arquivo periódico | TCE-PR (CSV anual) |

**Registro obrigatório:**
- [ ] `delta_strategy` definido para o tribunal
- [ ] Estratégia testada em dry-run antes do primeiro run diário
- [ ] Documentada em `juris-raw/<tribunal>/_config/delta_strategy.json`

**Formato de `delta_strategy.json`:**
```json
{
  "tribunal_id": "tce-mg",
  "strategy": "last_n_pages",
  "date_field": null,
  "safety_window_days": 7,
  "max_pages": 3,
  "rate_limit": {"requests_per_min": 10, "backoff_base_sec": 3},
  "keywords": ["licitação", "pregão", "contratação"],
  "relevance_filter": true,
  "notes": "Selenium obrigatório. chkColegiado=true. Cookie banner + CAPTCHA bypass."
}
```

### 1b) Janela de Segurança (parametrizável)

A janela de segurança captura publicações atrasadas pelo tribunal.

- [ ] **Parâmetro**: `safety_window_days` (no `delta_strategy.json`)
- [ ] **Default**: 7 dias
- [ ] **Cálculo**: `query_from = checkpoint_date - safety_window_days`
- [ ] **Exceções por tribunal** (quando o tribunal atrasa mais):

| Tribunal | `safety_window_days` | Justificativa |
|----------|---------------------|---------------|
| TCE-MG | 14 | Publicação manual, atrasos frequentes |
| TCE-PR | 30 | CSV atualizado mensalmente |
| TCU | 7 | Publicação regular |
| Outros | 7 | Default |

- [ ] Janela parametrizável via env var override: `SAFETY_WINDOW_<TRIBUNAL>=N`
- [ ] Run diário calcula: `today - safety_window_days` → `today`
- [ ] Itens já baixados dentro da janela → `skipped` (sem re-download)

### 1c) Checkpoint e estado

- [ ] **Checkpoint lido**: `juris-raw/<tribunal>/_runs/YYYY-MM-DD/checkpoint.json`
  - Contém: `last_date`, `last_doc_ids[]`, `counters`, `failures[]`
- [ ] **Keywords/filtros de relevância**: mesmos critérios do baseline (19 termos + regex)
- [ ] **Rate limiting**: conforme `delta_strategy.json`

## 2. PROCESSAMENTO — Idempotência e dedup

### 2a) Dedup intra-run (padrão)
- [ ] **Chave estável** (`doc_id`) por documento — mesmo padrão do baseline
- [ ] **Skip por `blob_exists`** — se `juris-raw/<tribunal>/acordaos/{doc_id}/decisao.pdf` já existe, skip
- [ ] **Re-run diário NÃO duplica** nem "rebaixa" dados existentes

### 2b) Dedup cross-run por `doc_id` + SHA do PDF

Mesmo `doc_id` pode ter PDF atualizado pelo tribunal. Detectar e tratar:

- [ ] **SHA-256 do PDF** calculado antes do upload
- [ ] **Comparação**: se blob já existe com mesmo `doc_id`:
  1. Calcular SHA-256 do PDF novo (downloaded)
  2. Ler `metadata.sha256` do blob existente (ou calcular do blob)
  3. Se SHA igual → `skipped` (conteúdo idêntico)
  4. Se SHA diferente → `updated` (PDF mudou, re-upload + novo metadata)
- [ ] **Registro de updates**: no `run_summary.json`, campo `updated` separado de `new`

**Formato do metadata com SHA:**
```json
{
  "doc_id": "tce-mg--AC-2026-0412",
  "sha256_pdf": "a1b2c3d4e5f6...",
  "sha256_json": "f6e5d4c3b2a1...",
  "uploaded_at": "2026-02-24T10:30:00Z",
  "updated_at": null
}
```

**Quando SHA difere (update):**
```json
{
  "doc_id": "tce-mg--AC-2026-0412",
  "sha256_pdf": "new_hash_here...",
  "sha256_json": "new_json_hash...",
  "uploaded_at": "2026-02-20T08:00:00Z",
  "updated_at": "2026-02-24T10:30:00Z",
  "previous_sha256_pdf": "a1b2c3d4e5f6..."
}
```

### 2c) Classificação de resultado

Cada item processado recebe exatamente uma classificação:

| Status | Significado | Conta como falha? |
|--------|-------------|-------------------|
| `new` | Documento baixado com sucesso (PDF + JSON) | Não |
| `updated` | Mesmo doc_id, PDF com SHA diferente (re-uploaded) | Não |
| `skipped` | Já existe no blob com SHA idêntico | Não |
| `no_pdf` | Documento sem PDF disponível | Não |
| `terminal_skip` | Attachment/não-decisão/image-only | Não |
| `failed` | Erro real (HTTP 5xx, timeout) | **Sim** |
| `poison` | Falha irrecuperável após retries | **Sim — CRÍTICO** |

## 3. SAÍDA — Blobs e arquivos gerados

### Blobs por documento novo
- [ ] `juris-raw/<tribunal>/acordaos/{doc_id}/decisao.pdf`
- [ ] `juris-raw/<tribunal>/acordaos/{doc_id}/metadata.json` (scraper JSON)

### Artefatos de run (pacote mínimo diário)
- [ ] `juris-raw/<tribunal>/_runs/YYYY-MM-DD/checkpoint.json`
- [ ] `juris-raw/<tribunal>/_runs/YYYY-MM-DD/run_summary.json`
- [ ] `outputs/DAILY_<TRIBUNAL>_YYYY-MM-DD.md` (relatório legível)

### Exceções (quando houver)
- [ ] `kb-raw/_exceptions/<tribunal>_terminal_YYYY-MM-DD.json`
- [ ] `outputs/<tribunal>_no_pdf_YYYY-MM-DD.txt`

## 4. AUDITORIA — Asserts pós-run

- [ ] **Contagem esperada**: `new + updated + skipped + no_pdf + terminal_skip == total_buscado`
- [ ] **Failed = 0** (ou alerta + registro)
- [ ] **Poison = 0** (invariante — nunca tolerado)
- [ ] **Novos blobs spot-check** (3 aleatórios dos `new` + `updated`):
  - [ ] PDF é válido (>1KB, header `%PDF`)
  - [ ] JSON tem campos obrigatórios (`doc_id`, `tribunal`, `data_sessao`, `ementa`)
  - [ ] `sha256_pdf` no metadata corresponde ao hash real do blob
- [ ] **Config is source of truth** (campos do registry, não do PDF):
  - [ ] `tribunal`, `uf`, `authority_score` = valores do registry

## 5. FILAS — main / poison

- [ ] **Se usa fila (Azure Queue)**:
  - [ ] Queue main = 0 ao final (todos processados ou em terminal_skip)
  - [ ] Poison queue = 0 (invariante)
  - [ ] Se poison > 0 → rotina de incidente (seção 7)
- [ ] **Se NÃO usa fila** (scraper direto):
  - [ ] Resultado equivalente via contadores no `run_summary.json`
  - [ ] Itens que falharam 3x = `terminal_skip` (não retentados no próximo dia)

## 6. OBSERVABILIDADE — Métricas e alertas

### Métricas por run (no `run_summary.json`)
```json
{
  "tribunal": "<tribunal>",
  "date": "YYYY-MM-DD",
  "delta_strategy": "<strategy>",
  "safety_window_days": 7,
  "delta_window": {"from": "YYYY-MM-DD", "to": "YYYY-MM-DD"},
  "counters": {
    "searched": 0,
    "new": 0,
    "updated": 0,
    "skipped": 0,
    "no_pdf": 0,
    "terminal_skip": 0,
    "failed": 0,
    "poison": 0
  },
  "duration_seconds": 0,
  "rate_items_per_min": 0.0,
  "checkpoint_updated": true
}
```

### Alertas (obrigatórios)
- [ ] `failed > 0` → alerta + detalhes no relatório
- [ ] `poison > 0` → alerta CRÍTICO + rotina de incidente
- [ ] Coverage drop: se `new == 0` por N dias consecutivos → alerta (tribunal pode ter mudado API)
- [ ] Run não rodou (heartbeat): se `_runs/YYYY-MM-DD/` não existe até horário esperado → alerta
- [ ] `new` anomalamente alto (>3x média) → alerta (possível duplicação ou mudança de API)
- [ ] `updated > 0` → informativo (tribunal republicou documentos, verificar se é normal)

### Logs
- [ ] `AZURE_LOG_LEVEL` suprimido (sem spam do SDK)
- [ ] Log format: `[YYYY-MM-DD HH:MM:SS] [LEVEL] [tribunal] message`

## 7. ROTINA DE INCIDENTE

Quando algo dá errado no run diário:

| Situação | Ação |
|----------|------|
| `failed > 0` | Investigar causa. Se transient (5xx, timeout) → retry manual ou esperar próximo dia. Se persistente → escalar. |
| `poison > 0` | **CRÍTICO.** Identificar doc_id, baixar raw, diagnosticar. Nunca ignorar. |
| `new == 0` por 3+ dias | Verificar se tribunal mudou API/site. Testar manualmente. |
| Run não rodou | Verificar scheduler/VM/cron. Reexecutar manualmente se dentro da janela. |
| Coverage caiu | Comparar volume esperado vs obtido. Checar se filtros/keywords ainda são válidos. |
| Checkpoint corrompido | Usar checkpoint do dia anterior (`_runs/D-1/checkpoint.json`). Reprocessar janela maior. |
| `updated` inesperado | Tribunal republicou PDFs. Verificar se é correção legítima ou bug no dedup. |

## 8. SEPARAÇÃO DE PR / AUTOMAÇÃO

### Separação de PR
- [ ] PR do agente diário **não inclui** código de "baseline full run"
- [ ] PR do baseline **não inclui** scheduler/infra do agente diário
- [ ] Código do agente reutiliza o scraper existente (modo `--incremental` ou `--since <date>`)

### Como Automatizar — Hooks sugeridos

**Opção A: Cron na VM (vm-tce-scraper)**
```bash
# crontab -e
0 6 * * * /home/azureuser/run_daily.sh >> /home/azureuser/logs/daily_$(date +\%F).log 2>&1
```

**Opção B: Azure Timer Trigger (Function App)**
```python
# function.json
{
  "scriptFile": "__init__.py",
  "bindings": [{
    "name": "timer",
    "type": "timerTrigger",
    "direction": "in",
    "schedule": "0 0 6 * * *"
  }]
}
```

**Opção C: GitHub Actions (scheduled workflow)**
```yaml
on:
  schedule:
    - cron: '0 9 * * *'  # 06:00 BRT
```

**Hook pós-run (qualquer opção):**
```
1. Upload checkpoint + run_summary para blob
2. Gerar DAILY_<TRIBUNAL>_YYYY-MM-DD.md
3. Se failed > 0: enviar alerta (email/webhook/issue)
4. Se new > 0: trigger pipeline de parsing (opcional)
5. Se updated > 0: log informativo + re-trigger parsing dos atualizados
```

---

## EXEMPLO PREENCHIDO — 1 dia (fake)

### `_config/delta_strategy.json` (TCE-MG)
```json
{
  "tribunal_id": "tce-mg",
  "strategy": "last_n_pages",
  "date_field": null,
  "safety_window_days": 14,
  "max_pages": 3,
  "rate_limit": {"requests_per_min": 10, "backoff_base_sec": 3},
  "keywords": ["licitação", "pregão", "contratação", "obra", "engenharia"],
  "relevance_filter": true,
  "notes": "Selenium obrigatório. chkColegiado=true. Cookie banner + CAPTCHA bypass."
}
```

### `_runs/2026-02-24/checkpoint.json`
```json
{
  "tribunal": "tce-mg",
  "last_date": "2026-02-24",
  "last_doc_ids": ["tce-mg--AC-2026-0412", "tce-mg--AC-2026-0411"],
  "previous_checkpoint": "2026-02-23",
  "window": {"from": "2026-02-10", "to": "2026-02-24"},
  "safety_window_days": 14
}
```

### `_runs/2026-02-24/run_summary.json`
```json
{
  "tribunal": "tce-mg",
  "date": "2026-02-24",
  "delta_strategy": "last_n_pages",
  "safety_window_days": 14,
  "delta_window": {"from": "2026-02-10", "to": "2026-02-24"},
  "counters": {
    "searched": 25,
    "new": 8,
    "updated": 1,
    "skipped": 12,
    "no_pdf": 2,
    "terminal_skip": 1,
    "failed": 0,
    "poison": 0
  },
  "duration_seconds": 347,
  "rate_items_per_min": 4.32,
  "checkpoint_updated": true,
  "new_blobs": [
    "juris-raw/tce-mg/acordaos/tce-mg--AC-2026-0412/decisao.pdf",
    "juris-raw/tce-mg/acordaos/tce-mg--AC-2026-0412/metadata.json"
  ],
  "updated_blobs": [
    {
      "blob": "juris-raw/tce-mg/acordaos/tce-mg--AC-2026-0390/decisao.pdf",
      "previous_sha256": "a1b2c3...",
      "new_sha256": "d4e5f6...",
      "reason": "tribunal_republished"
    }
  ],
  "terminal_skips": [
    {"doc_id": "tce-mg--AT-2026-0089", "reason": "non_decision_attachment", "type": "despacho"}
  ],
  "no_pdf_items": [
    {"doc_id": "tce-mg--AC-2026-0410", "reason": "404_genuine"},
    {"doc_id": "tce-mg--AC-2026-0409", "reason": "pdf_not_available_yet"}
  ]
}
```

### `outputs/DAILY_TCE-MG_2026-02-24.md`
```markdown
# DAILY TCE-MG — 2026-02-24

## Config
- Strategy: `last_n_pages` (3 páginas)
- Janela de segurança: 14 dias (2026-02-10 → 2026-02-24)

## Resumo
| Métrica | Valor |
|---------|-------|
| Buscados | 25 |
| Novos | 8 |
| Atualizados (SHA diff) | 1 |
| Skipped (já existia) | 12 |
| No PDF | 2 |
| Terminal skip | 1 |
| Failed | **0** |
| Poison | **0** |
| Duração | 5m47s |
| Taxa | 4.32 items/min |

## Decisões
- **8 novos acordãos** baixados (fev/2026)
- **1 atualizado**: AC-2026-0390 (tribunal republicou PDF com correção)
- **12 já existiam** no blob com SHA idêntico
- **2 sem PDF**: AC-2026-0410 (404 genuíno), AC-2026-0409 (ainda não publicado)
- **1 terminal_skip**: AT-2026-0089 (despacho, não é decisão)

## Alertas
- Nenhum alerta. Run saudável.
- 1 update detectado (AC-2026-0390) — informativo, não é anomalia.

## Spot-check (3 novos + 1 updated)
| doc_id | PDF válido | SHA match | tribunal | uf | score |
|--------|-----------|-----------|----------|----|-------|
| AC-2026-0412 | PASS (142KB) | PASS | TCE | MG | 0.85 |
| AC-2026-0411 | PASS (98KB) | PASS | TCE | MG | 0.85 |
| AC-2026-0408 | PASS (203KB) | PASS | TCE | MG | 0.85 |
| AC-2026-0390 (upd) | PASS (155KB) | PASS (new SHA) | TCE | MG | 0.85 |

## Checkpoint
- Anterior: 2026-02-23
- Novo: 2026-02-24
- Janela: 2026-02-10 → 2026-02-24 (14 dias)
```
