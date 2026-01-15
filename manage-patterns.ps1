# MANAGE-PATTERNS.PS1 - Gerenciador de Patterns do Govy
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('list', 'add', 'remove', 'deploy', 'validate')]
    [string]$Action,
    
    [ValidateSet('e001', 'pg001', 'o001', 'l001')]
    [string]$Extractor,
    
    [ValidateSet('positivo', 'negativo', 'regex', 'sinonimo')]
    [string]$Type,
    
    [string]$Value,
    
    [int]$Index
)

$ErrorActionPreference = "Stop"
$PatternsFile = "patterns.json"
$RepoPath = "C:\govy\repos\govy-function-current"

# Cores
function Write-Color {
    param([string]$Text, [string]$Color = 'White')
    Write-Host $Text -ForegroundColor $Color
}

# Carregar patterns.json
function Get-Patterns {
    if (-not (Test-Path $PatternsFile)) {
        Write-Color "ERRO: patterns.json nao encontrado!" Red
        exit 1
    }
    return Get-Content $PatternsFile -Raw -Encoding UTF8 | ConvertFrom-Json
}

# Salvar patterns.json
function Save-Patterns {
    param($Patterns)
    try {
        $json = $Patterns | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText("$PWD\$PatternsFile", $json, [System.Text.Encoding]::UTF8)
        Write-Color "Arquivo salvo com sucesso!" Green
        return $true
    } catch {
        Write-Color "ERRO ao salvar: $_" Red
        return $false
    }
}

# AÇÃO: LISTAR
function Invoke-List {
    $patterns = Get-Patterns
    $config = $patterns.$Extractor
    
    if (-not $config) {
        Write-Color "ERRO: Extractor '$Extractor' nao existe!" Red
        exit 1
    }
    
    Write-Host ""
    Write-Color "=======================================" Cyan
    Write-Color "$Extractor - $($config.label)" Cyan
    Write-Color "=======================================" Cyan
    Write-Host ""
    
    # Termos Positivos
    Write-Color "TERMOS POSITIVOS ($($config.termos_positivos.Count)):" Green
    for ($i = 0; $i -lt $config.termos_positivos.Count; $i++) {
        Write-Host "  $($i+1). $($config.termos_positivos[$i])"
    }
    Write-Host ""
    
    # Termos Negativos
    Write-Color "TERMOS NEGATIVOS ($($config.termos_negativos.Count)):" Red
    for ($i = 0; $i -lt $config.termos_negativos.Count; $i++) {
        Write-Host "  $($i+1). $($config.termos_negativos[$i])"
    }
    Write-Host ""
    
    # Regex Patterns
    Write-Color "REGEX PATTERNS ($($config.regex_patterns.Count)):" Yellow
    for ($i = 0; $i -lt $config.regex_patterns.Count; $i++) {
        $pattern = $config.regex_patterns[$i]
        if ($pattern.Length -gt 80) {
            $pattern = $pattern.Substring(0, 77) + "..."
        }
        Write-Host "  $($i+1). $pattern"
    }
    Write-Host ""
    
    # Pesos
    Write-Color "PESOS:" Magenta
    Write-Host "  Contexto positivo: $($config.peso_contexto_positivo)"
    Write-Host "  Contexto negativo: $($config.peso_contexto_negativo)"
    Write-Host "  Sinonimo: $($config.peso_sinonimo)"
    Write-Host ""
}

# AÇÃO: ADICIONAR
function Invoke-Add {
    if (-not $Value) {
        Write-Color "ERRO: Valor (-Value) e obrigatorio!" Red
        exit 1
    }
    
    $patterns = Get-Patterns
    $config = $patterns.$Extractor
    
    if (-not $config) {
        Write-Color "ERRO: Extractor '$Extractor' nao existe!" Red
        exit 1
    }
    
    switch ($Type) {
        'positivo' {
            if ($config.termos_positivos -contains $Value) {
                Write-Color "AVISO: Termo '$Value' ja existe nos positivos!" Yellow
                exit 0
            }
            $config.termos_positivos += $Value
            Write-Color "Adicionado '$Value' aos termos positivos de $Extractor" Green
            Write-Host "Total agora: $($config.termos_positivos.Count) termos"
        }
        'negativo' {
            if ($config.termos_negativos -contains $Value) {
                Write-Color "AVISO: Termo '$Value' ja existe nos negativos!" Yellow
                exit 0
            }
            $config.termos_negativos += $Value
            Write-Color "Adicionado '$Value' aos termos negativos de $Extractor" Green
            Write-Host "Total agora: $($config.termos_negativos.Count) termos"
        }
        'regex' {
            # Validar regex
            try {
                [regex]::new($Value) | Out-Null
            } catch {
                Write-Color "ERRO: Regex invalido!" Red
                Write-Color "Detalhes: $_" Red
                exit 1
            }
            
            if ($config.regex_patterns -contains $Value) {
                Write-Color "AVISO: Regex ja existe!" Yellow
                exit 0
            }
            
            $config.regex_patterns += $Value
            Write-Color "Adicionado regex ao $Extractor" Green
            Write-Host "Total agora: $($config.regex_patterns.Count) patterns"
        }
    }
    
    $patterns.$Extractor = $config
    if (Save-Patterns -Patterns $patterns) {
        Write-Host ""
        Write-Color "Deseja fazer deploy? (s/n)" Yellow
        # Retorna sucesso para o Claude processar
    }
}

