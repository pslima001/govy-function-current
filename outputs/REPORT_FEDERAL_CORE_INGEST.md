# REPORT: Federal Core Ingest + Vigencia Layer

**Data**: 2026-02-23
**Pipeline**: Fase 1 (Registry + Chunking) + Camada Normativa (vigencia + relacoes)

---

## 1. Resumo Executivo

| Metrica | Valor |
|---------|-------|
| Documentos no DB | 82 |
| Provisions (artigos/pars/incisos) | 4.184 |
| Chunks | 1.272 |
| Relacoes detectadas | 118 |
| Docs com published_at | 81/82 (98.8%) |
| Docs com effective_from | 53/82 (64.6%) |
| Docs status "vigente" | 54/82 (65.9%) |
| Docs status "desconhecido" | 28/82 (34.1%) |
| Erros de processamento | 0 |
| Tempo de execucao (extractors) | 49.8s |

---

## 2. Composicao por Tipo

| Tipo | Total | Vigentes | Com published_at |
|------|-------|----------|------------------|
| Instrucao Normativa | 70 | 44 | 70 |
| Portaria | 7 | 7 | 7 |
| Resolucao | 4 | 2 | 4 |
| Lei | 1 | 1 | 0* |

*Lei 14.133/2021: vigor_pattern=RE_VIGOR_PUBLICACAO detectado (status=vigente), mas published_at nao encontrada no texto OCR.

---

## 3. Datas Extraidas

### 3.1. Distribuicao

| Categoria | Qtd |
|-----------|-----|
| published_at = effective_from (mesma data) | 36 |
| So published_at (sem effective_from) | 28 |
| published_at != effective_from (datas diferentes) | 17 |
| Nenhuma data | 1 |

### 3.2. Padroes de Vigencia Detectados

- **RE_VIGOR_PUBLICACAO** ("entra em vigor na data de sua publicacao"): padrao dominante — 36 docs
- **RE_VIGOR_DATA** ("entra em vigor em DD de MES de AAAA"): 11 docs com data especifica
- **RE_VIGOR_DIAS** ("entra em vigor apos N dias"): 6 docs com vacatio
- **RE_EFEITOS** ("produz efeitos a partir de"): 0 docs (nenhum match neste corpus)
- **Nenhum padrao** (published_at extraido via DOU, mas sem clausula de vigencia): 28 docs

### 3.3. Doc sem published_at

- `lei_14133_2021_federal_br` — PDF grande (280K chars), texto OCR sem padrao "publicada no DOU"

### 3.4. Docs sem effective_from (29 total)

Documentos onde published_at foi extraida mas nenhum padrao de vigencia foi encontrado no texto. Status definido como "desconhecido". Exemplos:
- `in_01_2010_federal_br`, `in_5_2017_federal_br`, `in_62_2021_federal_br`
- `resolucao_4_2024_federal_br`, `resolucao_8_2025_federal_br`
- Possiveis causas: padrao de vigencia em formato nao coberto, ou ausencia de clausula explicita

---

## 4. Relacoes Detectadas

### 4.1. Resumo

| Tipo | Qtd | Confidence |
|------|-----|------------|
| referencia (correlata) | 96 | low (needs_review=true) |
| altera | 10 | high |
| revoga | 10 | high (9) + low (1*) |
| regulamenta | 2 | high |
| **Total** | **118** | 22 high, 96 low |

*1 revogacao generica ("revogam-se as disposicoes em contrario")

### 4.1b. Target Resolution (v2)

| Metrica | Valor |
|---------|-------|
| target_doc_id resolvidos | **16/118 (13.6%)** |
| High-confidence resolvidos | **8/22 (36.4%)** |
| Low-confidence resolvidos | **8/96 (8.3%)** |
| Alteracoes resolvidas | 8/10 |
| Revogacoes resolvidas | 0/10 (targets nao no corpus) |
| Regulamentacoes resolvidas | 0/2 (Decreto nao no corpus) |

### 4.2. Relacoes High Confidence

#### Revogacoes (10) — 0 resolvidas
| Fonte | Revoga | Target doc_id |
|-------|--------|---------------|
| in_210_2019 | IN 3/2011 | - (nao no corpus) |
| in_26_2022 | IN 43/2020 | - (nao no corpus) |
| in_3_2015 | IN 7/2012 | - (nao no corpus) |
| in_3_2018 | IN 02/2010 | - (nao no corpus) |
| in_412_2025 | IN 10/2018 | - (nao no corpus) |
| in_4_2018 | IN 5/1998 | - (nao no corpus) |
| in_51_2021 | IN 8/2018 | - (nao no corpus) |
| in_5_2017 | IN 2/2008 | - (nao no corpus) |
| in_91_2022 | IN 72/2021 | - (nao no corpus) |
| portaria_2162_2024 | Portaria 179/2019 | - (nao no corpus) |

