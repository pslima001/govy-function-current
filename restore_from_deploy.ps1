# Script de Restauração Completa do Deploy
$ErrorActionPreference = "Stop"

Write-Host "🔧 RESTAURAÇÃO COMPLETA DO GOVY" -ForegroundColor Cyan
Write-Host "================================`n" -ForegroundColor Cyan

# 1. Fazer backup do estado atual
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupDir = ".\backups\before_full_restore_$timestamp"
Write-Host "📦 Criando backup..." -ForegroundColor Yellow
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
if (Test-Path ".\function_app.py") { Copy-Item ".\function_app.py" $backupDir -Force }
if (Test-Path ".\govy") { Copy-Item ".\govy" $backupDir -Recurse -Force -ErrorAction SilentlyContinue }
Write-Host "✅ Backup criado`n" -ForegroundColor Green

# 2. Extrair deploy.zip
Write-Host "🔓 Extraindo deploy.zip..." -ForegroundColor Cyan
$tempExtract = ".\temp_extract"
if (Test-Path $tempExtract) { Remove-Item $tempExtract -Recurse -Force }
Expand-Archive -Path ".\deploy.zip" -DestinationPath $tempExtract -Force

# 3. Copiar arquivos
Write-Host "📥 Copiando arquivos..." -ForegroundColor Cyan
Copy-Item "$tempExtract\function_app.py" ".\function_app.py" -Force
Copy-Item "$tempExtract\patterns.json" ".\patterns.json" -Force
Copy-Item "$tempExtract\host.json" ".\host.json" -Force
Copy-Item "$tempExtract\requirements.txt" ".\requirements.txt" -Force

# 4. Copiar govy/
if (Test-Path ".\govy") { Remove-Item ".\govy" -Recurse -Force }
Copy-Item "$tempExtract\govy" ".\govy" -Recurse -Force
Write-Host "  ✅ Todos os arquivos restaurados" -ForegroundColor Green

# 5. Limpar
Remove-Item $tempExtract -Recurse -Force

# 6. Verificar estrutura
Write-Host "`n🔍 Verificando..." -ForegroundColor Cyan
Get-ChildItem ".\govy\api" | Select-Object Name

# 7. Deploy
Write-Host "`n🚀 FAZENDO DEPLOY..." -ForegroundColor Cyan
func azure functionapp publish func-govy-parse-test --build remote

Write-Host "`n✅ CONCLUÍDO! Aguarde 30s e teste: .\govy.ps1 testar" -ForegroundColor Green