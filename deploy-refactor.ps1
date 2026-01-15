# Deploy Refatoração Govy - Método Otimizado
# Execução: .\deploy-refactor.ps1

$ErrorActionPreference = "Stop"

Write-Host "🚀 DEPLOY DA REFATORAÇÃO GOVY" -ForegroundColor Cyan
Write-Host "================================`n"

# Configuração
$resourceGroup = "rg-govy-parse-test-sponsor"
$functionAppName = "func-govy-parse-test"
$zipFile = "deploy.zip"

# Verificar se ZIP existe
if (-not (Test-Path $zipFile)) {
    Write-Host "❌ Arquivo $zipFile não encontrado!" -ForegroundColor Red
    exit 1
}

Write-Host "📦 Arquivo ZIP encontrado: $zipFile"
$zipSize = (Get-Item $zipFile).Length / 1MB
Write-Host "   Tamanho: $([math]::Round($zipSize, 2)) MB`n"

# Método 1: Kudu API (mais confiável)
Write-Host "🔧 MÉTODO 1: Deploy via Kudu API" -ForegroundColor Yellow
Write-Host "-----------------------------------"

try {
    Write-Host "   Obtendo credenciais..."
    $creds = az functionapp deployment list-publishing-credentials `
        --name $functionAppName `
        --resource-group $resourceGroup | ConvertFrom-Json
    
    $username = $creds.publishingUserName
    $password = $creds.publishingPassword
    $base64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${username}:${password}"))
    
    $kuduUrl = "https://${functionAppName}.scm.azurewebsites.net/api/zipdeploy"
    
    Write-Host "   Fazendo upload..."
    $headers = @{
        Authorization = "Basic $base64"
    }
    
    $response = Invoke-RestMethod -Uri $kuduUrl `
        -Method POST `
        -Headers $headers `
        -InFile $zipFile `
        -ContentType "application/zip" `
        -TimeoutSec 300
    
    Write-Host "✅ Deploy via Kudu concluído!" -ForegroundColor Green
    $deployMethod = "kudu"
    
} catch {
    Write-Host "⚠️  Kudu falhou: $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host "`n🔧 MÉTODO 2: Azure CLI (fallback)" -ForegroundColor Yellow
    Write-Host "-----------------------------------"
    
    try {
        az functionapp deployment source config-zip `
            --resource-group $resourceGroup `
            --name $functionAppName `
            --src $zipFile `
            --timeout 300
        
        Write-Host "✅ Deploy via Azure CLI concluído!" -ForegroundColor Green
        $deployMethod = "cli"
        
    } catch {
        Write-Host "❌ Ambos os métodos falharam!" -ForegroundColor Red
        Write-Host "Erro: $($_.Exception.Message)"
        exit 1
    }
}

Write-Host "`n🔍 PÓS-DEPLOY: Verificações" -ForegroundColor Cyan
Write-Host "================================`n"

Write-Host "1️⃣ Verificando WEBSITE_RUN_FROM_PACKAGE..."
$websiteRunFromPackage = az functionapp config appsettings list `
    --name $functionAppName `
    --resource-group $resourceGroup `
    --query "[?name=='WEBSITE_RUN_FROM_PACKAGE']" | ConvertFrom-Json

if ($websiteRunFromPackage.Count -gt 0) {
    Write-Host "   ⚠️  WEBSITE_RUN_FROM_PACKAGE encontrada! Deletando..." -ForegroundColor Yellow
    az functionapp config appsettings delete `
        --name $functionAppName `
        --resource-group $resourceGroup `
        --setting-names WEBSITE_RUN_FROM_PACKAGE | Out-Null
    Write-Host "   ✅ Deletada com sucesso!" -ForegroundColor Green
} else {
    Write-Host "   ✅ WEBSITE_RUN_FROM_PACKAGE não existe (correto)" -ForegroundColor Green
}

Write-Host "`n2️⃣ Reiniciando Function App..."
az functionapp restart `
    --name $functionAppName `
    --resource-group $resourceGroup | Out-Null
Write-Host "   ✅ Restart concluído!" -ForegroundColor Green

Write-Host "`n⏳ Aguardando 30 segundos para startup..."
Start-Sleep -Seconds 30

Write-Host "`n3️⃣ Testando endpoint /api/ping..."
try {
    $pingUrl = "https://func-govy-parse-test-exabasfqgsfgexhd.eastus-01.azurewebsites.net/api/ping"
    $pingResponse = Invoke-RestMethod -Uri $pingUrl -Method GET -TimeoutSec 10
    
    if ($pingResponse -eq "pong") {
        Write-Host "   ✅ Ping OK: $pingResponse" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  Resposta inesperada: $pingResponse" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ❌ Ping falhou: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host "`n4️⃣ Verificando functions carregadas..."
$functions = az functionapp function list `
    --name $functionAppName `
    --resource-group $resourceGroup `
    --output json | ConvertFrom-Json

Write-Host "   Functions encontradas: $($functions.Count)"
foreach ($func in $functions) {
    Write-Host "   - $($func.name)" -ForegroundColor Gray
}

if ($functions.Count -eq 5) {
    Write-Host "   ✅ Todas as 5 functions carregadas!" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  Esperadas 5 functions, encontradas $($functions.Count)" -ForegroundColor Yellow
}

Write-Host "`n📊 RESUMO DO DEPLOY" -ForegroundColor Cyan
Write-Host "================================"
Write-Host "Método usado: $deployMethod"
Write-Host "Functions carregadas: $($functions.Count)/5"
Write-Host "WEBSITE_RUN_FROM_PACKAGE: $(if ($websiteRunFromPackage.Count -gt 0) {'DELETADA ✅'} else {'NÃO EXISTE ✅'})"
Write-Host "`n🎯 PRÓXIMOS PASSOS:" -ForegroundColor Green
Write-Host "1. Executar: .\govy.ps1 testar"
Write-Host "2. Verificar se os 4 parâmetros são extraídos corretamente"
Write-Host "3. Se tudo OK, a refatoração está completa! 🎉`n"
