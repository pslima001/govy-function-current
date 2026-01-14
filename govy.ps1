# GOVY.PS1 - Sistema Unificado
param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet('testar', 'ver', 'validar', 'deploy', 'status', 'ajustar', 'help')]
    [string]$Comando,
    
    [Parameter(Position=1)]
    [string]$Argumento1,
    
    [Alias('e')]
    [ValidateSet('e001', 'pg001', 'o001', 'l001')]
    [string]$Extractor = 'e001',
    
    [Alias('t')]
    [ValidateSet('positivo', 'negativo')]
    [string]$Tipo = 'positivo'
)

$Global:CONFIG = @{
    FunctionAppName = "func-govy-parse-test"
    ResourceGroup = "rg-govy-parse-test-sponsor"
    FunctionUrl = "https://func-govy-parse-test-exabasfqgsfgexhd.eastus-01.azurewebsites.net"
    StorageAccount = "stgovyparsetestsponsor"
    Container = "editais-teste"
    PatternsPath = "govy\extractors\config\patterns.json"
}

$Global:EXTRACTORS = @{
    'e001' = @{ id = 'e001_entrega'; nome = 'Prazo de Entrega' }
    'pg001' = @{ id = 'pg001_pagamento'; nome = 'Prazo de Pagamento' }
    'o001' = @{ id = 'o001_objeto'; nome = 'Objeto' }
    'l001' = @{ id = 'l001_locais'; nome = 'Locais' }
}

function Write-ColorOutput {
    param([string]$Message, [string]$Type = 'info')
    $colors = @{'success' = 'Green'; 'error' = 'Red'; 'warning' = 'Yellow'; 'info' = 'Cyan'}
    Write-Host $Message -ForegroundColor $colors[$Type]
}

function Get-FunctionKey {
    param([string]$FunctionName)
    try {
        $keys = az functionapp function keys list --function-name $FunctionName --name $Global:CONFIG.FunctionAppName --resource-group $Global:CONFIG.ResourceGroup --output json | ConvertFrom-Json
        return $keys.default
    } catch {
        Write-ColorOutput "Erro ao obter key: $_" 'error'
        return $null
    }
}

function Upload-Pdf {
    param([string]$FilePath)
    if (-not (Test-Path $FilePath)) {
        Write-ColorOutput "Arquivo nao encontrado: $FilePath" 'error'
        return $null
    }
    $guid = [System.Guid]::NewGuid().ToString("N")
    $blobName = "uploads/$guid.pdf"
    Write-ColorOutput "Fazendo upload..." 'info'
    try {
        az storage blob upload --account-name $Global:CONFIG.StorageAccount --container-name $Global:CONFIG.Container --name $blobName --file $FilePath --auth-mode login --output none
        Write-ColorOutput "Upload completo: $blobName" 'success'
        return $blobName
    } catch {
        Write-ColorOutput "Erro no upload: $_" 'error'
        return $null
    }
}

function Invoke-ExtractParams {
    param([string]$BlobName)
    Write-ColorOutput "Extraindo parametros..." 'info'
    $key = Get-FunctionKey -FunctionName "extract_params"
    if (-not $key) { return $null }
    $url = "$($Global:CONFIG.FunctionUrl)/api/extract_params?code=$key"
    $body = @{ blob_name = $BlobName } | ConvertTo-Json
    try {
        $result = Invoke-RestMethod -Uri $url -Method POST -ContentType "application/json" -Body $body
        Write-ColorOutput "Extracao completa!" 'success'
        return $result
    } catch {
        Write-ColorOutput "Erro na extracao: $($_.Exception.Message)" 'error'
        return $null
    }
}

function Show-Results {
    param($Result)
    if (-not $Result) { return }
    Write-Host ""
    Write-ColorOutput "=== RESULTADOS ===" 'info'
    $obj = $Result.params.o001_objeto
    if ($obj.status -eq 'found') {
        Write-ColorOutput "OBJETO: $($obj.value.Substring(0, [Math]::Min(100, $obj.value.Length)))..." 'success'
    } else {
        Write-ColorOutput "OBJETO: NAO ENCONTRADO" 'error'
    }
    $entrega = $Result.params.e001_entrega
    if ($entrega.status -eq 'found') {
        Write-ColorOutput "PRAZO ENTREGA: $($entrega.value)" 'success'
    } else {
        Write-ColorOutput "PRAZO ENTREGA: NAO ENCONTRADO" 'warning'
    }
    $pagamento = $Result.params.pg001_pagamento
    if ($pagamento.status -eq 'found') {
        Write-ColorOutput "PRAZO PAGAMENTO: $($pagamento.value)" 'success'
    } else {
        Write-ColorOutput "PRAZO PAGAMENTO: NAO ENCONTRADO" 'warning'
    }
    $locais = $Result.params.l001_locais
    if ($locais.status -eq 'found') {
        Write-ColorOutput "LOCAIS: $($locais.values.Count) encontrado(s)" 'success'
    } else {
        Write-ColorOutput "LOCAIS: NAO ENCONTRADO" 'warning'
    }
    Write-Host ""
}

