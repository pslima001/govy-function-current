# ============================================================================
# DEPLOY CORRETO - GOVY Azure Functions
# ============================================================================
# Este script usa o comando OFICIAL do Azure Functions Core Tools
# Garante que SOMENTE os arquivos Python são enviados, SEM .venv

Write-Host "===================================" -ForegroundColor Cyan
Write-Host "  DEPLOY GOVY - MÉTODO CORRETO" -ForegroundColor Cyan
Write-Host "===================================" -ForegroundColor Cyan
Write-Host ""

# 1. Verificar se está no diretório correto
$currentDir = Get-Location
if (-not (Test-Path "function_app.py")) {
    Write-Host "ERRO: Execute este script de C:\govy\repos\govy-function-current\" -ForegroundColor Red
    exit 1
}

Write-Host "[1/4] Validando ambiente..." -ForegroundColor Yellow

# 2. Verificar se func está instalado
try {
    $funcVersion = func --version
    Write-Host "  Azure Functions Core Tools: $funcVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERRO: Azure Functions Core Tools não encontrado!" -ForegroundColor Red
    Write-Host "  Instale: https://learn.microsoft.com/azure/azure-functions/functions-run-local" -ForegroundColor Yellow
    exit 1
}

# 3. Verificar pasta govy
if (-not (Test-Path "govy")) {
    Write-Host "  ERRO: Pasta govy/ não encontrada!" -ForegroundColor Red
    exit 1
}

Write-Host "  Pasta govy/: OK" -ForegroundColor Green
Write-Host "  function_app.py: OK" -ForegroundColor Green
Write-Host ""

# 4. Criar .funcignore se não existir
Write-Host "[2/4] Configurando exclusões..." -ForegroundColor Yellow

$funcignoreContent = @"
.git*
.vscode
local.settings.json
test
.venv
__pycache__
*.pyc
.python_packages
.pytest_cache
backups
docs
scripts
deploy*.ps1
*.md
*.zip
review_queue
"@

$funcignoreContent | Out-File -FilePath ".funcignore" -Encoding utf8 -Force
Write-Host "  .funcignore atualizado" -ForegroundColor Green
Write-Host ""

# 5. DEPLOY usando func CLI
Write-Host "[3/4] Executando deploy..." -ForegroundColor Yellow
Write-Host "  Método: func azure functionapp publish" -ForegroundColor Cyan
Write-Host "  Target: func-govy-parse-test" -ForegroundColor Cyan
Write-Host "  Build: --build remote (SCM_DO_BUILD_DURING_DEPLOYMENT=true)" -ForegroundColor Cyan
Write-Host ""

# Executar deploy
func azure functionapp publish func-govy-parse-test --build remote

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "ERRO no deploy!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[4/4] Reiniciando Function App..." -ForegroundColor Yellow
az functionapp restart --name func-govy-parse-test --resource-group rg-govy-parse-test-sponsor

Write-Host ""
Write-Host "===================================" -ForegroundColor Green
Write-Host "  DEPLOY CONCLUÍDO COM SUCESSO!" -ForegroundColor Green
Write-Host "===================================" -ForegroundColor Green
Write-Host ""
Write-Host "PRÓXIMOS PASSOS:" -ForegroundColor Cyan
Write-Host "1. Aguarde 2-3 minutos (cold start)" -ForegroundColor White
Write-Host "2. Teste o endpoint diagnóstico:" -ForegroundColor White
Write-Host "   https://func-govy-parse-test-exabasfqgsfgexhd.eastus-01.azurewebsites.net/api/diagnostic_full" -ForegroundColor Yellow
Write-Host ""
Write-Host "3. Ou teste /api/ingest_doctrine com um documento:" -ForegroundColor White
Write-Host "   POST https://func-govy-parse-test-exabasfqgsfgexhd.eastus-01.azurewebsites.net/api/ingest_doctrine" -ForegroundColor Yellow
Write-Host ""
