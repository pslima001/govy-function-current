#Requires -Version 5.1
<#
.SYNOPSIS
    Verificacao de sanidade do ambiente de desenvolvimento GOVY.
.DESCRIPTION
    Roda antes de iniciar qualquer tarefa. Falha se algo estiver errado:
    - git status limpo
    - branch nao e main
    - python disponivel
    - claude --version == estavel (npm)
    - where.exe claude nao aponta para .local\bin (standalone/canary)
    - ruff e pytest disponiveis
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"

$exitCode = 0

function Fail($msg) {
    Write-Host "FAIL: $msg" -ForegroundColor Red
    $script:exitCode = 1
}

function Pass($msg) {
    Write-Host "OK:   $msg" -ForegroundColor Green
}

function Warn($msg) {
    Write-Host "WARN: $msg" -ForegroundColor Yellow
}

Write-Host "=== GOVY Dev Sanity Check ===" -ForegroundColor Cyan
Write-Host ""

# -- 1. Git status (nao pode ter alteracoes pendentes) ----------------------------
$dirty = git status --porcelain 2>&1
if ($dirty) {
    Warn "Working tree tem alteracoes. Considere commit ou stash antes de iniciar tarefa."
    Write-Host "       $($dirty | Select-Object -First 5 | Out-String)" -ForegroundColor DarkGray
} else {
    Pass "Working tree limpa"
}

# -- 2. Branch nao pode ser main ---------------------------------------------------
$branch = (git branch --show-current 2>&1).Trim()
if ($branch -eq "main") {
    Fail "Branch atual e 'main'. Crie uma feature branch: git checkout -b feat/<nome>"
} else {
    Pass "Branch: $branch"
}

# -- 3. Python disponivel ----------------------------------------------------------
try {
    $pyVer = & python --version 2>&1
    if ($pyVer -match "Python \d+\.\d+") {
        Pass "Python: $pyVer"
    } else {
        # Fallback: try python3
        $pyVer = & python3 --version 2>&1
        if ($pyVer -match "Python \d+\.\d+") {
            Pass "Python (python3): $pyVer"
        } else {
            Fail "Python nao encontrado ou retornou saida inesperada: $pyVer"
        }
    }
} catch {
    Fail "Python nao encontrado no PATH"
}

# -- 4. Claude Code versao ---------------------------------------------------------
try {
    $claudeVer = & claude --version 2>&1
    if ($claudeVer -match "\d+\.\d+\.\d+") {
        Pass "Claude Code: $claudeVer"
    } else {
        Fail "claude --version retornou saida inesperada: $claudeVer"
    }
} catch {
    Fail "Claude Code nao encontrado no PATH"
}

# -- 5. Claude Code NAO pode ser standalone (.local\bin) ---------------------------
try {
    $claudePaths = & where.exe claude 2>&1
    foreach ($p in $claudePaths) {
        if ($p -match '\.local\\bin\\claude') {
            Fail "Claude standalone detectado: $p — desinstale ou renomeie (ver docs/dev-environment.md)"
        }
    }
    if ($exitCode -eq 0 -or -not ($claudePaths -match '\.local\\bin\\claude')) {
        Pass "Claude Code path OK (sem standalone em .local\bin)"
    }
} catch {
    Warn "Nao foi possivel verificar path do Claude"
}

# -- 6. Ruff disponivel ------------------------------------------------------------
try {
    $ruffVer = & ruff --version 2>&1
    if ($ruffVer -match "\d+\.\d+") {
        Pass "Ruff: $ruffVer"
    } else {
        Fail "ruff --version retornou saida inesperada: $ruffVer"
    }
} catch {
    Fail "Ruff nao encontrado. Instale: pip install ruff"
}

# -- 7. Pytest disponivel ----------------------------------------------------------
try {
    $pytestVer = & pytest --version 2>&1
    if ($pytestVer -match "\d+\.\d+") {
        Pass "Pytest: $pytestVer"
    } else {
        Fail "pytest --version retornou saida inesperada: $pytestVer"
    }
} catch {
    Fail "Pytest nao encontrado. Instale: pip install pytest"
}

# -- Resultado ---------------------------------------------------------------------
Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "RESULTADO: AMBIENTE OK — pode comecar a trabalhar." -ForegroundColor Green
} else {
    Write-Host "RESULTADO: PROBLEMAS DETECTADOS — corrija antes de continuar." -ForegroundColor Red
}

exit $exitCode
