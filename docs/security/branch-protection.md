# Branch Protection Hardening

Data: 2026-02-19

## Estado atual (antes do hardening)

| Setting | Valor |
|---------|-------|
| Required reviews | 0 |
| Enforce admins | **false** (admin faz bypass) |
| Required status checks | `lint-and-test` (strict) |
| Conversation resolution | true |
| Force push | bloqueado |
| Delete branch | permitido |

## Estado alvo (apos hardening)

| Setting | Valor |
|---------|-------|
| Required reviews | 0 (solo dev pode self-merge) |
| Enforce admins | **true** (ninguem faz bypass) |
| Require PR before merge | **true** |
| Required status checks | `lint-and-test` (strict) |
| Conversation resolution | true |
| Force push | bloqueado |
| Delete branch | bloqueado |

## Impacto

- **Nao e mais possivel push direto para main** (nem admin)
- Todas as mudancas passam por PR + CI green
- Solo dev (pslima001) pode fazer self-merge (reviews=0)
- CI `lint-and-test` deve passar antes do merge

## Como aplicar

```bash
bash scripts/harden_github_branch_protection.sh
```

Requisitos:
- `gh` CLI autenticado com permissoes de admin
- Executar APOS merge do PR de hardening

O script mostra o estado antes/depois para confirmacao.

## Procedimento de emergencia

Se um fix urgente for necessario e o CI estiver quebrado:
1. Admin vai para GitHub UI → Settings → Branches → main → Edit
2. Desabilitar temporariamente "Enforce admins"
3. Merge o fix via PR (sem esperar CI) ou push direto
4. Reabilitar "Enforce admins" imediatamente apos
5. Documentar o incidente
