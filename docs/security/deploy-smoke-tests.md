# Deploy Smoke Tests

Data: 2026-02-19

## Overview

Apos cada deploy para Azure Functions, o workflow `deploy-fixed.yml` executa smoke tests automaticos via `scripts/smoke_test_endpoints.py`.

## Endpoints testados

| # | Endpoint | Metodo | Assertion |
|---|----------|--------|-----------|
| 1 | `/api/ping` | GET | status 200, body contem "pong" |
| 2 | `/api/dicionario?stats=true` | GET | status 200, JSON com `"success": true` |

## Comportamento

- **Timeout**: 15s por request
- **Retries**: 3 tentativas com backoff (10s, 20s, 30s) para tolerar cold start
- **Soft-skip**: se `BASE_URL` ou `FUNC_KEY` nao estiverem configurados, o script sai com exit 0 e warning (nao bloqueia deploy)
- **Diagnostico**: em caso de falha, imprime URL, status code e body (truncado em 2KB)

## Secrets necessarios

Configurar em GitHub → Settings → Secrets and variables → Actions:

| Secret | Valor |
|--------|-------|
| `AZURE_FUNCTION_BASE_URL` | `https://func-govy-parse-test-exabasfqgsfgexhd.eastus-01.azurewebsites.net` |
| `AZURE_FUNCTION_KEY` | Function key do Azure portal (obter via `az functionapp keys list`) |

## Como obter a function key

```bash
az functionapp keys list \
  --name func-govy-parse-test \
  --resource-group rg-govy-parse-test-sponsor \
  --query "functionKeys.default" -o tsv
```
