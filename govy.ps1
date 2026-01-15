# GOVY.PS1 - Sistema Unificado v2 CORRIGIDO
param(
    [Parameter(Mandatory=$false, Position=0)]
    [ValidateSet('testar', 'ver', 'validar', 'deploy', 'status', 'ajustar', 'help')]
    [string]$Comando = 'testar',
    
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
    MasterKey = "30XqJz2yguWbu0GW8sOznfnOobyKTCTR4zKBTkrpSQJyAzFurKKWZg=="
}

$Global:EXTRACTORS = @{
    'e001' = @{ id = 'e001_entrega'; nome = 'Prazo de Entrega' }
    'pg001' = @{ id = 'pg001_pagamento'; nome = 'Prazo de Pagamento' }
    'o001' = @{ id = 'o001_objeto'; nome = 'Objeto' }
    'l001' = @{ id = 'l001_locais'; nome = 'Locais' }
}

function Write-ColorOutput {
    param([string]$Message, [string]$Type = 'info')
    $colors = @{'success' = 'Green'; 'error' = 'Red'; 'warning' = 'Yellow'; 'info' = 'Cyan'; 'highlight' = 'Magenta'}
    $color = if ($colors.ContainsKey($Type)) { $colors[$Type] } else { 'White' }
    Write-Host $Message -ForegroundColor $color
}

function Select-PdfFile {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Filter = "PDF files (*.pdf)|*.pdf|All files (*.*)|*.*"
    $dialog.Title = "Selecione o edital PDF para testar"
    $dialog.InitialDirectory = [Environment]::GetFolderPath('MyDocuments')
    
    if ($dialog.ShowDialog() -eq 'OK') {
        return $dialog.FileName
    }
    return $null
}

