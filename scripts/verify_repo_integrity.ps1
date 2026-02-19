#Requires -Version 5.1
<#
.SYNOPSIS
    Verifica integridade do repositório GOVY antes de commit/PR.
.DESCRIPTION
    - Confirma repo correto
    - Bloqueia commits em main
    - Detecta arquivos fora dos paths permitidos
    - Roda ruff lint + format + pytest
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$exitCode = 0

function Fail($msg) {
    Write-Host "FAIL: $msg" -ForegroundColor Red
    $script:exitCode = 1
}

function Pass($msg) {
    Write-Host "OK:   $msg" -ForegroundColor Green
}

# ── 1. Repo correto ──────────────────────────────────────────────────────────
$toplevel = (git rev-parse --show-toplevel 2>&1).Trim().Replace('\', '/')
if ($toplevel -notlike "*govy-function-current*") {
    Fail "Repo errado: $toplevel (esperado *govy-function-current*)"
} else {
    Pass "Repo: $toplevel"
}

# ── 2. Nao esta em main ──────────────────────────────────────────────────────
$branch = (git branch --show-current 2>&1).Trim()
if ($branch -eq "main") {
    Fail "Branch atual e 'main'. Crie uma feature branch."
} else {
    Pass "Branch: $branch"
}

# ── 3. Arquivos nao rastreados fora de paths permitidos ──────────────────────
$allowedPrefixes = @(
    "govy/", "tests/", "docs/", "scripts/", ".github/",
    "ruff.toml", "requirements.txt", "pyproject.toml",
    ".pre-commit-config.yaml", ".claude/"
)

$untracked = git status --porcelain 2>&1 | Where-Object { $_ -match '^\?\?' }
foreach ($line in $untracked) {
    $file = ($line -replace '^\?\?\s+', '').Trim()
    $allowed = $false
    foreach ($prefix in $allowedPrefixes) {
        if ($file.StartsWith($prefix)) { $allowed = $true; break }
    }
    if (-not $allowed) {
        Fail "Arquivo fora do escopo: $file"
    }
}
if ($exitCode -eq 0) { Pass "Nenhum arquivo fora do escopo" }

# ── 4. Ruff lint ─────────────────────────────────────────────────────────────
Write-Host "`n--- Ruff lint ---" -ForegroundColor Cyan
$lintPaths = @(
    "govy/utils/juris_*.py",
    "govy/doctrine/*.py",
    "tests/test_juris_*.py",
    "tests/test_doctrine_*.py"
)
$lintArgs = @("check") + $lintPaths
& python -m ruff @lintArgs
if ($LASTEXITCODE -ne 0) { Fail "ruff check falhou" } else { Pass "ruff check" }

# ── 5. Ruff format ───────────────────────────────────────────────────────────
Write-Host "`n--- Ruff format ---" -ForegroundColor Cyan
$fmtArgs = @("format", "--check") + $lintPaths
& python -m ruff @fmtArgs
if ($LASTEXITCODE -ne 0) { Fail "ruff format --check falhou" } else { Pass "ruff format" }

# ── 6. Pytest ─────────────────────────────────────────────────────────────────
Write-Host "`n--- Pytest ---" -ForegroundColor Cyan
$testPaths = @(
    "tests/test_juris_*.py",
    "tests/test_doctrine_*.py"
)
& python -m pytest @testPaths -q --tb=short
if ($LASTEXITCODE -ne 0) { Fail "pytest falhou" } else { Pass "pytest" }

# ── Resultado ─────────────────────────────────────────────────────────────────
Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "RESULTADO: TUDO OK" -ForegroundColor Green
} else {
    Write-Host "RESULTADO: FALHOU — corrija antes do PR" -ForegroundColor Red
}
exit $exitCode
