# Storage Authentication Architecture

Data: 2026-02-18
Status: **Option 3 (Hybrid)** — app code usa MI, runtime usa connection string.

## Resumo

A Function App `func-govy-parse-test` foi migrada para usar **DefaultAzureCredential**
(Managed Identity) em todo o codigo aplicativo. O runtime do Azure Functions continua
usando connection string (`AzureWebJobsStorage`) porque o Linux Consumption Plan
nao suporta identity-based storage para montagem do pacote de deploy.

## O que esta seguro

| Componente | Autenticacao | Status |
|------------|-------------|--------|
| App code (17 arquivos) | DefaultAzureCredential (MI) | Migrado |
| `govy/utils/azure_clients.py` | Singleton BlobServiceClient com MI | Criado |
| `AZURE_STORAGE_CONNECTION_STRING` | **Removido** dos App Settings | Removido |
| `GOVY_STORAGE_ACCOUNT` | Account name (sem segredo) | Ativo |
| Managed Identity | SystemAssigned, principalId: `ba66c30e-...` | Ativo |

### RBAC da Managed Identity em `stgovyparsetestsponsor`

| Role | Scope |
|------|-------|
| Storage Blob Data Contributor | Storage Account |
| Storage Queue Data Contributor | Storage Account |
| Storage Table Data Contributor | Storage Account |

## O que ainda usa connection string (e por que)

### `AzureWebJobsStorage` (runtime)

- **Motivo**: O Linux Consumption Plan depende desta connection string para montar
  o pacote de deploy (squashfs) e gerenciar triggers, locks, e estado do host.
- **Tentativa**: Em 2026-02-18, testamos a migracao para identity-based
  (`AzureWebJobsStorage__accountName` + URIs). Resultado: host subiu, mas todos os
  endpoints retornaram 404 (funcoes nao carregadas). Rollback imediato, app restaurada.
- **Decisao**: Manter connection string para o runtime ate que o plano de hosting
  seja alterado (ver Plano Futuro).

### `TCE_STORAGE_CONNECTION` (outro storage account)

- **Motivo**: Acessa `sttcejurisprudencia`, um storage account separado usado pelo
  pipeline de jurisprudencia do TCE.
- **Escopo**: Usado apenas em `govy/api/tce_queue_handler.py` (`_get_tce_blob_service()`).
- **Migracao futura**: Requer habilitar MI no `sttcejurisprudencia` e atribuir RBAC.

## Por que nao desabilitamos shared keys

Desabilitar `--allow-shared-key-access false` no `stgovyparsetestsponsor` quebraria
o `AzureWebJobsStorage` do runtime (que usa account key). Tentativa prematura em
2026-02-18 foi revertida imediatamente.

## Plano futuro para hardening total

Duas opcoes mutuamente exclusivas:

### Opcao A: Separar runtime storage

1. Criar um storage account dedicado ao runtime (ex: `stgovyruntime`)
2. Mover `AzureWebJobsStorage` para apontar para `stgovyruntime`
3. Desabilitar shared keys em `stgovyparsetestsponsor` (dados)
4. Manter shared keys habilitadas em `stgovyruntime` (runtime)

### Opcao B: Migrar para Elastic Premium / Dedicated

1. Migrar Function App para plano Elastic Premium ou Dedicated (App Service Plan)
2. Repetir Phase 4 (identity-based `AzureWebJobsStorage`)
3. Desabilitar shared keys em `stgovyparsetestsponsor`

### Prerequisitos para qualquer opcao

- Avaliar impacto de custo (Elastic Premium vs Consumption)
- Testar em ambiente de staging antes de producao
- Migrar `TCE_STORAGE_CONNECTION` para MI (requer RBAC em `sttcejurisprudencia`)

## Cronologia

| Data | Acao | Resultado |
|------|------|-----------|
| 2026-02-18 | Backup `$web` para `backup-web/web-20260218/` | OK |
| 2026-02-18 | SWA `swa-tribunals-console` criado | OK |
| 2026-02-18 | MI habilitada + RBAC atribuido | OK |
| 2026-02-18 | 17 arquivos migrados para DefaultAzureCredential | OK |
| 2026-02-18 | Deploy com remote build (commit `635180b`) | OK |
| 2026-02-18 | Smoke tests READ/WRITE/DELETE | OK |
| 2026-02-18 | Phase 4 (identity-based runtime) tentada | FAIL (404) |
| 2026-02-18 | Rollback Phase 4 | OK |
| 2026-02-18 | Phase 5: `AZURE_STORAGE_CONNECTION_STRING` removido | OK |
| 2026-02-18 | Smoke tests pos-Phase 5 | OK |

## Anti-regression CI check

O script `scripts/check_no_connection_strings.py` roda no CI em todo PR e push para main.

**O que faz**: varre `govy/**/*.py` e `function_app.py` procurando `from_connection_string(` e `DefaultEndpointsProtocol=.*AccountKey=`.

**Sentinel comment**: usos intencionais devem ter `# ALLOW_CONNECTION_STRING_OK` na mesma linha ou na linha anterior. Sem sentinel = violacao = CI falha.

**Usos permitidos atualmente**:
- `govy/api/tce_queue_handler.py` — acesso ao storage `sttcejurisprudencia` (GOV-29)
- `function_app.py` — 5 usos em endpoints de teste/queue (TCE + AzureWebJobsStorage)
