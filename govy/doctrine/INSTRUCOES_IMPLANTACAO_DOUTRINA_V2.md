# INSTRUÇÕES DE IMPLANTAÇÃO - DOUTRINA V2
**Data:** 02/02/2026  
**Arquiteto:** ChatGPT  
**Implementador:** Claude  

---

## 🎯 OBJETIVO

Evoluir o pipeline de doutrina para `doctrine_processed_v2` com:
- **raw_chunks**: texto bruto interno (nunca UI)
- **semantic_chunks**: doutrina neutralizada via OpenAI (com `argument_role` v1)
- **verbatim_legal_chunks**: jurisprudência citável (texto literal + `citation_meta`)

---

## 📦 ARQUIVOS CRIADOS

Todos os arquivos estão em `/mnt/user-data/outputs/`:

1. **semantic.py** - Extração semântica via OpenAI + argument_role v1
2. **verbatim_classifier.py** - Detecta tribunal/jurisprudência
3. **citation_extractor.py** - Extrai metadados de citação
4. **run_batch.py** - Batch runner para processar em massa
5. **pipeline.py** - Pipeline completo v2 (SUBSTITUIR o atual)

---

## 🚀 PASSO A PASSO NA VM

### PASSO 1: Backup do Pipeline Atual

```powershell
# Na VM (via RDP)
cd C:\govy\repos\govy-function-current\govy\doctrine

# Fazer backup
Copy-Item pipeline.py pipeline.py.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')

# Verificar backup
Get-ChildItem *.backup_*
```

### PASSO 2: Copiar Arquivos Novos

**Baixe os 5 arquivos de `/mnt/user-data/outputs/` e coloque em:**

```
C:\govy\repos\govy-function-current\govy\doctrine\
├── semantic.py              (NOVO)
├── verbatim_classifier.py   (NOVO)
├── citation_extractor.py    (NOVO)
├── run_batch.py            (NOVO)
└── pipeline.py             (SUBSTITUIR)
```

### PASSO 3: Configurar OPENAI_API_KEY

```powershell
# Adicionar no Azure Functions
az functionapp config appsettings set `
  --name func-govy-parse-test `
  --resource-group rg-govy-parse-test-sponsor `
  --settings "OPENAI_API_KEY=sk-..."

# Verificar
az functionapp config appsettings list `
  --name func-govy-parse-test `
  --resource-group rg-govy-parse-test-sponsor `
  --query "[?name=='OPENAI_API_KEY']"
```

### PASSO 4: Commit e Deploy

```powershell
cd C:\govy\repos\govy-function-current

# Git add
git add govy/doctrine/*.py

# Commit
git commit -m "feat(doctrine): Implement v2 pipeline with semantic chunks and argument_role

- Add semantic.py: OpenAI extraction with argument_role v1 catalog
- Add verbatim_classifier.py: Detect tribunal/jurisprudence
- Add citation_extractor.py: Extract citation metadata
- Add run_batch.py: Batch processing runner
- Update pipeline.py: doctrine_processed_v2 with raw/semantic/verbatim chunks
- BREAKING: DoctrineIngestRequest fields now have defaults"

# Push
git push origin main
```

### PASSO 5: Deploy

```powershell
# Deploy via func publish (ÚNICO MÉTODO CORRETO)
func azure functionapp publish func-govy-parse-test --python --build remote

# Aguardar 2 minutos (cold start)
Start-Sleep -Seconds 120
```

### PASSO 6: Testar com 1 Arquivo

```powershell
$url = "https://func-govy-parse-test-exabasfqgsfgexhd.eastus-01.azurewebsites.net"
$key = "<AZURE_FUNCTION_KEY>"

# Teste com 1 DOCX
$body = @{
    blob_name = "raw/2049e64fa65d42ff8cafbcd3dff6d35c.docx"
    etapa_processo = "habilitacao"
    tema_principal = "habilitacao"
    force_reprocess = $true
} | ConvertTo-Json

Invoke-RestMethod -Uri "$url/api/ingest_doctrine?code=$key" `
  -Method POST `
  -ContentType "application/json" `
  -Body $body
```

### PASSO 7: Validar Resultado

```powershell
# Listar blobs processados
$connString = az storage account show-connection-string `
  --name stgovyparsetestsponsor `
  --resource-group rg-govy-parse-test-sponsor `
  --query "connectionString" `
  --output tsv

az storage blob list `
  --connection-string $connString `
  --container-name doutrina-processed `
  --query "[].{Name:name, Size:properties.contentLength}" `
  --output table

# Baixar e verificar JSON
az storage blob download `
  --connection-string $connString `
  --container-name doutrina-processed `
  --name "habilitacao/habilitacao/<source_sha>.json" `
  --file "C:\temp\resultado_v2.json"