function Invoke-Testar {
    param([string]$FilePath)
    if (-not $FilePath) {
        Write-ColorOutput "Uso: .\govy.ps1 testar arquivo.pdf" 'error'
        return
    }
    Write-ColorOutput "TESTANDO: $FilePath" 'info'
    $blobName = Upload-Pdf -FilePath $FilePath
    if (-not $blobName) { return }
    $result = Invoke-ExtractParams -BlobName $blobName
    if (-not $result) { return }
    Show-Results -Result $result
}

function Invoke-Ver {
    param([string]$Ext)
    if (-not $Ext) {
        Write-ColorOutput "Uso: .\govy.ps1 ver e001" 'error'
        return
    }
    $extractorId = $Global:EXTRACTORS[$Ext].id
    $extractorNome = $Global:EXTRACTORS[$Ext].nome
    $patterns = Get-Content $Global:CONFIG.PatternsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $config = $patterns.extractors.$extractorId
    Write-Host ""
    Write-ColorOutput "=== $extractorNome ===" 'info'
    Write-Host "Threshold: $($config.threshold_score)"
    Write-Host ""
    Write-ColorOutput "Termos Positivos:" 'success'
    $config.contexto.positivos | ForEach-Object { Write-Host "  - $_" }
    Write-Host ""
    Write-ColorOutput "Termos Negativos:" 'error'
    $config.contexto.negativos | ForEach-Object { Write-Host "  - $_" }
    Write-Host ""
}

function Invoke-Ajustar {
    param([string]$Termo)
    if (-not $Termo) {
        Write-ColorOutput "Uso: .\govy.ps1 ajustar 'termo' -e e001 -t positivo" 'error'
        return
    }
    $extractorId = $Global:EXTRACTORS[$Extractor].id
    $extractorNome = $Global:EXTRACTORS[$Extractor].nome
    Write-ColorOutput "Adicionando '$Termo' aos $Tipo de $extractorNome..." 'info'
    $patterns = Get-Content $Global:CONFIG.PatternsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $contexto = $patterns.extractors.$extractorId.contexto
    $lista = if ($Tipo -eq 'positivo') { 'positivos' } else { 'negativos' }
    if ($contexto.$lista -contains $Termo) {
        Write-ColorOutput "Termo ja existe!" 'warning'
        return
    }
    $contexto.$lista += $Termo
    $patterns | ConvertTo-Json -Depth 10 | Set-Content $Global:CONFIG.PatternsPath -Encoding UTF8
    Write-ColorOutput "Termo '$Termo' adicionado!" 'success'
    $deploy = Read-Host "Fazer deploy agora? (s/n)"
    if ($deploy -eq 's') { Invoke-Deploy }
}

function Invoke-Validar {
    Write-ColorOutput "Validando patterns.json..." 'info'
    try {
        $patterns = Get-Content $Global:CONFIG.PatternsPath -Raw -Encoding UTF8 | ConvertFrom-Json
        Write-ColorOutput "JSON valido!" 'success'
    } catch {
        Write-ColorOutput "JSON invalido: $_" 'error'
    }
}

function Invoke-Deploy {
    Write-ColorOutput "Iniciando deploy..." 'info'
    git add .
    $commitMsg = Read-Host "Mensagem do commit"
    if (-not $commitMsg) { $commitMsg = "update: ajustes em patterns" }
    git commit -m $commitMsg
    git push origin main
    Write-ColorOutput "Push completo!" 'success'
    Write-ColorOutput "Acompanhe: https://github.com/pslima001/govy-function-current/actions" 'info'
}

function Invoke-Status {
    Write-ColorOutput "Status do Azure Functions..." 'info'
    az functionapp function list --name $Global:CONFIG.FunctionAppName --resource-group $Global:CONFIG.ResourceGroup --output table
}

function Show-Help {
    Write-Host ""
    Write-Host "=== GOVY.PS1 - Sistema Unificado ===" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "COMANDOS:"
    Write-Host "  .\govy.ps1 testar arquivo.pdf       Testar PDF"
    Write-Host "  .\govy.ps1 ajustar 'termo' -e e001  Adicionar termo"
    Write-Host "  .\govy.ps1 ver e001                 Ver config"
    Write-Host "  .\govy.ps1 validar                  Validar JSON"
    Write-Host "  .\govy.ps1 deploy                   Deploy"
    Write-Host "  .\govy.ps1 status                   Status Azure"
    Write-Host ""
}

switch ($Comando) {
    'testar' { Invoke-Testar -FilePath $Argumento1 }
    'ver' { Invoke-Ver -Ext $Argumento1 }
    'ajustar' { Invoke-Ajustar -Termo $Argumento1 }
    'validar' { Invoke-Validar }
    'deploy' { Invoke-Deploy }
    'status' { Invoke-Status }
    'help' { Show-Help }
    default { Show-Help }
}
