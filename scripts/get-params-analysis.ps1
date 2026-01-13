Write-Host "=== GOVY - Analise ===" -ForegroundColor Cyan
Write-Host ""
Write-Host ">>> params.json" -ForegroundColor Green
Get-Content "params.json" -ErrorAction SilentlyContinue
Write-Host ""
Write-Host ">>> Arquivos .py encontrados" -ForegroundColor Green
Get-ChildItem -Path "src" -Recurse -Filter "*.py" | ForEach-Object { Write-Host $_.FullName }
Write-Host ""
Write-Host ">>> Conteudo dos arquivos" -ForegroundColor Green
Get-ChildItem -Path "src" -Recurse -Filter "*.py" | ForEach-Object {
    if ($_.Name -ne "__init__.py") {
        Write-Host "--- $($_.Name) ---" -ForegroundColor Yellow
        Get-Content $_.FullName
        Write-Host ""
    }
}
Write-Host ">>> function_app.py" -ForegroundColor Green
Get-Content "function_app.py" -ErrorAction SilentlyContinue
Write-Host ""
Write-Host "=== FIM ===" -ForegroundColor Cyan