# Abrir e verificar estrutura
code C:\temp\resultado_v2.json
```

**Verificar se o JSON contém:**
```json
{
  "kind": "doctrine_processed_v2",
  "raw_chunks": [...],
  "semantic_chunks": [
    {
      "argument_role": "DEFINICAO",  // ou null se INCERTO
      "coverage_status": "COMPLETO",
      ...
    }
  ],
  "verbatim_legal_chunks": [
    {
      "citation_meta": {
        "tribunal": "TCU",
        ...
      }
    }
  ]
}
```

---

## 🔍 VALIDAÇÕES OBRIGATÓRIAS

### ✅ Checklist de Sucesso

- [ ] `kind == "doctrine_processed_v2"`
- [ ] `semantic_chunks` existe e tem items
- [ ] `argument_role` está preenchido quando `coverage_status != "INCERTO"`
- [ ] `argument_role == null` quando `coverage_status == "INCERTO"`
- [ ] `argument_role` está no catálogo v1: `DEFINICAO, FINALIDADE, DISTINCAO, LIMITE, RISCO, CRITERIO, PASSO_A_PASSO`
- [ ] `verbatim_legal_chunks` contém texto literal sem alteração
- [ ] `citation_meta` foi extraído (quando possível)
- [ ] `raw_chunks` existe mas NÃO deve ser usado na UI
- [ ] Reprocessamento com `force_reprocess=false` retorna `already_processed`

---

## 📊 BATCH EM MASSA (OPCIONAL)

### Criar Manifest JSON

```json
{
  "default": {
    "etapa_processo": "habilitacao",
    "tema_principal": "habilitacao"
  },
  "files": {
    "Art. 62 - HABILITAÇÃO - INTRODUÇÃO.docx": {
      "etapa_processo": "habilitacao",
      "tema_principal": "habilitacao",
      "autor": "INTERNO",
      "obra": "INTERNO",
      "edicao": "INTERNO",
      "ano": 2021,
      "capitulo": "Art. 62",
      "secao": "Introdução"
    }
  }
}
```

Salvar como: `C:\temp\manifest_doutrina.json`

### Rodar Batch

```powershell
cd C:\govy\repos\govy-function-current

# Configurar env vars
$env:AZURE_STORAGE_CONNECTION_STRING = $connString
$env:DOCTRINE_CONTAINER_SOURCE = "doutrina"
$env:DOCTRINE_CONTAINER_PROCESSED = "doutrina-processed"
$env:DOCTRINE_MANIFEST_JSON = "C:\temp\manifest_doutrina.json"
$env:DOCTRINE_FORCE_REPROCESS = "false"
$env:OPENAI_API_KEY = "sk-..."

# Rodar
python govy/doctrine/run_batch.py
```

---

## ⚠️ REGRAS CRÍTICAS

### 1. ARGUMENT_ROLE

- **Catálogo v1 (fixo):** `DEFINICAO, FINALIDADE, DISTINCAO, LIMITE, RISCO, CRITERIO, PASSO_A_PASSO`
- **Se `coverage_status="INCERTO"` → `argument_role=null`**
- **Nunca criar role fora do catálogo**

### 2. DOUTRINA vs JURISPRUDÊNCIA

- **Doutrina:** sigilo, neutralidade, sem autor/obra, sem consenso
- **Jurisprudência:** texto literal, citável, com citation_meta

### 3. NÃO BLOQUEAR

- Não usar `review_status=BLOCKED`
- Sanitizar e marcar `INCERTO` quando necessário
- Sempre gerar saída (nunca abortar)

---

## 🛠️ TROUBLESHOOTING

### Erro: "OPENAI_API_KEY não configurada"

```powershell
az functionapp config appsettings set `
  --name func-govy-parse-test `
  --resource-group rg-govy-parse-test-sponsor `
  --settings "OPENAI_API_KEY=sk-..."
```

### Erro: "ModuleNotFoundError: govy.doctrine.semantic"

- Verifique se `semantic.py` está em `govy/doctrine/`
- Rode `git status` para confirmar que arquivo foi adicionado
- Redeploy: `func azure functionapp publish func-govy-parse-test --python --build remote`

### Erro 404 no endpoint

- Aguarde 2 minutos (cold start)
- Verifique logs: `func azure functionapp logstream func-govy-parse-test`

### Arquivo não foi processado (already_processed)

- Use `force_reprocess=true` no request
- Ou delete o blob processado:
  ```powershell
  az storage blob delete `
    --connection-string $connString `
    --container-name doutrina-processed `
    --name "habilitacao/habilitacao/<source_sha>.json"
  ```

---

## 📝 PRÓXIMOS PASSOS

Após validação bem-sucedida:

1. ✅ Processar todos os arquivos de doutrina via batch
2. ✅ Revisar `semantic_chunks` com `coverage_status="INCERTO"`
3. ✅ Implementar interface de revisão jurídica
4. ✅ Indexar no Azure AI Search
5. ✅ Integrar no chatbot legal

---

**FIM DAS INSTRUÇÕES**
