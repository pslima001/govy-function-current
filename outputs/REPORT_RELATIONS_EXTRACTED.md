# REPORT: Relations & Vigencia Extraction

**Data**: 2026-02-23 (v2 — com resolucao de target_doc_id)
**Script**: `scripts/run_extractors.py`
**Modulos**: `govy/legal/relation_extractor.py` + `govy/legal/effective_date_extractor.py`

---

## Execucao

- **Input**: 82 documentos do legal_document (Postgres)
- **Source**: blobs em `normas-juridicas-raw` (stgovyparsetestsponsor)
- **Output**: 118 relacoes em legal_relation + datas atualizadas em legal_document
- **Resultado**: 82/82 OK, 0 erros, 55.5s
- **Override**: Lei 14.133/2021 published_at/effective_from fixado via `overrides.json`

---

## Relation Extractor

### Padroes Implementados

| Pattern | Tipo | Confidence | Matches |
|---------|------|------------|---------|
| RE_REVOGA_EXPLICITA | revoga | high | 9 |
| RE_REVOGA_FICAM | revoga | high | 0 |
| RE_REVOGAM_SE | revoga | low | 1 |
| RE_ALTERA | altera | high | 10 |
| RE_REGULAMENTA | regulamenta | high | 2 |
| RE_REF_NORMA | referencia | low | 96 |
| RE_PASSA_VIGORAR | (detector) | - | (nao gera relacao direta) |

### Target Resolution (v2)

| Metrica | v1 | v2 | Delta |
|---------|----|----|-------|
| Total relacoes | 118 | 118 | = |
| target_doc_id resolvidos | 0 | **16** | +16 |
| % resolved | 0% | **13.6%** | +13.6pp |
| High-confidence resolvidos | 0/22 | **8/22** | +8 |
| Low-confidence resolvidos | 0/96 | **8/96** | +8 |

**Causa da melhoria**: Fix no `_TYPE_MAP` do relation_extractor (v1 gerava `instrucao_normativa_5_2017` mas DB usa `in_5_2017`). Adicionado tambem fallback para leading zeros (e.g. `in_02_2010` → `in_2_2010`).

### Resolved Targets (16)

| Fonte | Tipo | Target | Resolved doc_id | Confidence |
|-------|------|--------|-----------------|------------|
| in_07_2018 | altera | IN 5/2017 | in_5_2017_federal_br | high |
| in_10_2020 | altera | IN 3/2018 | in_3_2018_federal_br | high |
| in_107_2020 | altera | IN 3/2018 | in_3_2018_federal_br | high |
| in_3_2019 | altera | IN 2/2018 | in_2_2018_federal_br | high |
| in_49_2020 | altera | IN 5/2017 | in_5_2017_federal_br | high |
| in_5_2022 | altera | IN 3/2015 | in_3_2015_federal_br | high |
| in_79_2024 | altera | IN 73/2022 | in_73_2022_federal_br | high |
| in_96_2020 | altera | IN 6/2019 | in_6_2019_federal_br | high |
| in_103_2022 | referencia | IN 96/2022 | in_96_2022_federal_br | low |
| in_103_2022 | referencia | IN 73/2022 | in_73_2022_federal_br | low |
| in_65_2021 | referencia | IN 5/2017 | in_5_2017_federal_br | low |
| in_67_2021 | referencia | IN 65/2021 | in_65_2021_federal_br | low |
| in_73_2020 | referencia | IN 5/2017 | in_5_2017_federal_br | low |
| in_81_2022 | referencia | IN 65/2021 | in_65_2021_federal_br | low |
| portaria_6521_2025 | referencia | IN 82/2025 | in_82_2025_federal_br | low |
| portaria_7604_2025 | referencia | IN 82/2025 | in_82_2025_federal_br | low |

### Unresolved High-Confidence Targets (14)

Documentos referenciados que NAO existem no DB (82-doc corpus):

| Fonte | Tipo | Target | Razao |
|-------|------|--------|-------|
| in_3_2018 | revoga | IN 02/2010 | IN 2/2010 nao esta no corpus |
| in_3_2015 | revoga | IN 7/2012 | IN 7/2012 nao esta no corpus |
| in_4_2018 | revoga | IN 5/1998 | IN 5/1998 nao esta no corpus |
| in_5_2017 | revoga | IN 2/2008 | IN 2/2008 nao esta no corpus |
| in_51_2021 | revoga | IN 8/2018 | IN 8/2018 nao esta no corpus |
| in_91_2022 | revoga | IN 72/2021 | IN 72/2021 nao esta no corpus |
| in_210_2019 | revoga | IN 3/2011 | IN 3/2011 nao esta no corpus |
| in_26_2022 | revoga | IN 43/2020 | IN 43/2020 nao esta no corpus |
| in_412_2025 | revoga | IN 10/2018 | IN 10/2018 nao esta no corpus |
| portaria_2162_2024 | revoga | Portaria 179/2019 | Portaria nao esta no corpus |
| in_42_2021 | altera | IN 53/2020 | IN 53/2020 nao esta no corpus |
| in_62_2021 | altera | IN 53/2020 | IN 53/2020 nao esta no corpus |
| in_6_2019 | regulamenta | Decreto 9.764/2019 | Decreto nao esta no corpus |
| in_96_2020 | regulamenta | Decreto 9.764/2019 | Decreto nao esta no corpus |