#### Alteracoes (10) — 8 resolvidas
| Fonte | Altera | Target doc_id |
|-------|--------|---------------|
| in_07_2018 | IN 5/2017 | **in_5_2017_federal_br** |
| in_10_2020 | IN 3/2018 | **in_3_2018_federal_br** |
| in_107_2020 | IN 3/2018 | **in_3_2018_federal_br** |
| in_3_2019 | IN 2/2018 | **in_2_2018_federal_br** |
| in_42_2021 | IN 53/2020 | - (nao no corpus) |
| in_49_2020 | IN 5/2017 | **in_5_2017_federal_br** |
| in_5_2022 | IN 3/2015 | **in_3_2015_federal_br** |
| in_62_2021 | IN 53/2020 | - (nao no corpus) |
| in_79_2024 | IN 73/2022 | **in_73_2022_federal_br** |
| in_96_2020 | IN 6/2019 | **in_6_2019_federal_br** |

#### Regulamentacoes (2) — 0 resolvidas
| Fonte | Regulamenta | Target doc_id |
|-------|-------------|---------------|
| in_6_2019 | Decreto 9.764/2019 | - (decreto nao no corpus) |
| in_96_2020 | Decreto 9.764/2019 | - (decreto nao no corpus) |

**Nota**: 14/22 high-confidence targets nao resolvidos porque os documentos referenciados nao existem no corpus de 82 docs. Adicionando mais documentos ao blob automaticamente melhora a resolucao.

### 4.3. Top 10 Docs por Quantidade de Relacoes

| doc_id | Relacoes |
|--------|----------|
| lei_14133_2021_federal_br | 7 |
| in_2_2023_federal_br | 5 |
| in_81_2022_federal_br | 5 |
| in_12_2023_federal_br | 5 |
| in_67_2021_federal_br | 5 |
| in_5_2017_federal_br | 5 |
| in_96_2022_federal_br | 4 |
| in_73_2022_federal_br | 4 |
| in_103_2022_federal_br | 4 |
| in_3_2018_federal_br | 4 |

---

## 5. Infraestrutura

| Componente | Detalhe |
|------------|---------|
| DB | pg-govy-legal (Flexible Server B1ms, brazilsouth) |
| Database | govy_legal |
| Migrations | 7 aplicadas (001-007) |
| Storage | stgovyparsetestsponsor / normas-juridicas-raw |
| Tabelas | jurisdiction(28), legal_document(82), legal_provision(4184), legal_chunk(1272), legal_relation(118) |

---

## 6. Leis Core Federais — Status

| Lei | doc_id | Status |
|-----|--------|--------|
| Lei 14.133/2021 (Nova Licitacoes) | lei_14133_2021_federal_br | PRESENTE (1468 provisions, 248 chunks) |
| Lei 8.666/1993 (Antiga Licitacoes) | - | AUSENTE |
| Lei 10.520/2002 (Pregao) | - | AUSENTE |
| Lei 12.462/2011 (RDC) | - | AUSENTE |
| LC 123/2006 (ME/EPP) | - | AUSENTE |
| Decreto 10.024/2019 (Pregao Eletronico) | - | AUSENTE |
| Decreto 7.892/2013 (SRP) | - | AUSENTE |
| Lei 12.527/2011 (LAI) | - | AUSENTE |
| Lei 13.303/2016 (Estatais) | - | AUSENTE |
| Lei 14.981/2024 | - | AUSENTE |
| Decreto 12.807 | - | AUSENTE |

**1 presente, 10 ausentes** — PDFs precisam ser obtidos e uploadados ao blob.

---

## 7. Proximos Passos

1. **Obter PDFs das 10 leis ausentes** e fazer upload ao blob + ingestao
2. **Melhorar regex de vigencia** para capturar mais padroes (29 docs sem effective_from)
3. **Fase 2**: Evidence Gate — validacao cruzada de referencias e resolucao de target_doc_id
4. **Fase 3**: Deteccao de conflitos entre normas (revogacao parcial, alteracao de artigos)
5. **Deploy** do codigo ao Function App (push + CI + deploy)
