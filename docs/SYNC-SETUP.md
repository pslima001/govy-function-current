# GOVY — Setup Sync Entre Computadores

## Como funciona

- Branch `wip/local` = branch de trabalho compartilhada entre maquinas
- Hook `Stop` do Claude Code = auto-commit + push ao final de cada resposta
- Nenhuma acao humana necessaria apos setup inicial

## Setup no novo computador (unica vez)

### 1. Clone o repo

```bash
git clone https://github.com/pslima001/govy-function-current.git
cd govy-function-current
git checkout wip/local
```

### 2. Crie o settings.local.json (secrets locais)

```bash
mkdir -p .claude
```

Crie `.claude/settings.local.json` com suas permissoes locais (NAO commitar):

```json
{
  "permissions": {
    "allow": [
      "Bash(python:*)",
      "Bash(git:*)"
    ]
  }
}
```

### 3. Verifique que o hook funciona

```bash
cat .claude/settings.json
# Deve mostrar o hook Stop com govy-sync.sh
```

### 4. Teste o sync manual

```bash
bash scripts/govy-sync.sh pull   # puxa mudancas do outro PC
bash scripts/govy-sync.sh push   # envia suas mudancas
bash scripts/govy-sync.sh full   # pull + push (padrao)
```

## Workflow diario

1. **Abrir Claude Code** no diretorio do projeto
2. **Trabalhar normalmente** — o hook `Stop` cuida do sync
3. **Trocar de PC**: abrir Claude Code no outro — ele puxa automaticamente via hook

## Troubleshooting

### "Not on wip/local"

```bash
git checkout wip/local
```

### Conflito de merge

```bash
git status                    # ver arquivos em conflito
# resolver manualmente
git add -A && git rebase --continue
```

### Push rejeitado (outro PC pushou antes)

```bash
bash scripts/govy-sync.sh full   # pull + push resolve isso
```

### Forcar sync manual

```bash
bash scripts/govy-sync.sh full
```

## Arquivos protegidos (NUNCA no git)

| Arquivo | Motivo |
|---|---|
| `snapshots/appsettings.json` | API keys e connection strings |
| `.claude/settings.local.json` | Permissoes com secrets locais |
| `outputs/audit_*.json` | Efemeros, regeneraveis |
| `outputs/parse_*_batch.json` | Efemeros, regeneraveis |
| `out/` | Scripts debug avulsos |

## Arquivos que SIM sincronizam

- `blueprints/` (nova arquitetura)
- `configs/` (policies)
- `scripts/` (batch, sync)
- `govy/` (todo o codigo)
- `packages/` (reestruturacao)
- `tests/`
- `outputs/REPORT_FINAL_*.md` (evidencia de fechamento)
- `.claude/settings.json` (hooks compartilhados)