### Unresolved Low-Confidence (distinct targets, 38)

Referencia genericas a normas nao presentes no DB. Exemplos mais frequentes:

- Lei 14.133 (sem ano) — 20+ citacoes, nao resolve por falta de ano no regex
- Lei 8.666/1993 — referencia historica, doc ausente
- Lei 12.527/2011 — LAI, doc ausente
- Decreto 9.764/2019 — regulamenta imoveis da Uniao, doc ausente
- Decreto 11.246/2022, Decreto 3.722/2001, etc. — decretos auxiliares

**Acao para melhorar resolution rate**: adicionar PDFs das 10 leis core ausentes ao blob e re-rodar.

### Observacoes

1. **96 referencias genericas** (low confidence, needs_review=true) — citacoes "nos termos da Lei X" que indicam correlacao
2. **22 relacoes high confidence** — revogacoes (10), alteracoes (10), regulamentacoes (2)
3. **8/10 alteracoes resolvidas** — as 2 nao resolvidas referenciam IN 53/2020 (ausente)
4. **0/10 revogacoes resolvidas** — todas referenciam documentos revogados (mais antigos, nao no corpus)
5. **Lei 14.133/2021** tem 7 referencias (a mais conectada)

### Limitacoes Conhecidas

- Nao detecta revogacao tacita (norma posterior regula mesma materia sem mencionar anterior)
- Nao detecta alteracao de artigos especificos ("o Art. X da Lei Y passa a vigorar...")
- Referencia sem ano nao gera doc_id (ex: "Lei 12.846" sem "/YYYY") — afeta ~20 citacoes da Lei 14.133

---

## Effective Date Extractor

### Padroes Implementados

| Pattern | Descricao | Matches |
|---------|-----------|---------|
| RE_PUBLICACAO_DOU | "publicada no DOU de DD/MM/AAAA" | ~75 |
| RE_DOU_EXTENSO | "DOU de DD de MES de AAAA" | ~6 |
| RE_VIGOR_PUBLICACAO | "entra em vigor na data de sua publicacao" | 36 |
| RE_VIGOR_DATA | "entra em vigor em DD de MES de AAAA" | 11 |
| RE_VIGOR_DIAS | "entra em vigor apos N dias" | 6 |
| RE_EFEITOS | "produz efeitos a partir de DD/MM/AAAA" | 0 |

### Resultados

| Metrica | Valor |
|---------|-------|
| published_at extraido (auto) | 81/82 (98.8%) |
| published_at com override | **82/82 (100%)** |
| effective_from extraido | 53/82 (64.6%) |
| effective_from com override | **54/82 (65.9%)** |
| status_vigencia = "vigente" | **55/82 (67.1%)** |
| status_vigencia = "desconhecido" | 27/82 (32.9%) |

### Overrides Aplicados

| doc_id | Campo | Valor | Motivo |
|--------|-------|-------|--------|
| lei_14133_2021_federal_br | published_at | 2021-04-01 | OCR sem padrao DOU |
| lei_14133_2021_federal_br | effective_from | 2021-04-01 | OCR sem data, vigor na publicacao |
| lei_14133_2021_federal_br | status_vigencia | vigente | Conhecida em vigor |

Overrides sao aplicados APOS os extractors automaticos via `normas-juridicas-registry/federal/overrides.json`.

---

## DB Schema (Migration 007)

```sql
-- legal_document: datas e status de vigencia
ALTER TABLE legal_document
    ADD COLUMN published_at DATE,
    ADD COLUMN effective_from DATE,
    ADD COLUMN effective_to DATE,
    ADD COLUMN status_vigencia VARCHAR(30) DEFAULT 'desconhecido';

-- legal_provision: vigencia por dispositivo
ALTER TABLE legal_provision
    ADD COLUMN valid_from DATE,
    ADD COLUMN valid_to DATE,
    ADD COLUMN status_vigencia VARCHAR(30) DEFAULT 'vigente';

-- legal_relation: evidence
ALTER TABLE legal_relation
    ADD COLUMN confidence VARCHAR(10) DEFAULT 'low',
    ADD COLUMN needs_review BOOLEAN DEFAULT true,
    ADD COLUMN evidence_text TEXT,
    ADD COLUMN evidence_pattern VARCHAR(200),
    ADD COLUMN evidence_position INTEGER;
```

---

## Arquivos

| Arquivo | Funcao |
|---------|--------|
| `govy/legal/relation_extractor.py` | Extrai revoga/altera/regulamenta/referencia + resolve target_doc_id |
| `govy/legal/effective_date_extractor.py` | Extrai published_at/effective_from/status_vigencia |
| `govy/legal/registry_overrides.py` | Aplica overrides manuais ao DB |
| `govy/db/migrations/007_add_vigencia_fields.sql` | DDL para campos de vigencia + evidence |
| `scripts/run_extractors.py` | Batch runner (blob → extract → write DB → apply overrides) |
| `scripts/ingest_core_pack.py` | Ingere leis core do manifest que estejam no blob |
| `normas-juridicas-registry/federal/overrides.json` | Overrides manuais de metadata |
| `normas-juridicas-registry/federal/federal_core_manifest.json` | Manifest de leis core (1 present, 10 missing) |
| `outputs/extractors_report_v2.json` | Report JSON completo |
