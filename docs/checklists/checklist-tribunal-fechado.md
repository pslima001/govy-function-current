# Checklist "TRIBUNAL FECHADO" — Baseline

Standard operacional para fechar um tribunal após full run do scraper + parsing completo.
**Todos os itens são obrigatórios salvo indicação (Opcional).**

---

## 0) Documentos / Artefatos

- [ ] `outputs/REPORT_<TRIBUNAL>_FINAL.md` com carimbo `<TRIBUNAL> FECHADO`
- [ ] `outputs/run_summary_<tribunal>.json` (machine-readable)
- [ ] `outputs/<tribunal>_missing*.txt` (quando houver missing — ver distinção na seção 1a)
- [ ] (Opcional) `outputs/<tribunal>_sample_keys.json` (lista de blobs auditados + timestamps)

## 1) Inventário e Cobertura

- [ ] Contagem em `juris-raw`:
  - PDFs: **N**
  - JSON do scraper (se existir): **N** (ou "não aplicável")
- [ ] Contagem em `kb-raw`: JSONs **M**
- [ ] Diff explicado: `N - M = X` com classificação:
  - [ ] `terminal_skip_non_decision_attachment`
  - [ ] `no_pdf` / 404 genuíno
  - [ ] `image-only` / sem texto extraível
  - [ ] outros (explicar)
- [ ] Poison queue do run atual = **0**
- [ ] Queue main no fim = **0** (ou explicar por que não é usado)

### 1a) Exceções Formais — `kb-raw/_exceptions/`

Toda exceção deve ser **registrada formalmente** em `kb-raw/_exceptions/<tribunal>_*.json`.

**Distinção obrigatória:**

| Categoria | Significado | Onde registrar | Ação futura |
|-----------|-------------|----------------|-------------|
| `terminal_skip` | Classificado e descartado intencionalmente (attachment, despacho, image-only, não-decisão) | `kb-raw/_exceptions/<tribunal>_terminal_skip.json` | Nunca reprocessar. Registrado com `reason` + `doc_id`. |
| `missing` | Existe em `juris-raw` mas NÃO gerou `kb-raw` e NÃO foi classificado como terminal_skip | `outputs/<tribunal>_missing*.txt` | **Investigar.** Pode ser bug no parser, PDF corrompido, ou caso não previsto. |
| `no_pdf` | Scraper encontrou o registro mas PDF não existe no tribunal | `kb-raw/_exceptions/<tribunal>_no_pdf.json` | Registrar e monitorar (pode aparecer depois). |

**Asserts obrigatórios:**
- [ ] `terminal_skip + no_pdf + missing + kb-raw_count == juris-raw_pdf_count` (soma fecha)
- [ ] Todo item em `_exceptions/` tem: `doc_id`, `reason`, `timestamp`, `source_blob`
- [ ] `missing` = **0** (ou cada item investigado e justificado no report)
- [ ] Arquivo `_exceptions/` é JSON array válido, ordenado por `doc_id`

**Formato padrão de `_exceptions/<tribunal>_terminal_skip.json`:**
```json
[
  {
    "doc_id": "tce-xx--12345",
    "reason": "non_decision_attachment",
    "detail": "Documento é despacho administrativo, não acórdão",
    "source_blob": "juris-raw/tce-xx/acordaos/tce-xx--12345/decisao.pdf",
    "timestamp": "2026-02-24T10:30:00Z"
  }
]
```

## 2) "Config is Source of Truth"

Verificar que os campos abaixo vêm do config/registry, **não** do texto do PDF:

- [ ] `kb_doc.tribunal` (ex.: TCE, TCU, TCM)
- [ ] `kb_doc.uf` (quando aplicável)
- [ ] `kb_doc.region` (quando aplicável e definido como padrão)
- [ ] `kb_doc.authority_score` = o valor do registry
- [ ] `source` / `tribunal_name` (quando padronizado por config)

**Evidência**: asserts em amostras + explicação no report.

## 3) Auditoria Mínima

Executar e listar as chaves completas dos blobs auditados + timestamps:

### Amostra A (random)
- [ ] 15 JSONs aleatórios (seed fixo)
- [ ] Listar: `blob_name`, `metadata.processed_at`

### Amostra B (estratificada por tempo)
- [ ] 5 mais antigos + 5 medianos + 5 mais recentes (por `lastModified` do blob em kb-raw)
- [ ] Listar: `blob_name`, `lastModified`, `metadata.processed_at`

### Asserts obrigatórios (todos PASS)
- [ ] `kb_doc.tribunal == "<...>"`
- [ ] `kb_doc.uf == "<UF>"` (se aplicável)
- [ ] `kb_doc.region == "<REGIAO>"` (se aplicável)
- [ ] `kb_doc.authority_score == <score_registry>`
- [ ] `metadata.parser_version == "<parser_id/version>"`

