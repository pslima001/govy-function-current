# process_tcu_batch_v2.ps1 - Processamento em lote com ENUM CLAMP local
# Versao: 2.0 | Data: 29/01/2026
# FIX: Clamp de enums ANTES do upsert para evitar 400

# ==============================================================================
# CONFIGURACAO
# ==============================================================================

$key = "<AZURE_FUNCTION_KEY>"
$url = "https://func-govy-parse-test-exabasfqgsfgexhd.eastus-01.azurewebsites.net"
$inputFolder = "C:\govy\kb_raw\juris\TCU"
$outputFolder = "C:\govy\kb_runs"

# Criar pasta de output se nao existir
if (-not (Test-Path $outputFolder)) {
    New-Item -ItemType Directory -Path $outputFolder | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = "$outputFolder\run_$timestamp.log"

# ==============================================================================
# ENUMS VALIDOS (SPEC 1.2)
# ==============================================================================

$validProcedural = @(
    "EDITAL", "DISPUTA", "JULGAMENTO", "HABILITACAO", 
    "CONTRATACAO", "EXECUCAO", "PAGAMENTO", "SANCIONAMENTO", "NAO_CLARO"
)

$validOutcome = @(
    "MANTEVE", "AFASTOU", "DETERMINOU_AJUSTE", "ANULOU", "NAO_CLARO"
)

$validRemedy = @(
    "IMPUGNACAO", "RECURSO", "CONTRARRAZOES", "REPRESENTACAO", 
    "DENUNCIA", "ORIENTACAO_GERAL", "NAO_CLARO"
)

$validEffect = @(
    "FLEXIBILIZA", "RIGORIZA", "CONDICIONAL"
)

$validSecao = @(
    "EMENTA", "RELATORIO", "FUNDAMENTACAO", "DISPOSITIVO", "VOTO", "NAO_CLARO"
)

# ==============================================================================
# MAPEAMENTOS DE NORMALIZACAO
# ==============================================================================

$proceduralMappings = @{
    "LICITACAO" = "EDITAL"
    "PRE_LICITATORIO" = "EDITAL"
    "POS_LICITATORIO" = "EXECUCAO"
}

$outcomeMappings = @{
    "JULGOU_IRREGULARES" = "MANTEVE"
    "JULGOU_REGULARES" = "MANTEVE"
    "JULGOU_REGULARES_COM_RESSALVA" = "DETERMINOU_AJUSTE"
    "APLICOU_MULTA" = "MANTEVE"
    "DETERMINOU" = "DETERMINOU_AJUSTE"
    "RECOMENDOU" = "DETERMINOU_AJUSTE"
    "NULIDADE" = "ANULOU"
    "PROCEDENTE" = "MANTEVE"
    "IMPROCEDENTE" = "AFASTOU"
    "PARCIALMENTE_PROCEDENTE" = "DETERMINOU_AJUSTE"
}

$remedyMappings = @{
    "TOMADA_DE_CONTAS" = "ORIENTACAO_GERAL"
    "TOMADA_DE_CONTAS_ESPECIAL" = "ORIENTACAO_GERAL"
    "TCE" = "ORIENTACAO_GERAL"
    "CONSULTA" = "ORIENTACAO_GERAL"
    "AUDITORIA" = "ORIENTACAO_GERAL"
    "TCU_REPRESENTACAO" = "REPRESENTACAO"
    "PEDIDO_REEXAME" = "RECURSO"
    "PEDIDO_DE_REEXAME" = "RECURSO"
    "RECONSIDERACAO" = "RECURSO"
    "EMBARGOS" = "RECURSO"
}

# ==============================================================================
# FUNCOES DE CLAMP
# ==============================================================================

function Normalize-String {
    param([string]$value)
    
    if (-not $value) { return "" }
    
    $v = $value.Trim().ToUpper()
    $v = $v -replace '[\s\-]+', '_'
    $v = $v -replace '__+', '_'
    
    # Remover acentos basicos
    $v = $v -replace '[ÁÀÃÂ]', 'A'
    $v = $v -replace '[ÉÈÊ]', 'E'
    $v = $v -replace '[ÍÌÎ]', 'I'
    $v = $v -replace '[ÓÒÕÔ]', 'O'
    $v = $v -replace '[ÚÙÛ]', 'U'
    $v = $v -replace 'Ç', 'C'
    
    return $v
}

function Clamp-Enum {
    param(
        [string]$value,
        [string[]]$valid,
        [hashtable]$mappings,
        [string]$fallback
    )
    
    if (-not $value) { return $fallback }
    
    $v = Normalize-String $value
    
    # Ja e valido?
    if ($valid -contains $v) { return $v }
    
    # Tem mapeamento?
    if ($mappings -and $mappings.ContainsKey($v)) {
        return $mappings[$v]
    }
    
    # Fallback
    return $fallback
}

function Clamp-ProceduralStage {
    param([string]$value)
    return Clamp-Enum -value $value -valid $validProcedural -mappings $proceduralMappings -fallback "NAO_CLARO"
}

function Clamp-HoldingOutcome {
    param([string]$value)
    return Clamp-Enum -value $value -valid $validOutcome -mappings $outcomeMappings -fallback "NAO_CLARO"
}

function Clamp-RemedyType {
    param([string]$value)
    return Clamp-Enum -value $value -valid $validRemedy -mappings $remedyMappings -fallback "ORIENTACAO_GERAL"
}

function Clamp-Effect {
    param([string]$value)
    return Clamp-Enum -value $value -valid $validEffect -mappings $null -fallback "CONDICIONAL"
}

function Clamp-Secao {
    param([string]$value)
    return Clamp-Enum -value $value -valid $validSecao -mappings $null -fallback "NAO_CLARO"
}

function Clamp-Chunk {
    param([PSCustomObject]$chunk)
    
    # Clonar chunk
    $clamped = $chunk.PSObject.Copy()
    
    # Aplicar clamp em cada campo
    if ($clamped.procedural_stage) {
        $clamped.procedural_stage = Clamp-ProceduralStage $clamped.procedural_stage
    }
    if ($clamped.holding_outcome) {
        $clamped.holding_outcome = Clamp-HoldingOutcome $clamped.holding_outcome
    }
    if ($clamped.remedy_type) {
        $clamped.remedy_type = Clamp-RemedyType $clamped.remedy_type
    }
    if ($clamped.effect) {
        $clamped.effect = Clamp-Effect $clamped.effect
    }
    if ($clamped.secao) {
        $clamped.secao = Clamp-Secao $clamped.secao
    }
    
    return $clamped
}

# ==============================================================================
# FUNCAO DE EXTRACAO DE ANO DO ARQUIVO
# ==============================================================================

function Get-YearFromFilename {
    param([string]$filename)
    
    # Tentar padroes comuns
    if ($filename -match '_(\d{4})_') {
        return [int]$Matches[1]
    }
    elseif ($filename -match '(\d{4})') {
        return [int]$Matches[1]
    }
    
    return $null
}

# ==============================================================================
# FUNCAO DE EXTRACAO DE TEXTO DO DOCX
# ==============================================================================

function Get-TextFromDocx {
    param([string]$path)
    
    try {
        $word = New-Object -ComObject Word.Application
        $word.Visible = $false
        $doc = $word.Documents.Open($path, $false, $true)
        $text = $doc.Content.Text
        $doc.Close($false)
        $word.Quit()
        [System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
        return $text
    }
    catch {
        Write-Host "   Erro ao extrair texto: $($_.Exception.Message)" -ForegroundColor Red
        return $null
    }
}

# ==============================================================================
# FUNCAO DE LOG
# ==============================================================================

function Write-Log {
    param([string]$message, [string]$color = "White")
    
    $ts = Get-Date -Format "HH:mm:ss"
    $logMsg = "[$ts] $message"
    
    Write-Host $logMsg -ForegroundColor $color
    Add-Content -Path $logFile -Value $logMsg
}

# ==============================================================================
# PROCESSAMENTO PRINCIPAL
# ==============================================================================

Write-Log "=== INICIO DO PROCESSAMENTO EM LOTE ===" "Cyan"
Write-Log "Input: $inputFolder"
Write-Log "Output: $logFile"

$files = Get-ChildItem -Path $inputFolder -Filter "*.docx" | Where-Object { -not $_.Name.StartsWith("~") }
$total = $files.Count
$processed = 0
$succeeded = 0
$failed = 0
$skipped = 0

Write-Log "Total de arquivos: $total"

foreach ($f in $files) {
    $processed++
    Write-Log ""
    Write-Log "[$processed/$total] $($f.Name)" "Yellow"
    
    # 1. Extrair texto do DOCX
    $text = Get-TextFromDocx $f.FullName
    
    if (-not $text) {
        Write-Log "   SKIP: Falha ao extrair texto" "Red"
        $skipped++
        continue
    }
    
    # 2. Verificar tamanho minimo
    if ($text.Length -lt 1500) {
        Write-Log "   SKIP: Texto muito curto ($($text.Length) chars)" "Yellow"
        $skipped++
        continue
    }
    
    # 3. Inferir ano do arquivo
    $year = Get-YearFromFilename $f.BaseName
    if (-not $year) {
        $year = (Get-Date).Year
        Write-Log "   AVISO: Ano nao detectado, usando $year"
    }
    
    # 4. Chamar extract_all
    $body = @{
        text = $text
        metadata = @{
            source = "TCU"
            tribunal = "TCU"
            year = $year
            title = $f.BaseName
        }
    } | ConvertTo-Json -Depth 5
    
    try {
        Write-Log "   Chamando extract_all..."
        $extractResp = Invoke-RestMethod -Uri "$url/api/kb/juris/extract_all?code=$key" `
            -Method POST `
            -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) `
            -ContentType "application/json; charset=utf-8" `
            -TimeoutSec 120
        
        Write-Log "   Status: $($extractResp.status), Action: $($extractResp.action)"
        
        if ($extractResp.status -eq "skipped") {
            Write-Log "   SKIP: $($extractResp.reason)" "Yellow"
            $skipped++
            continue
        }
        
        if ($extractResp.status -eq "failed") {
            Write-Log "   FAILED: $($extractResp.error)" "Red"
            $failed++
            continue
        }
        
        # 5. APLICAR CLAMP LOCAL (HOTFIX)
        if ($extractResp.chunk) {
            $chunk = $extractResp.chunk
            
            Write-Log "   Aplicando CLAMP local..."
            Write-Log "   ANTES: procedural=$($chunk.procedural_stage), outcome=$($chunk.holding_outcome), remedy=$($chunk.remedy_type)"
            
            # Clamp cada campo
            $chunk.procedural_stage = Clamp-ProceduralStage $chunk.procedural_stage
            $chunk.holding_outcome = Clamp-HoldingOutcome $chunk.holding_outcome
            $chunk.remedy_type = Clamp-RemedyType $chunk.remedy_type
            $chunk.effect = Clamp-Effect $chunk.effect
            if ($chunk.secao) {
                $chunk.secao = Clamp-Secao $chunk.secao
            }
            
            Write-Log "   DEPOIS: procedural=$($chunk.procedural_stage), outcome=$($chunk.holding_outcome), remedy=$($chunk.remedy_type)"
            
            # 6. Forcar uf/region null para TCU
            $chunk.uf = $null
            $chunk.region = $null
            
            # 7. Chamar upsert
            if ($extractResp.action -eq "auto_indexed") {
                Write-Log "   Chamando upsert..."
                
                $upsertBody = @{
                    chunks = @($chunk)
                    generate_embeddings = $true
                } | ConvertTo-Json -Depth 5
                
                try {
                    $upsertResp = Invoke-RestMethod -Uri "$url/api/kb/index/upsert?code=$key" `
                        -Method POST `
                        -Body ([System.Text.Encoding]::UTF8.GetBytes($upsertBody)) `
                        -ContentType "application/json; charset=utf-8" `
                        -TimeoutSec 60
                    
                    Write-Log "   UPSERT OK: indexed=$($upsertResp.indexed)" "Green"
                    $succeeded++
                }
                catch {
                    $statusCode = $_.Exception.Response.StatusCode.value__
                    Write-Log "   UPSERT FALHOU: $statusCode - $($_.Exception.Message)" "Red"
                    $failed++
                }
            }
            else {
                Write-Log "   Enviado para REVIEW QUEUE" "Yellow"
                $succeeded++
            }
        }
        else {
            Write-Log "   SEM CHUNK na resposta" "Yellow"
            $skipped++
        }
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Log "   ERRO $statusCode : $($_.Exception.Message)" "Red"
        $failed++
    }
    
    # Pequena pausa para nao sobrecarregar
    Start-Sleep -Milliseconds 500
}

# ==============================================================================
# RESUMO FINAL
# ==============================================================================

Write-Log ""
Write-Log "=== RESUMO FINAL ===" "Cyan"
Write-Log "Total processados: $processed"
Write-Log "Sucesso: $succeeded" "Green"
Write-Log "Falhas: $failed" "Red"
Write-Log "Skipped: $skipped" "Yellow"
Write-Log ""
Write-Log "Log salvo em: $logFile"
