# Criar o script diretamente no repositório
$scriptContent = @'
# ============================================================
# GOVY - Extrator de Parametros e Regex
# ============================================================

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   GOVY - Analise de Parametros/Regex" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

$RepoRoot = git rev-parse --show-toplevel 2>$null
if (-not $RepoRoot) {
    Write-Host "ERRO: Execute dentro do repositorio git" -ForegroundColor Red
    exit 1
}

Set-Location $RepoRoot
Write-Host "Repositorio: $RepoRoot`n" -ForegroundColor Gray

Write-Host ">>> params.json" -ForegroundColor Green
Write-Host "---------------------------------------------" -ForegroundColor Gray
if (Test-Path "params.json") {
    Get-Content "params.json" -Raw
} else {
    Write-Host "Arquivo nao encontrado" -ForegroundColor Red
}

Write-Host "`n>>> Estrutura de Arquivos .py" -ForegroundColor Green
Write-Host "---------------------------------------------" -ForegroundColor Gray
if (Test-Path "src") {
    Get-ChildItem -Path "src" -Recurse -File -Filter "*.py" | ForEach-Object {
        Write-Host "  $($_.FullName.Replace($RepoRoot, '').TrimStart('\'))" -ForegroundColor White
    }
}

Write-Host "`n>>> Conteudo dos Arquivos Python" -ForegroundColor Green
Write-Host "---------------------------------------------" -ForegroundColor Gray

$pyFiles = Get-ChildItem -Path "src" -Recurse -File -Filter "*.py" -ErrorAction SilentlyContinue
foreach ($file in $pyFiles) {
    $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
    if ($file.Name -eq "__init__.py" -and (!$content -or $content.Trim().Length -lt 10)) { continue }
    Write-Host "`n=== $($file.Name) ===" -ForegroundColor Cyan
    Write-Host $content
}

Write-Host "`n>>> function_app.py" -ForegroundColor Green
Write-Host "---------------------------------------------" -ForegroundColor Gray
if (Test-Path "function_app.py") {
    Get-Content "function_app.py" -Raw
}

Write-Host "`n>>> requirements.txt" -ForegroundColor Green
Write-Host "---------------------------------------------" -ForegroundColor Gray
if (Test-Path "requirements.txt") {
    Get-Content "requirements.txt" -Raw
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "   FIM - Cole a saida no chat Claude" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan
'@

[System.IO.File]::WriteAllText("$PWD\scripts\get-params-analysis.ps1", $scriptContent)
Write-Host "Script criado com sucesso!" -ForegroundColor Green

# Executar imediatamente
.\scripts\get-params-analysis.ps1
