# Security Checks in CI

Data: 2026-02-19

## Overview

O workflow `CI - Lint & Test` inclui checks de seguranca que rodam em todo PR e push para main.

## gitleaks — Secret Scanning

**Action**: `gitleaks/gitleaks-action@v2`
**Mode**: hard-fail (bloqueia PR se encontrar segredo)

Varre o diff do PR (ou commit) procurando segredos vazados (API keys, tokens, connection strings).

### Allowlist

Configurada em `.gitleaks.toml` na raiz do repo. Paths permitidos:
- `backups/` — codigo legado arquivado
- `scripts/migrate_tce_sp.py` — template de connection string (nao e secret real)
- `scripts/doctrine_batch_*.py` — scripts offline de batch
- `scripts/kb/` — scripts offline de indexacao
- `kb_content_hub/` — codigo de referencia/staging
- `tests/contract/` — testes de contrato

Para adicionar um novo path a allowlist, editar `.gitleaks.toml` e documentar a justificativa.

## pip-audit — Vulnerability Scanning

**Mode**: soft-fail (warning, nao bloqueia PR)

Roda `pip-audit -r requirements.txt` para verificar CVEs conhecidos nas dependencias.

### Por que soft-fail?

`cryptography==41.0.7` tem CVEs conhecidos mas e a versao pinada por compatibilidade com o Azure SDK. Upgrade requer teste de regressao dedicado.

### Quando migrar para hard-fail?

Quando `cryptography` for atualizado e todas as vulnerabilidades criticas forem resolvidas. Criar ticket dedicado para isso.

## Anti-regression auth check

Documentado em `docs/security/storage-auth.md` (secao "Anti-regression CI check").
