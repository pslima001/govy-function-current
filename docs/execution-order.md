# Ordem de Execução do Motor de Classificação

Documento de referência para a pipeline de classificação de documentos de TCEs.
Cada etapa recebe o resultado da anterior e produz entrada para a próxima.

---

## Visão Geral

```
Documento ──► 1. DESCARTE ──► 2. CLASSES ──► 3. PROCEDURES ──► 4. TIE_BREAKERS ──► 5. EQUIVALENCES ──► 6. STATUS ──► Resultado
```

---

## Etapas

### 1. DESCARTE (Pré-filtro)

**Objetivo:** Eliminar documentos irrelevantes antes de gastar processamento com classificação.

**Entrada:** Texto bruto do documento (text_head, caption_raw, etc.)

**Lógica:**
- Para cada regra em `DESCARTE` (ordenadas por prioridade):
  - Se `pattern_all` → todas devem dar match
  - Se `pattern_any` → ao menos uma deve dar match
  - Se `guardrail_none` → nenhuma pode dar match (se alguma deu match, o descarte é cancelado)
- Se a regra dispara: marca `is_irrelevant = true` com a flag correspondente e **interrompe** o pipeline.

**Saída:** `is_irrelevant: bool`, `irrelevant_flag: str | null`

**Se irrelevante:** Retorna resultado mínimo sem prosseguir para etapas 2-6.

---

### 2. CLASSES (Classificação Primária)

**Objetivo:** Identificar a classe principal do documento por score de confiança.

**Entrada:** Texto do documento + lista de classes compiladas

**Lógica:**
- Para cada classe habilitada (`enabled: true`):
  - Percorrer `sources_priority` na ordem definida
  - Para cada source, testar patterns: `strong`, `weak`, `negative`
  - Calcular score usando `confidence_rules`:
    - `strong_hit` → score base para hit forte
    - `weak_hit` → score base para hit fraco
    - `neg_hit_penalty` → penalidade por hit negativo
  - Score final = max(strong, weak) + neg_hit_penalty (se aplicável)
- Filtrar classes com score ≥ `globals.confidence.class_keep_min`
- Ordenar por score (desc), depois por priority (desc) para desempate
- Primeira = `primary_class`, demais = `secondary_classes`

**Saída:** `primary_class`, `secondary_classes[]`, `confidence`, `evidence[]`

---

### 3. PROCEDURES (Flags de Procedimento)

**Objetivo:** Detectar procedimentos que coexistem com a classe (ex: Exame Prévio de Edital).

**Entrada:** Texto do documento + lista de procedures compiladas

**Lógica:**
- Para cada procedure habilitada:
  - Testar patterns (strong, weak, negative) no mesmo esquema de sources_priority
  - Calcular score usando `scoring`
  - Se score ≥ threshold mínimo → adicionar à lista de procedures detectadas

**Saída:** `procedures[]` (lista de procedure IDs detectados)

**Nota:** Procedures NÃO competem com classes. Um documento pode ter `primary_class: representacao` e `procedures: [exame_previo_edital]` simultaneamente.

---

### 4. TIE_BREAKERS (Desempate e Ajustes)

**Objetivo:** Aplicar regras condicionais para resolver ambiguidades e ajustar scores.

**Entrada:** Resultado das etapas 2 e 3 + texto do documento

**Lógica:**
- Ordenar TIE_BREAKERS por `priority` (desc)
- Para cada regra habilitada:
  - Avaliar condições:
    - `when_all`: TODAS devem dar match
    - `when_any`: ao menos uma deve dar match
    - `when_none`: NENHUMA pode dar match
  - Se condições satisfeitas, executar ações em `then`:
    - `upweight_class(class_id, delta)`: soma delta ao score da classe
    - `downweight_class(class_id, delta)`: subtrai delta do score
    - `force_primary_class(class_id)`: define como classe primária independente de score
    - `add_procedure(procedure_id)`: adiciona procedure à lista
    - `add_secondary_class(class_id)`: adiciona classe secundária
    - `mark_irrelevant()`: marca como irrelevante
- Recalcular ranking após todos os ajustes

**Saída:** `primary_class` (possivelmente alterada), scores ajustados

---

### 5. EQUIVALENCES (Reconciliação com Baseline)

**Objetivo:** Detectar quando resultado do motor difere do baseline apenas na forma, não na substância.

**Entrada:** Resultado final da classificação + resultado do baseline (se disponível)

**Lógica:**
- Para cada regra de equivalência:
  - Verificar se baseline combina com algum grupo em `baseline_any_of`
  - Verificar se rules produziu `rules_primary` como classe principal
  - Se `requires_procedure` definido, verificar se o procedure foi detectado
  - Se todas condições atendidas: marcar como equivalente (não é divergência)

**Saída:** `is_equivalent: bool`, `equivalence_id: str | null`

**Nota:** Esta etapa é de reconciliação, não altera a classificação. Serve para calcular métricas de divergência (convergent vs divergent vs equivalent).

---

### 6. STATUS (Decisão Final)

**Objetivo:** Produzir o resultado final com status e flag de suspeita.

**Entrada:** Todos os resultados anteriores

**Lógica:**
- Se `primary_class` tem `whitelist: false` → `is_suspect: true` (documento provavelmente irrelevante para licitantes)
- Se `confidence < globals.confidence.class_keep_min` → `is_suspect: true`
- Definir `rules_status`:
  - `"classified"` → classificação confiável
  - `"low_confidence"` → abaixo do threshold
  - `"irrelevant"` → marcado como irrelevante (etapa 1 ou tie-breaker)
  - `"unclassified"` → nenhuma classe deu match

**Saída:** Objeto final conforme `schemas/output.schema.json`

---

## Diagrama de Decisão

```
                    ┌──────────┐
                    │ Documento│
                    └────┬─────┘
                         │
                    ┌────▼─────┐
                    │ DESCARTE │
                    └────┬─────┘
                         │
                   irrelevante?
                    ╱          ╲
                  sim          não
                  │              │
            ┌─────▼──────┐  ┌───▼────┐
            │ Retorna     │  │ CLASSES │
            │ is_irrelevant│  └───┬────┘
            └─────────────┘      │
                            ┌────▼──────┐
                            │ PROCEDURES│
                            └────┬──────┘
                                 │
                          ┌──────▼───────┐
                          │ TIE_BREAKERS │
                          └──────┬───────┘
                                 │
                          ┌──────▼────────┐
                          │ EQUIVALENCES  │
                          └──────┬────────┘
                                 │
                            ┌────▼───┐
                            │ STATUS │
                            └────┬───┘
                                 │
                           ┌─────▼──────┐
                           │  Resultado  │
                           └────────────┘
```

---

## Referências

- `rules/core.json` — Classes, procedures, tie-breakers, equivalences, discard rules
- `rules/tribunals/*.json` — Overlays por tribunal
- `schemas/output.schema.json` — Contrato de saída
- `src/govy/classification/compiler.py` — Compilador de regras (Fase 1)
