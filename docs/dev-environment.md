# Dev Environment — GOVY

## Claude Code (instalacao padrao)

### Instalar via npm (UNICA forma aprovada)

```powershell
npm install -g @anthropic-ai/claude-code@stable
```

### Verificar instalacao

```powershell
where.exe claude
# Deve mostrar path do npm global (ex: C:\Users\<user>\AppData\Roaming\npm\claude)
# NAO deve mostrar C:\Users\<user>\.local\bin\claude.exe

claude --version
# Deve retornar versao estavel (ex: 2.1.37)
```

### Desinstalar/neutralizar standalone (canary)

Se `where.exe claude` mostrar `C:\Users\<user>\.local\bin\claude.exe`:

```powershell
# Opcao 1: renomear (preserva para rollback)
Rename-Item "$env:USERPROFILE\.local\bin\claude.exe" "claude.exe.bak"

# Opcao 2: remover
Remove-Item "$env:USERPROFILE\.local\bin\claude.exe"

# Verificar
where.exe claude
claude --version
```

### Por que evitar o standalone?

- A versao standalone (`~/.local/bin/claude.exe`) pode ser canary/instavel.
- Usa runtime Bun embutido que pode ter bugs.
- A versao npm e deterministica e controlada por `package.json` do npm global.

## Python

### Versao do projeto

Python 3.11 (conforme CI e `ruff.toml` target-version).

### Verificar

```powershell
python --version
# Se nao funcionar (Windows Store redirect), use:
python3 --version
```

## Ferramentas de qualidade

### Ruff (linter + formatter)

```powershell
pip install ruff
ruff --version

# Lint
ruff check govy/utils/juris_*.py tests/test_juris_*.py

# Format check
ruff format --check govy/utils/juris_*.py tests/test_juris_*.py
```

Configuracao em `ruff.toml` na raiz do repo.

### Pytest

```powershell
pip install pytest
pytest --version

# Rodar testes do KB pipeline
pytest tests/test_juris_*.py -q --tb=short
```

## Sanity Check

Antes de comecar qualquer tarefa, rode:

```powershell
.\scripts\dev_sanity_check.ps1
```

Este script verifica automaticamente todos os pontos acima.