# AÇÃO: REMOVER
function Invoke-Remove {
    if ($Index -le 0) {
        Write-Color "ERRO: Index (-Index) e obrigatorio e deve ser > 0!" Red
        exit 1
    }
    
    $patterns = Get-Patterns
    $config = $patterns.$Extractor
    
    if (-not $config) {
        Write-Color "ERRO: Extractor '$Extractor' nao existe!" Red
        exit 1
    }
    
    $arrayIndex = $Index - 1
    
    switch ($Type) {
        'positivo' {
            if ($arrayIndex -ge $config.termos_positivos.Count) {
                Write-Color "ERRO: Index $Index invalido! Max: $($config.termos_positivos.Count)" Red
                exit 1
            }
            $removed = $config.termos_positivos[$arrayIndex]
            $config.termos_positivos = @($config.termos_positivos | Where-Object { $_ -ne $removed })
            Write-Color "Removido '$removed' dos termos positivos" Green
        }
        'negativo' {
            if ($arrayIndex -ge $config.termos_negativos.Count) {
                Write-Color "ERRO: Index $Index invalido! Max: $($config.termos_negativos.Count)" Red
                exit 1
            }
            $removed = $config.termos_negativos[$arrayIndex]
            $config.termos_negativos = @($config.termos_negativos | Where-Object { $_ -ne $removed })
            Write-Color "Removido '$removed' dos termos negativos" Green
        }
        'regex' {
            if ($arrayIndex -ge $config.regex_patterns.Count) {
                Write-Color "ERRO: Index $Index invalido! Max: $($config.regex_patterns.Count)" Red
                exit 1
            }
            $removed = $config.regex_patterns[$arrayIndex]
            $config.regex_patterns = @($config.regex_patterns | Where-Object { $_ -ne $removed })
            Write-Color "Removido regex #$Index" Green
        }
    }
    
    $patterns.$Extractor = $config
    if (Save-Patterns -Patterns $patterns) {
        Write-Host ""
        Write-Color "Deseja fazer deploy? (s/n)" Yellow
    }
}

# AÇÃO: VALIDAR
function Invoke-Validate {
    Write-Color "Validando patterns.json..." Cyan
    try {
        $patterns = Get-Patterns
        Write-Color "JSON valido!" Green
        Write-Host "Extractors configurados: $($patterns.PSObject.Properties.Count)"
        
        foreach ($key in $patterns.PSObject.Properties.Name) {
            $config = $patterns.$key
            Write-Host "  $key ($($config.label)): $($config.regex_patterns.Count) patterns"
        }
        return $true
    } catch {
        Write-Color "ERRO: JSON invalido!" Red
        Write-Color "Detalhes: $_" Red
        return $false
    }
}

# AÇÃO: DEPLOY
function Invoke-Deploy {
    Write-Color "Iniciando deploy..." Cyan
    Write-Host ""
    
    # Validar primeiro
    if (-not (Invoke-Validate)) {
        Write-Color "Deploy cancelado devido a erros de validacao!" Red
        exit 1
    }
    
    Write-Host ""
    
    # Criar ZIP
    Write-Color "Criando release.zip..." Yellow
    if (Test-Path release.zip) { Remove-Item release.zip -Force }
    
    $files = @('host.json', 'function_app.py', 'requirements.txt', 'patterns.json', 'params.json', '.funcignore')
    
    # Verificar se todos os arquivos existem
    foreach ($file in $files) {
        if (-not (Test-Path $file)) {
            Write-Color "ERRO: Arquivo $file nao encontrado!" Red
            exit 1
        }
    }
    
    Compress-Archive -Path $files -DestinationPath release.zip -Force
    Write-Color "ZIP criado!" Green
    Write-Host ""
    
    # Deploy via Azure CLI
    Write-Color "Fazendo deploy no Azure..." Yellow
    az functionapp deployment source config-zip `
        --resource-group rg-govy-parse-test-sponsor `
        --name func-govy-parse-test `
        --src release.zip `
        --build-remote true `
        --timeout 600
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Color "=======================================" Green
        Write-Color "DEPLOY COMPLETO!" Green
        Write-Color "=======================================" Green
        Write-Host ""
        Write-Color "Aguarde 30 segundos e teste com:" Cyan
        Write-Color ".\govy.ps1 testar" White
        Write-Host ""
    } else {
        Write-Color "ERRO no deploy!" Red
        Write-Color "Verifique o output acima para detalhes." Yellow
        exit 1
    }
}

# EXECUTAR AÇÃO
switch ($Action) {
    'list' { Invoke-List }
    'add' { Invoke-Add }
    'remove' { Invoke-Remove }
    'validate' { Invoke-Validate }
    'deploy' { Invoke-Deploy }
}
