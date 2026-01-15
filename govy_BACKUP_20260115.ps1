# GOVY.PS1 - Sistema de Testes v3 FINAL
param(
    [Parameter(Mandatory=$false, Position=0)]
    [ValidateSet('testar', 'help')]
    [string]$Comando = 'testar'
)

$Global:CONFIG = @{
    FunctionUrl = "https://func-govy-parse-test-exabasfqgsfgexhd.eastus-01.azurewebsites.net"
    StorageAccount = "stgovyparsetestsponsor"
    Container = "editais-teste"
    MasterKey = "30XqJz2yguWbu0GW8sOznfnOobyKTCTR4zKBTkrpSQJyAzFurKKWZg=="
}

function Select-PdfFile {
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.OpenFileDialog
    $dialog.Filter = "PDF files (*.pdf)|*.pdf"
    $dialog.Title = "Selecione o PDF"
    if ($dialog.ShowDialog() -eq 'OK') { return $dialog.FileName }
    return $null
}

function Upload-Pdf {
    param([string]$FilePath)
    $guid = [System.Guid]::NewGuid().ToString("N")
    $blobName = "uploads/$guid.pdf"
    Write-Host "Upload: $([System.IO.Path]::GetFileName($FilePath))..." -ForegroundColor Cyan
    az storage blob upload --account-name $Global:CONFIG.StorageAccount --container-name $Global:CONFIG.Container --name $blobName --file $FilePath --auth-mode key --output none
    Write-Host "OK: $blobName" -ForegroundColor Green
    return $blobName
}

function Invoke-ExtractParams {
    param([string]$BlobName)
    Write-Host "Extraindo..." -ForegroundColor Cyan
    $url = "$($Global:CONFIG.FunctionUrl)/api/extract_params?code=$($Global:CONFIG.MasterKey)"
    $body = @{ blob_name = $BlobName } | ConvertTo-Json
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $result = Invoke-RestMethod -Uri $url -Method POST -ContentType "application/json" -Body $body
    $sw.Stop()
    Write-Host "Completo em $($sw.Elapsed.TotalSeconds)s!" -ForegroundColor Green
    return $result
}

function Show-Results {
    param($Result, $FilePath)
    $fileName = [System.IO.Path]::GetFileName($FilePath)
    Write-Host "`n========================================" -ForegroundColor Magenta
    Write-Host "RESULTADOS: $fileName" -ForegroundColor Magenta
    Write-Host "========================================" -ForegroundColor Magenta
    
    if ($Result.debug_info) {
        Write-Host "`nDEBUG: Texto=$($Result.debug_info.texto_length) chars | Chunks=$($Result.debug_info.chunks_count)" -ForegroundColor Yellow
    }
    
    $encontrados = 0
    $params = $Result.parametros
    
    foreach ($p in @(@{k='o001';n='OBJETO'},@{k='e001';n='PRAZO ENTREGA'},@{k='pg001';n='PAGAMENTO'},@{k='l001';n='LOCAIS'})) {
        $data = $params.($p.k)
        if ($data.encontrado) {
            Write-Host "`n[OK] $($p.n): $($data.valor)" -ForegroundColor Green
            Write-Host "     Confianca: $($data.confianca)" -ForegroundColor Gray
            $encontrados++
        } else {
            Write-Host "`n[X] $($p.n): NAO ENCONTRADO" -ForegroundColor Red
        }
    }
    
    Write-Host "`n========================================" -ForegroundColor Magenta
    Write-Host "Encontrados: $encontrados/4" -ForegroundColor $(if($encontrados -eq 4){'Green'}else{'Yellow'})
    Write-Host "========================================`n" -ForegroundColor Magenta
}

function Invoke-Testar {
    $pdf = Select-PdfFile
    if (-not $pdf) { Write-Host "Nenhum PDF selecionado" -ForegroundColor Yellow; return }
    $blob = Upload-Pdf -FilePath $pdf
    if (-not $blob) { return }
    $result = Invoke-ExtractParams -BlobName $blob
    if (-not $result) { return }
    Show-Results -Result $result -FilePath $pdf
}

if ($Comando -eq 'testar') { Invoke-Testar }
else { 
    Write-Host "`nGOVY - SISTEMA DE TESTES DE EDITAIS" -ForegroundColor Cyan
    Write-Host "Uso: .\govy.ps1 testar`n" -ForegroundColor White
}