## 4) Validação de Schema Mínimo

Toda entrada em `kb-raw` deve aderir ao schema mínimo. Validar em **100% dos blobs** (scan completo).

### 4a) Schema `kb_doc` (campos obrigatórios)

| Campo | Tipo | Regra |
|-------|------|-------|
| `doc_id` | string | não vazio, match com padrão `<tribunal>--*` |
| `tribunal` | string | valor do registry (ex.: `TCE`, `TCU`, `TCM`) |
| `uf` | string | 2 chars uppercase, quando aplicável |
| `authority_score` | float | `0.0 < score <= 1.0`, igual ao registry |
| `content` | string | não vazio, >= 50 chars (ou justificar) |
| `ementa` | string | presente (pode ser vazio se parser não encontrou — registrar) |
| `data_sessao` | string/null | formato `YYYY-MM-DD` ou null (nunca string vazia) |
| `citation` | string/null | presente em amostras (ou regra de fallback documentada) |
| `source` | string | não vazio |
| `tipo_documento` | string | não vazio (ex.: `acordao`, `decisao`, `resolucao`) |

### 4b) Schema `metadata` (campos obrigatórios no blob metadata)

| Campo | Tipo | Regra |
|-------|------|-------|
| `parser_version` | string | match com `parser_id` do registry |
| `processed_at` | string | formato ISO 8601 |
| `source_blob` | string | path do blob em `juris-raw` que originou este kb-raw |
| `tribunal_id` | string | match com ID do tribunal no registry |

### Asserts
- [ ] **0 blobs** faltando campos obrigatórios de `kb_doc`
- [ ] **0 blobs** faltando campos obrigatórios de `metadata`
- [ ] **0 blobs** com `doc_id` que não segue o padrão do tribunal
- [ ] **0 blobs** com `authority_score` diferente do registry
- [ ] **0 blobs** com `data_sessao` em formato inválido (aceitar null, rejeitar `""` ou formatos errados)

## 5) Sanidade de Conteúdo

- [ ] Scan completo:
  - [ ] `kb_doc.content` vazio = **0**
  - [ ] `kb_doc.content` < 50 chars = **0** (ou justificar exceções)
  - [ ] `citation` presente em amostras (ou regra de fallback)

## 6) Legado / Não Usado (obrigatório)

Inventariar e documentar TODOS os artefatos legacy ou não utilizados do tribunal.

### 6a) `juris-parsed/<tribunal>/`
- [ ] Status: **"vazio e não utilizado"** OU **"utilizado"** (contagem e função)
- [ ] Se vazio: confirmar que nenhum código referencia este prefixo
- [ ] Se tem dados: explicar origem, se devem ser migrados ou deletados

### 6b) Poison queues antigas
- [ ] `<tribunal>-poison` queue: **existe?** Contagem atual?
- [ ] Se count > 0: listar doc_ids, classificar (são do run atual ou de runs anteriores?)
- [ ] Se são de runs anteriores: investigar e limpar (com backup antes)
- [ ] Decisão documentada no report: "limpa", "mantida porque X", ou "não existe"

### 6c) Containers / prefixos deprecated
- [ ] `tce-jurisprudencia/<tribunal>/` (prefixo antigo): confirmar **read-only / não usado**
- [ ] Outros prefixos legacy: inventariar e marcar como deprecated no report
- [ ] Nenhum código em produção referencia artefatos legacy

### 6d) Blobs órfãos
- [ ] Blobs em `juris-raw/<tribunal>/` que NÃO são PDFs nem JSONs do scraper (ex.: `.tmp`, `.partial`)
- [ ] Contagem de órfãos = **0** (ou listar e explicar)

## 7) Estrutura de Storage

- [ ] Confirmar prefixos e naming:
  - `juris-raw/<tribunal>/acordaos/{doc_id}/decisao.pdf`
  - `juris-raw/<tribunal>/acordaos/{doc_id}/metadata.json`
  - `kb-raw/<tribunal>--...--...json`
- [ ] Consistência: **100%** dos blobs seguem a convenção de naming

## 8) Reprodutibilidade

- [ ] Report inclui os comandos exatos:
  - deploy
  - enqueue / execução
  - contagens
  - auditoria
  - checagem de filas
- [ ] Commit/PR:
  - [ ] commit hash do fix
  - [ ] link do PR e comentário com evidências (se aplicável)

---

## Estrutura de Outputs (padrão)

```
outputs/
  REPORT_<TRIBUNAL>_FINAL.md
  run_summary_<tribunal>.json
  <tribunal>_missing_*.txt

kb-raw/
  _exceptions/
    <tribunal>_terminal_skip.json
    <tribunal>_no_pdf.json

juris-raw/
  <tribunal>/_runs/YYYY-MM-DD/   (checkpoint + summary)
```
