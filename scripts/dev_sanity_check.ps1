#Requires -Version 5.1
<#
.SYNOPSIS
    Verificacao de sanidade do ambiente de desenvolvimento GOVY.
.DESCRIPTION
    Roda antes de iniciar qualquer tarefa.
    FALHA (exit 1) se qualquer check nao passar.
    EXIT 0 somente quando TUDO estiver correto.
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

Write-Host "=== GOVY Dev Sanity Check ===" -ForegroundColor Cyan
Write-Host ""

# -- 1. Repo correto ---------------------------------------------------------------
$toplevel = (git rev-parse --show-toplevel 2>&1).Trim().Replace('\', '/')
if ($toplevel -notlike "*govy-function-current*") {
    Fail "Repo errado: $toplevel (esperado *govy-function-current*)"
} else {
    Pass "Repo: $toplevel"
}

# -- 2. Branch nao pode ser main ---------------------------------------------------
$branch = (git branch --show-current 2>&1).Trim()
if ($branch -eq "main") {
    Fail "Branch atual e 'main'. Crie feature branch: git checkout -b feat/<nome>"
} else {
    Pass "Branch: $branch"
}

# -- 3. Working tree limpa (FAIL, nao warn) ----------------------------------------
$dirty = git status --porcelain 2>&1
if ($dirty) {
    Fail "Working tree suja. Commit ou stash antes de iniciar."
    $dirty | Select-Object -First 5 | ForEach-Object { Write-Host "       $_" -ForegroundColor DarkGray }
} else {
    Pass "Working tree limpa"
}

# -- 4. Python == 3.11.x -----------------------------------------------------------
$pyCmd = $null
$pyVer = $null
try {
    $pyVer = (& python --version 2>&1).ToString().Trim()
    if ($pyVer -match "Python 3\.11") { $pyCmd = "python" }
} catch {}
if (-not $pyCmd) {
    try {
        $pyVer = (& python3 --version 2>&1).ToString().Trim()
        if ($pyVer -match "Python 3\.11") { $pyCmd = "python3" }
    } catch {}
}
if ($pyCmd) {
    Pass "Python: $pyVer (via $pyCmd)"
} else {
    if ($pyVer) {
        Fail "Python versao errada: $pyVer (esperado 3.11.x)"
    } else {
        Fail "Python nao encontrado no PATH"
    }
}

# -- 5. Claude Code == 2.1.37 ------------------------------------------------------
$expectedClaude = "2.1.37"
try {
    $claudeRaw = (& claude --version 2>&1).ToString().Trim()
    # Extract version number (may include prefix text)
    if ($claudeRaw -match "(\d+\.\d+\.\d+)") {
        $claudeVer = $Matches[1]
        if ($claudeVer -eq $expectedClaude) {
            Pass "Claude Code: $claudeVer"
        } else {
            Fail "Claude Code versao errada: $claudeVer (esperado $expectedClaude)"
        }
    } else {
        Fail "claude --version retornou saida inesperada: $claudeRaw"
    }
} catch {
    Fail "Claude Code nao encontrado no PATH. Instale: npm install -g @anthropic-ai/claude-code@stable"
}

# -- 6. Claude standalone NAO pode estar no PATH -----------------------------------
try {
    $claudePaths = @(& where.exe claude 2>&1)
    $standaloneFound = $false
    foreach ($p in $claudePaths) {
        $pStr = $p.ToString()
        if ($pStr -match '\.local[\\/]bin[\\/]claude') {
            Fail "Claude standalone detectado: $pStr — desinstale (ver docs/dev-environment.md)"
            $standaloneFound = $true
        }
    }
    if (-not $standaloneFound) {
        Pass "Claude path OK (sem standalone em .local/bin)"
    }
} catch {
    Fail "Nao foi possivel verificar path do Claude (where.exe falhou)"
}

# -- 7. Ruff disponivel ------------------------------------------------------------
try {
    $ruffVer = (& ruff --version 2>&1).ToString().Trim()
    if ($ruffVer -match "\d+\.\d+") {
        Pass "Ruff: $ruffVer"
    } else {
        Fail "ruff --version retornou saida inesperada: $ruffVer"
    }
} catch {
    Fail "Ruff nao encontrado. Instale: pip install ruff"
}

# -- 8. Pytest disponivel ----------------------------------------------------------
try {
    $pytestVer = (& pytest --version 2>&1).ToString().Trim()
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
