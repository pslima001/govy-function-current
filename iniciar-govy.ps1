Set-Location "C:\govy\repos\govy-function-current"
Clear-Host
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "   GOVY - SISTEMA DE TESTES DE EDITAIS    " -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Comandos rapidos:" -ForegroundColor Yellow
Write-Host "  testar    - Selecionar PDF e testar"
Write-Host "  ajustar   - Adicionar termo"
Write-Host "  ver       - Ver configuracao"
Write-Host "  deploy    - Fazer deploy"
Write-Host ""

function testar { 
    if ($args.Count -eq 0) {
        & ".\govy.ps1" testar
    } else {
        & ".\govy.ps1" testar $args[0]
    }
}

function ajustar { 
    & ".\govy.ps1" ajustar @args
}

function ver { 
    & ".\govy.ps1" ver $args[0]
}

function deploy { 
    & ".\govy.ps1" deploy
}

Write-Host "Digite 'testar' para comecar!" -ForegroundColor Green
Write-Host ""