function Upload-Pdf {
    param([string]$FilePath)
    if (-not (Test-Path $FilePath)) {
        Write-ColorOutput "Arquivo nao encontrado: $FilePath" 'error'
        return $null
    }
    
    $fileName = [System.IO.Path]::GetFileName($FilePath)
    $guid = [System.Guid]::NewGuid().ToString("N")
    $blobName = "uploads/$guid.pdf"
    
    Write-ColorOutput "Fazendo upload de: $fileName" 'info'
    
    try {
        az storage blob upload --account-name $Global:CONFIG.StorageAccount --container-name $Global:CONFIG.Container --name $blobName --file $FilePath --auth-mode key --output none
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
    
    $key = $Global:CONFIG.MasterKey
    $url = "$($Global:CONFIG.FunctionUrl)/api/extract_params?code=$key"
    $body = @{ blob_name = $BlobName } | ConvertTo-Json
    
    try {
        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $result = Invoke-RestMethod -Uri $url -Method POST -ContentType "application/json" -Body $body
        $stopwatch.Stop()
        Write-ColorOutput "Extracao completa em $($stopwatch.Elapsed.TotalSeconds)s!" 'success'
        return $result
    } catch {
        Write-ColorOutput "Erro na extracao: $($_.Exception.Message)" 'error'
        if ($_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $errorDetails = $reader.ReadToEnd()
            Write-ColorOutput "Detalhes: $errorDetails" 'error'
        }
        return $null
    }
}

function Show-Results {
    param($Result, $FilePath)
    if (-not $Result) { return }
    
    $fileName = [System.IO.Path]::GetFileName($FilePath)
    
    Write-Host ""
    Write-ColorOutput "============================================" 'highlight'
    Write-ColorOutput "RESULTADOS: $fileName" 'highlight'
    Write-ColorOutput "============================================" 'highlight'
    Write-Host ""
    
    # Obter params da resposta
    $params = $Result.params
    if (-not $params) {
        Write-ColorOutput "Formato de resposta desconhecido!" 'error'
        Write-Host ($Result | ConvertTo-Json -Depth 5)
        return
    }
    
    # Obter cada parâmetro
    $objeto = $params.o001_objeto
    $entrega = $params.e001_entrega  
    $pagamento = $params.pg001_pagamento
    $locais = $params.l001_locais
    
    $encontrados = 0
    
    # OBJETO
    Write-Host ""
    if ($objeto -and $objeto.status -eq "found") {
        $valorTrunc = if ($objeto.value.Length -gt 100) { $objeto.value.Substring(0, 100) + "..." } else { $objeto.value }
        Write-ColorOutput "[OK] OBJETO: $valorTrunc" 'success'
        Write-Host "     Score: $($objeto.score)"
        $encontrados++
    } else {
        Write-ColorOutput "[X] OBJETO: NAO ENCONTRADO" 'error'
    }
    
    # PRAZO DE ENTREGA
    Write-Host ""
    if ($entrega -and $entrega.status -eq "found") {
        Write-ColorOutput "[OK] PRAZO DE ENTREGA: $($entrega.value)" 'success'
        Write-Host "     Score: $($entrega.score)"
        if ($entrega.evidence) {
            $ctx = $entrega.evidence.Substring(0, [Math]::Min(150, $entrega.evidence.Length))
            Write-Host "     Contexto: $ctx..."
        }
        $encontrados++
    } else {
        Write-ColorOutput "[X] PRAZO DE ENTREGA: NAO ENCONTRADO" 'warning'
        Write-Host "     Dica: Abra o PDF e veja como o prazo esta escrito"
    }
    
    # PRAZO DE PAGAMENTO
    Write-Host ""
    if ($pagamento -and $pagamento.status -eq "found") {
        Write-ColorOutput "[OK] PRAZO DE PAGAMENTO: $($pagamento.value)" 'success'
        Write-Host "     Score: $($pagamento.score)"
        if ($pagamento.evidence) {
            $ctx = $pagamento.evidence.Substring(0, [Math]::Min(150, $pagamento.evidence.Length))
            Write-Host "     Contexto: $ctx..."
        }
        $encontrados++
    } else {
        Write-ColorOutput "[X] PRAZO DE PAGAMENTO: NAO ENCONTRADO" 'warning'
    }
    
    # LOCAIS
    Write-Host ""
    if ($locais -and $locais.status -eq "found") {
        $valorTrunc = if ($locais.value.Length -gt 100) { $locais.value.Substring(0, 100) + "..." } else { $locais.value }
        Write-ColorOutput "[OK] LOCAIS: $valorTrunc" 'success'
        Write-Host "     Score: $($locais.score)"
        $encontrados++
    } else {
        Write-ColorOutput "[X] LOCAIS: NAO ENCONTRADO" 'warning'
    }
    
    # RESUMO
    Write-Host ""
    Write-ColorOutput "============================================" 'highlight'
    $corFinal = if ($encontrados -eq 4) { 'success' } else { 'warning' }
    Write-ColorOutput "Encontrados: $encontrados/4" $corFinal
    Write-ColorOutput "============================================" 'highlight'
    Write-Host ""
    
    # Meta info se disponível
    if ($Result.meta) {
        Write-Host "Pages: $($Result.meta.page_count) | Tables: $($Result.meta.tables_count)"
        Write-Host ""
    }
    
    # Abrir PDF
    $abrir = Read-Host "Abrir PDF para comparar? (s/n)"
    if ($abrir -eq 's' -or $abrir -eq 'S') {
        Start-Process $FilePath
        Write-ColorOutput "PDF aberto!" 'success'
    }
}

function Invoke-Testar {
    param([string]$FilePath)
    
    if (-not $FilePath) {
        Write-ColorOutput "Selecione o PDF para testar..." 'info'
        $FilePath = Select-PdfFile
        if (-not $FilePath) {
            Write-ColorOutput "Nenhum arquivo selecionado." 'warning'
            return
        }
    }
    
    Write-ColorOutput "TESTANDO: $FilePath" 'highlight'
    Write-Host ""
    
    $blobName = Upload-Pdf -FilePath $FilePath
    if (-not $blobName) { return }
    
    $result = Invoke-ExtractParams -BlobName $blobName
    if (-not $result) { return }
    
    Show-Results -Result $result -FilePath $FilePath
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
    Write-ColorOutput "=== $extractorNome ===" 'highlight'
    Write-Host "Threshold: $($config.threshold_score)"
    Write-Host ""
    Write-ColorOutput "Termos Positivos ($($config.contexto.positivos.Count)):" 'success'
    $config.contexto.positivos | ForEach-Object { Write-Host "  - $_" }
    Write-Host ""
    Write-ColorOutput "Termos Negativos ($($config.contexto.negativos.Count)):" 'error'
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
    Write-ColorOutput "Termo '$Termo' adicionado aos $lista!" 'success'
    Write-ColorOutput "Total agora: $($contexto.$lista.Count) termos" 'info'
    Write-Host ""
    $deploy = Read-Host "Fazer deploy agora? (s/n)"
    if ($deploy -eq 's') { Invoke-Deploy }
}

function Invoke-Validar {
    Write-ColorOutput "Validando patterns.json..." 'info'
    try {
        $patterns = Get-Content $Global:CONFIG.PatternsPath -Raw -Encoding UTF8 | ConvertFrom-Json
        Write-ColorOutput "JSON valido!" 'success'
        Write-ColorOutput "$($patterns.extractors.Count) extractors configurados" 'success'
    } catch {
        Write-ColorOutput "JSON invalido: $_" 'error'
    }
}

function Invoke-Deploy {
    Write-ColorOutput "Iniciando deploy..." 'highlight'
    Write-Host ""
    git add .
    $commitMsg = Read-Host "Mensagem do commit (Enter para default)"
    if (-not $commitMsg) { $commitMsg = "update: ajustes em patterns.json" }
    git commit -m $commitMsg
    git push origin main
    Write-ColorOutput "Push completo!" 'success'
    Write-Host ""
    Write-ColorOutput "GitHub Actions: https://github.com/pslima001/govy-function-current/actions" 'info'
    Write-Host ""
    $aguardar = Read-Host "Aguardar deploy? (aguarda 3min) (s/n)"
    if ($aguardar -eq 's') {
        Write-ColorOutput "Aguardando 3 minutos..." 'info'
        Start-Sleep -Seconds 180
        Write-ColorOutput "Deploy deve estar completo!" 'success'
    }
}

function Invoke-Status {
    Write-ColorOutput "Status do Azure Functions..." 'info'
    az functionapp function list --name $Global:CONFIG.FunctionAppName --resource-group $Global:CONFIG.ResourceGroup --output table
}

function Show-Help {
    Write-Host ""
    Write-ColorOutput "============================================" 'highlight'
    Write-ColorOutput "GOVY.PS1 - Sistema Unificado v2" 'highlight'
    Write-ColorOutput "============================================" 'highlight'
    Write-Host ""
    Write-Host "COMANDOS:"
    Write-Host ""
    Write-Host "  .\govy.ps1 testar [arquivo.pdf]    Testar PDF (abre dialog se nao passar arquivo)"
    Write-Host "  .\govy.ps1 ajustar 'termo' -e e001 Adicionar termo ao extractor"
    Write-Host "  .\govy.ps1 ver e001                Ver configuracao"
    Write-Host "  .\govy.ps1 validar                 Validar patterns.json"
    Write-Host "  .\govy.ps1 deploy                  Fazer deploy"
    Write-Host "  .\govy.ps1 status                  Ver status Azure"
    Write-Host ""
    Write-Host "EXTRACTORS: e001 (entrega), pg001 (pagamento), o001 (objeto), l001 (locais)"
    Write-Host ""
    Write-Host "EXEMPLO DE USO:"
    Write-Host "  1. .\govy.ps1 testar              (seleciona PDF visualmente)"
    Write-Host "  2. Ver resultado e abrir PDF"
    Write-Host "  3. .\govy.ps1 ajustar 'novo termo' -e e001 -t positivo"
    Write-Host "  4. .\govy.ps1 deploy"
    Write-Host "  5. .\govy.ps1 testar              (testa novamente)"
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

