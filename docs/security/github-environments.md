# GitHub Environments — Production Gate

Data: 2026-02-19

## Overview

O workflow `deploy-fixed.yml` usa `environment: production` para exigir aprovacao manual antes de cada deploy para Azure Functions.

## Configuracao (manual no GitHub UI)

1. Ir para `https://github.com/pslima001/govy-function-current/settings/environments`
2. Clicar "New environment" → nome: `production`
3. Configurar:
   - **Required reviewers**: adicionar o owner do repo (Paulo)
   - **Wait timer**: 0 (ou delay desejado)
   - **Deployment branches**: selecionar "Selected branches" → `main`

## Comportamento

- Quando um push para main dispara o deploy, o workflow **pausa** e aguarda aprovacao
- O reviewer recebe notificacao no GitHub e pode aprovar ou rejeitar
- Somente apos aprovacao o deploy continua (OIDC login → zip deploy → smoke tests)

## Secrets no Environment

Os OIDC credentials (client-id, tenant-id, subscription-id) estao **hardcoded no YAML**, nao em secrets. Portanto nao precisam ser duplicados no environment.

Os smoke test secrets (`AZURE_FUNCTION_BASE_URL`, `AZURE_FUNCTION_KEY`) estao em repo-level secrets e sao acessiveis pelo environment `production` por padrao.

Se desejar restringir secrets ao environment (mais seguro):
1. Mover os secrets de repo-level para environment-level em Settings → Environments → production → Secrets
2. Isso garante que apenas o deploy workflow em `production` pode acessar a function key

## Nota

Se o environment `production` nao existir quando o workflow rodar, o GitHub auto-cria o environment SEM protection rules. O deploy nao sera bloqueado, mas o gate nao tera efeito ate as rules serem configuradas manualmente.
