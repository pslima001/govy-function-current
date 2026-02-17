# KB CONTENT HUB - INSTRUÇÕES DE DEPLOY
# Data: 05/02/2026

## ARQUIVOS INCLUÍDOS

```
kb_content_hub/
├── govy/
│   ├── juris/
│   │   ├── __init__.py           # Módulo juris (side-effect free)
│   │   └── metadata_extract.py   # Detecção de tribunais e números
│   └── api/
│       ├── kb_juris_paste.py     # Endpoint POST /api/kb/juris/paste
│       └── kb_content_admin.py   # Endpoints list/approve/reject/update/delete
├── function_app_additions.py     # Código para adicionar ao function_app.py
└── kb_content_hub.html           # Frontend web
```

## PASSO 1: COPIAR ARQUIVOS PARA A VM

Na VM (C:\govy\repos\govy-function-current):

```powershell
# 1.1 Criar pasta juris
New-Item -ItemType Directory -Force -Path "govy\juris"

# 1.2 Os arquivos .py precisam ser transferidos via base64
# Use o Claude para obter cada arquivo individualmente
```

## PASSO 2: ADICIONAR ENDPOINTS AO function_app.py

Abra `function_app.py` e adicione o conteúdo de `function_app_additions.py` antes do final do arquivo.

## PASSO 3: GIT ADD + COMMIT

```powershell
git status
git add govy/juris/__init__.py
git add govy/juris/metadata_extract.py
git add govy/api/kb_juris_paste.py
git add govy/api/kb_content_admin.py
git add function_app.py
git commit -m "Add KB Content Hub: paste jurisprudencia + CRUD"
```

## PASSO 4: DEPLOY

```powershell
func azure functionapp publish func-govy-parse-test --python --build remote
```

## PASSO 5: AGUARDAR 2 MINUTOS E TESTAR

```powershell
$url = "https://func-govy-parse-test-exabasfqgsfgexhd.eastus-01.azurewebsites.net"
$key = "<AZURE_FUNCTION_KEY>"

# Verificar diagnostic
Invoke-RestMethod -Uri "$url/api/diagnostic_full" | ConvertTo-Json -Depth 5
# Deve mostrar kb_juris_paste.py e kb_content_admin.py em govy_api_files
```

## PASSO 6: UPLOAD DO FRONTEND

```powershell
az storage blob upload `
  --account-name stgovyparsetestsponsor `
  --container-name '$web' `
  --file "kb_content_hub.html" `
  --name "kb_content_hub.html" `
  --overwrite
```

## PASSO 7: ACESSAR O FRONTEND

URL: https://stgovyparsetestsponsor.z13.web.core.windows.net/kb_content_hub.html

1. Cole a Function Key no campo de configuração
2. Clique em "Salvar"
3. Cole um texto de jurisprudência
4. Clique em "Analisar e Salvar"

## ENDPOINTS CRIADOS

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| /api/kb/juris/paste | POST | Colar texto de jurisprudência |
| /api/kb/content/list | GET | Listar conteúdos (filtros: review_status, tribunal_family) |
| /api/kb/content/{id}/approve | POST | Aprovar e indexar no kb-legal |
| /api/kb/content/{id}/reject | POST | Rejeitar |
| /api/kb/content/{id}/update | POST | Atualizar metadados |
| /api/kb/content/{id}/delete | POST | Soft delete (mode=soft) ou hard delete (mode=hard) |

## CONTAINERS CRIADOS AUTOMATICAMENTE

- `kb-raw` - Textos originais
- `kb-processed` - JSONs processados
- `kb-trash` - Soft deletes

## TROUBLESHOOTING

### Erro 404 no endpoint
- Verificar se arquivos foram tracked no git (`git status`)
- Verificar se deploy foi feito

### Erro de import
- Verificar se `__init__.py` existe em `govy/juris/`
- Verificar se é side-effect free

### Container não existe
- Os containers são criados automaticamente no primeiro uso
