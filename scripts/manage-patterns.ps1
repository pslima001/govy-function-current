# ============================================================
# GOVY - Gerenciador de Patterns
# ============================================================
# Uso:
#   .\scripts\manage-patterns.ps1 -Action list
#   .\scripts\manage-patterns.ps1 -Action add -Extractor e001_entrega -Tipo positivos -Termo "prazo maximo"
#   .\scripts\manage-patterns.ps1 -Action remove -Extractor e001_entrega -Tipo positivos -Termo "prazo maximo"
# ============================================================

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("list", "add", "remove", "show")]
    [string]$Action,
    
    [string]$Extractor,
    [string]$Tipo,
    [string]$Termo
)

$patternsPath = "govy\extractors\config\patterns.json"

if (-not (Test-Path $patternsPath)) {
    Write-Host "ERRO: patterns.json nao encontrado em $patternsPath" -ForegroundColor Red
    exit 1
}

$json = Get-Content $patternsPath -Raw | ConvertFrom-Json

switch ($Action) {
    "list" {
        Write-Host "`n=== EXTRACTORS DISPONIVEIS ===" -ForegroundColor Cyan
        $json.extractors.PSObject.Properties | ForEach-Object {
            $ext = $_.Value
            Write-Host "`n[$($_.Name)]" -ForegroundColor Yellow
            Write-Host "  Nome: $($ext.nome)"
            Write-Host "  Ativo: $($ext.ativo)"
            if ($ext.contexto) {
                Write-Host "  Positivos: $($ext.contexto.positivos.Count) termos"
                Write-Host "  Negativos: $($ext.contexto.negativos.Count) termos"
            }
            if ($ext.gatilhos) {
                Write-Host "  Gatilhos: $($ext.gatilhos.Count) termos"
            }
        }
    }
    
    "show" {
        if (-not $Extractor) {
            Write-Host "ERRO: Informe -Extractor" -ForegroundColor Red
            exit 1
        }
        $ext = $json.extractors.$Extractor
        if (-not $ext) {
            Write-Host "ERRO: Extractor '$Extractor' nao encontrado" -ForegroundColor Red
            exit 1
        }
        Write-Host "`n=== $Extractor ===" -ForegroundColor Cyan
        Write-Host ($ext | ConvertTo-Json -Depth 5)
    }
    
    "add" {
        if (-not $Extractor -or -not $Tipo -or -not $Termo) {
            Write-Host "ERRO: Informe -Extractor, -Tipo e -Termo" -ForegroundColor Red
            Write-Host "Exemplo: -Extractor e001_entrega -Tipo positivos -Termo 'prazo maximo'" -ForegroundColor Gray
            exit 1
        }
        
        $ext = $json.extractors.$Extractor
        if (-not $ext) {
            Write-Host "ERRO: Extractor '$Extractor' nao encontrado" -ForegroundColor Red
            exit 1
        }
        
        # Determinar onde adicionar
        $lista = $null
        if ($Tipo -eq "positivos" -or $Tipo -eq "negativos") {
            if ($ext.contexto) {
                $lista = $ext.contexto.$Tipo
            }
        } elseif ($Tipo -eq "gatilhos") {
            $lista = $ext.gatilhos
        } elseif ($Tipo -eq "stop_markers") {
            $lista = $ext.stop_markers
        }
        
        if (-not $lista) {
            Write-Host "ERRO: Tipo '$Tipo' nao encontrado em '$Extractor'" -ForegroundColor Red
            exit 1
        }
        
        # Verificar duplicata
        if ($lista -contains $Termo) {
            Write-Host "AVISO: Termo '$Termo' ja existe em $Extractor.$Tipo" -ForegroundColor Yellow
            exit 0
        }
        
        # Adicionar
        $novaLista = @($lista) + $Termo
        
        if ($Tipo -eq "positivos" -or $Tipo -eq "negativos") {
            $ext.contexto.$Tipo = $novaLista
        } elseif ($Tipo -eq "gatilhos") {
            $ext.gatilhos = $novaLista
        } elseif ($Tipo -eq "stop_markers") {
            $ext.stop_markers = $novaLista
        }
        
        # Atualizar historico
        $hoje = Get-Date -Format "yyyy-MM-dd"
        $novoHist = @{
            data = $hoje
            tipo = "add"
            descricao = "Adicionado '$Termo' em $Extractor.$Tipo"
        }
        $json.historico += $novoHist
        $json._meta.atualizado_em = $hoje
        
        # Salvar
        $json | ConvertTo-Json -Depth 10 | Out-File -FilePath $patternsPath -Encoding UTF8
        
        Write-Host "OK: Termo '$Termo' adicionado em $Extractor.$Tipo" -ForegroundColor Green
        Write-Host "Execute 'git add/commit/push' para persistir no GitHub" -ForegroundColor Gray
    }
    
    "remove" {
        if (-not $Extractor -or -not $Tipo -or -not $Termo) {
            Write-Host "ERRO: Informe -Extractor, -Tipo e -Termo" -ForegroundColor Red
            exit 1
        }
        
        $ext = $json.extractors.$Extractor
        if (-not $ext) {
            Write-Host "ERRO: Extractor '$Extractor' nao encontrado" -ForegroundColor Red
            exit 1
        }
        
        $lista = $null
        if ($Tipo -eq "positivos" -or $Tipo -eq "negativos") {
            if ($ext.contexto) {
                $lista = $ext.contexto.$Tipo
            }
        } elseif ($Tipo -eq "gatilhos") {
            $lista = $ext.gatilhos
        }
        
        if (-not $lista) {
            Write-Host "ERRO: Tipo '$Tipo' nao encontrado" -ForegroundColor Red
            exit 1
        }
        
        if (-not ($lista -contains $Termo)) {
            Write-Host "AVISO: Termo '$Termo' nao existe em $Extractor.$Tipo" -ForegroundColor Yellow
            exit 0
        }
        
        $novaLista = $lista | Where-Object { $_ -ne $Termo }
        
        if ($Tipo -eq "positivos" -or $Tipo -eq "negativos") {
            $ext.contexto.$Tipo = @($novaLista)
        } elseif ($Tipo -eq "gatilhos") {
            $ext.gatilhos = @($novaLista)
        }
        
        $hoje = Get-Date -Format "yyyy-MM-dd"
        $json.historico += @{
            data = $hoje
            tipo = "remove"
            descricao = "Removido '$Termo' de $Extractor.$Tipo"
        }
        $json._meta.atualizado_em = $hoje
        
        $json | ConvertTo-Json -Depth 10 | Out-File -FilePath $patternsPath -Encoding UTF8
        
        Write-Host "OK: Termo '$Termo' removido de $Extractor.$Tipo" -ForegroundColor Green
    }
}

Write-Host ""
