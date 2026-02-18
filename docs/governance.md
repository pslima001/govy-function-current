# Governance — GOVY Repository

> Regra #1: nenhum codigo "existe" ate estar no GitHub (branch + PR merged).

## Fluxo Obrigatorio

```text
1. git checkout main && git pull
2. git checkout -b feat/<nome>
3. Mudancas pequenas e focadas
4. Rodar ruff / pytest / pre-commit antes do commit
5. git push -u origin feat/<nome>
6. Abrir PR contra main
7. CI verde (lint-and-test)
8. Merge (squash + delete branch)
```

## Branch Protection (main)

| Regra | Status |
|-------|--------|
| PR obrigatorio | Ativo |
| CI obrigatoria (lint-and-test) | Ativo |
| Branch atualizada antes de merge | Ativo |
| Resolucao de conversas | Ativo |
| Force push bloqueado | Ativo |

## Convencoes de Commit

Formato: conventional commits.

```
feat:   nova funcionalidade
fix:    correcao de bug
chore:  tarefas de manutencao
test:   adicao/correcao de testes
ci:     mudancas no CI/CD
docs:   documentacao
```

Co-author line obrigatoria quando assistido por IA:
```
Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

## Naming de Branches

Padrao: `feat/<feature-name>`

Exemplos:
- `feat/kb-pipeline-phase2`
- `feat/governance-consolidation`
- `fix/juris-regex-edge-case`

## CI Deterministico

O workflow `lint-and-test` roda:
- `ruff check` nos paths do KB pipeline
- `ruff format --check` nos mesmos paths
- `pytest` nos testes correspondentes

Paths cobertos pelo CI:
- `govy/utils/juris_*.py`
- `tests/test_juris_*.py`

O CI **nao** pega codigo legado (backups/, govy/api/, govy/extractors/, etc.).

## Testes Obrigatorios

Toda mudanca em `govy/utils/juris_*.py` deve ter teste correspondente em `tests/test_juris_*.py`.

## Trabalho Local

- **Proibido** trabalhar fora do repo (Desktop, Downloads, etc.).
- Rascunhos temporarios: usar `notes/` dentro do repo (incluido no `.gitignore`).
- Antes de iniciar qualquer tarefa: rodar `scripts/dev_sanity_check.ps1`.

## Sanity Check

Antes de commitar, rodar:

```powershell
.\scripts\dev_sanity_check.ps1
```

Este script verifica:
- Working tree limpa
- Branch nao e main
- Python, ruff, pytest disponiveis
- Claude Code na versao correta (estavel, nao canary)

## Merge Strategy

- Squash merge
- Deletar branch apos merge
- Verificar CI pos-merge: `gh run list --limit 5`
