# Relatório de Implementação — Fase 1: Fundação (Infraestrutura de Regras)

**Repositório:** govy-function-current
**Branch:** dev
**Commit:** 2931ec3
**Data:** 2026-02-17
**Implementado por:** Claude Opus 4.6

---

## 1) Contexto do Projeto

O repositório `govy-function-current` é um microserviço Azure Functions (Python 3.11) que já existia para extração de parâmetros de editais de licitação. Ele possui:

- **2 endpoints HTTP**: `POST /api/parse_layout` (OCR via Azure Document Intelligence) e `POST /api/extract_params` (extração de parâmetros)
- **4 extractors**: O001 (objeto), E001 (prazo de entrega), PG001 (prazo de pagamento), L001 (locais de entrega — 4 variantes)
- **1 quality gate**: avaliação de qualidade do OCR
- **0 testes**, **0 schemas formais**, **0 classificação de documentos**

A Fase 1 implementa a **infraestrutura de regras para classificação de documentos de TCEs** como módulo totalmente separado, sem alterar nenhum código existente.

---

## 2) Estrutura de Arquivos Criados

```
govy-function-current/
├── rules/
│   ├── core.json                              # 522 linhas — regras universais
│   └── tribunals/
│       └── tce-sp.json                        # 80 linhas — overlay TCE-SP
├── schemas/
│   └── output.schema.json                     # 78 linhas — contrato de saída
├── src/govy/
│   └── classification/
│       ├── __init__.py                        # package marker
│       └── compiler.py                        # 310 linhas — compilador de ruleset
└── tests/
    ├── __init__.py
    ├── fixtures/
    │   ├── core_test.json                     # fixture de teste (core minimal)
    │   └── overlay_test.json                  # fixture de teste (overlay minimal)
    └── unit/
        ├── __init__.py
        └── test_compiler.py                   # 291 linhas — 17 testes unitários
```

**Total: 10 arquivos, 1.556 linhas adicionadas.**

---

## 3) Detalhamento de Cada Entrega

### 3.1 `rules/core.json`

Implementado com a estrutura `tabs` exatamente conforme especificação. Contém:

#### tabs.CLASSES — 14 classes

| # | id | label | priority | whitelist | strong_hit | weak_hit | neg_penalty |
|---|---|---|---|---|---|---|---|
| 1 | cautelar | Cautelar / Liminar | 90 | true | 0.95 | 0.70 | -0.40 |
| 2 | representacao | Representação / Denúncia | 80 | true | 0.96 | 0.68 | -0.55 |
| 3 | pedido_reconsideracao | Pedido de Reconsideração | 78 | true | 0.95 | 0.65 | -0.30 |
| 4 | embargos_declaracao | Embargos de Declaração | 75 | true | 0.96 | 0.65 | -0.30 |
| 5 | sancoes | Sanções | 72 | true | 0.92 | 0.62 | -0.30 |
| 6 | recurso_ordinario | Recurso Ordinário | 70 | true | 0.95 | 0.60 | -0.40 |
| 7 | agravo | Agravo | 68 | true | 0.90 | 0.60 | -0.30 |
| 8 | termo_rescisao | Termo de Rescisão | 65 | true | 0.95 | 0.70 | -0.30 |
| 9 | contrato_gestao | Contrato de Gestão / OS | 60 | true | 0.95 | 0.65 | -0.30 |
| 10 | convenios_parcerias | Convênios / Parcerias | 55 | true | 0.90 | 0.60 | -0.30 |
| 11 | relatorio_fiscalizacao | Relatório / Auditoria / Inspeção | 50 | true | 0.95 | 0.60 | -0.30 |
| 12 | acompanhamento | Acompanhamento | 40 | true | 0.90 | 0.60 | -0.30 |
| 13 | contratos | Contratos (execução / genérico) | 20 | true | 0.85 | 0.55 | -0.40 |
| 14 | prestacao_contas | Prestação de Contas / Contas Anuais | 10 | **false** | 0.95 | 0.65 | -0.60 |

Cada classe possui:
- `id`, `label`, `enabled`, `priority`, `whitelist`
- `patterns`: { `strong`: [...], `weak`: [...], `negative`: [...] }
- `confidence_rules`: { `strong_hit`, `weak_hit`, `neg_hit_penalty` }
- `sources_priority`: lista ordenada de campos a consultar (ex: `["text_head", "caption_raw", "classe_raw", "ementa"]`)

Exemplos de patterns por classe:

**representacao** (strong):
- `\btrata-?se\s+de\s+representa[cç][aã]o\b`
- `\brepresenta[cç][aã]o\b\s+formulad[ao]\b`
- `\bden[uú]ncia\b`, `\bdenunciante\b`, `\bdenunciado\b`

**cautelar** (strong):
- `\bcautelar(es)?\b`, `\bliminar\b`, `\bmedida\s+cautelar\b`
- `\bsusta[cç][aã]o\b`, `\bsustar\b`, `\bsuspens[aã]o\b`

**prestacao_contas** (strong + negative):
- Strong: `\bcontas\s+anuais\b`, `\bpresta[cç][aã]o\s+de\s+contas\b`, `\bexerc[ií]cio:\s*\d{4}\b`
- Negative: `\bedital\b`, `\bpreg[aã]o\b`, `\bconcorr[eê]ncia\b` (guardrails para não descartar licitação)

#### tabs.PROCEDURES — 1 procedimento

| id | label | priority | strong_hit | weak_hit |
|---|---|---|---|---|
| exame_previo_edital | Procedimento: Exame Prévio de Edital | 85 | 1.0 | 0.75 |

Patterns strong:
- `\bEXAMES?\s+PR[ÉE]VIOS?\s+DE\s+EDITAL\b`
- `\bEXAME\s+PR[ÉE]VIO\s+DE\s+EDITAL\b`
- `\bEXAME\s+PR[ÉE]VIO\b[\s\S]{0,80}\bEDITAL\b`

**Decisão arquitetural:** `exame_previo_edital` é tratado como procedure/flag, NÃO como classe. Isso evita que EPE "engula" representação como classe primária.

#### tabs.TIE_BREAKERS — 9 regras core (genéricas multi-tribunal)

| # | id | priority | Condição | Ação |
|---|---|---|---|---|
| 1 | tb_repr_by_parties_header | 100 | when_any: Representante(s):/Representado(a):/Denunciante/Denunciado no text_head, ou "representação" no caption_raw | upweight representacao +0.20 |
| 2 | tb_recurso_by_term | 95 | when_any: "Pedido de Reconsideração"/"Recurso Ordinário" no text_head, "recurso" no caption_raw | upweight recurso_ordinario +0.25 |
| 3 | tb_embargos_by_term | 94 | when_any: "Embargos de Declaração" no text_head, "embargos" no caption_raw | upweight embargos_declaracao +0.25 |
| 4 | tb_cautelar_by_term | 93 | when_any: cautelar/liminar/medida de urgência no text_head, "cautelar" no caption_raw | upweight cautelar +0.25 |
| 5 | tb_relatorio_fisc_by_org_units | 85 | when_any: Diretoria/Departamento/Coordenadoria de Fiscalização, Relatório Técnico, Auditoria | upweight relatorio_fiscalizacao +0.20 |
| 6 | tb_acompanhamento_by_followup | 75 | when_any: acompanhamento/monitoramento, execução contratual/fiscalização do contrato | upweight acompanhamento +0.15 |
| 7 | tb_contratos_by_contract_terms | 70 | when_any: aditivo/apostilamento/reajuste/reequilíbrio, contratante:/contratada: | upweight contratos +0.15 |
| 8 | tb_contrato_gestao_by_os | 65 | when_any: contrato de gestão, organização social/OS | upweight contrato_gestao +0.25, downweight contratos -0.15 |
| 9 | tb_triage_contracts_vs_acomp_vs_fisc | 60 | when_any: vocabulário de fiscalização/contratos/acompanhamento | reforços suaves +0.10/+0.08/+0.08 |

Todas são "safe" para multi-tribunal: usam vocabulário jurídico universal, só dão ajustes de score (não forçam classe), e o `pick_primary()` final decide por score+priority.

#### tabs.EQUIVALENCES — 1 regra

```json
{
  "id": "eq_repr_plus_epe_proc",
  "baseline_any_of": [
    ["exame_previo_edital", "representacao"],
    ["exame_previo_edital"]
  ],
  "rules_primary": "representacao",
  "requires_procedure": "exame_previo_edital"
}
```

Se baseline marcou EPE+Representação e rules marcou primary=representacao + procedure=exame_previo_edital → não é divergência.

#### tabs.DESCARTE — 1 regra

```json
{
  "id": "discard_contas_anuais",
  "action": "mark_irrelevant",
  "flag": "IRRELEVANT_CONTAS",
  "match": {
    "pattern_all": ["\\b(Contas\\s+Anuais|Presta[cç][aã]o\\s+de\\s+Contas)\\b", "\\bExerc[ií]cio\\s*:\\s*20\\d{2}\\b"],
    "pattern_any": ["\\b[ÓO]rg[aã]o\\s*:\\b", "\\bRespons[aá]vel\\s*:\\b", "\\bUnidade\\s+Gestora\\b", "\\bOrdenador(a)?\\s+da\\s+Despesa\\b"],
    "guardrail_none": ["\\b(edital|preg[aã]o|concorr[eê]ncia|tomada\\s+de\\s+pre[cç]os|registro\\s+de\\s+pre[cç]os|ata\\s+de\\s+registro\\s+de\\s+pre[cç]os)\\b"]
  }
}
```

Lógica: `todos pattern_all` devem bater + `pelo menos 1 pattern_any` deve bater + `nenhum guardrail_none` pode bater.

#### globals

```json
{
  "regex_flags": ["IGNORECASE", "MULTILINE"],
  "normalize_accents": true,
  "confidence": {
    "class_prefilter_min": 0.85,
    "class_keep_min": 0.7,
    "stance_force_neutral_below": 0.7
  },
  "quote": {
    "min_chars": 200,
    "max_chars": 1800,
    "dedupe_similarity": 0.9
  }
}
```

#### meta

```json
{
  "ruleset_id": "core-v1",
  "created_at": "2026-02-17T00:00:00Z",
  "title": "Core rules v1 - universal TCE"
}
```

---

### 3.2 `rules/tribunals/tce-sp.json`

Overlay que adiciona variações locais do TCE-SP sem alterar o core.

**tabs.CLASSES — 2 overrides (append de patterns):**

`representacao` — adiciona strong:
- `\bREPRESENTANTE(S)?:\b`
- `\bREPRESENTAD[AO](S)?:\b`
- `\bRepresentante(s)?:\b`
- `\bRepresentada(s)?:\b`

`relatorio_fiscalizacao` — adiciona strong:
- `\bDIRETORIA\s+DE\s+FISCALIZA[CÇ][AÃ]O\b`
- `\bRELAT[ÓO]RIO\s+T[ÉE]CNICO\b`

**tabs.PROCEDURES — 1 override (append de patterns):**

`exame_previo_edital` — adiciona strong:
- `\bEXAME\s+PR[ÉE]VIO\s+DE\s+EDITAL\b`
- `\bEXAMES\s+PR[ÉE]VIOS\s+DE\s+EDITAL\b`

**tabs.TIE_BREAKERS — 2 regras locais:**

| id | priority | when | then |
|---|---|---|---|
| tce_sp_epe_does_not_override_representacao | 110 | `when_all`: EPE no head + REPRESENTANTE(S): + REPRESENTAD[AO](S): | `force_primary_class: representacao` + `add_procedure: exame_previo_edital` |
| tce_sp_epe_alone_add_procedure | 105 | `when_all`: EPE no head (sem exigir partes) | `add_procedure: exame_previo_edital` |

Priority 110 e 105 (maiores que todos os tie-breakers core) garantem que as regras TCE-SP são avaliadas primeiro.

**tabs.EQUIVALENCES — 1 regra local:**
- `baseline_epe_plus_repr_equivalence`: mesma lógica do core, reforço local.

**globals override:**
- `confidence.class_keep_min: 0.7`

---

### 3.3 `src/govy/classification/compiler.py`

**Função principal:**
```python
def load_ruleset(tribunal_id: str, *, rules_dir: Optional[Path] = None) -> CompiledRuleset
```

- `tribunal_id = "core"` → carrega só o core, sem overlay
- `tribunal_id = "tce-sp"` → carrega core + `rules/tribunals/tce-sp.json`, faz merge

**Data classes imutáveis (frozen=True):**

```python
@dataclass(frozen=True)
class CompiledClass:
    id: str
    label: str
    priority: int
    enabled: bool
    whitelist: bool
    confidence_rules: Dict[str, float]    # strong_hit, weak_hit, neg_hit_penalty
    sources_priority: List[str]
    strong_patterns: tuple[re.Pattern]    # pré-compilados
    weak_patterns: tuple[re.Pattern]
    negative_patterns: tuple[re.Pattern]

@dataclass(frozen=True)
class CompiledProcedure:
    id: str
    label: str
    priority: int
    enabled: bool
    scoring: Dict[str, float]             # strong_hit, weak_hit, neg_hit_penalty
    sources_priority: List[str]
    strong_patterns: tuple[re.Pattern]
    weak_patterns: tuple[re.Pattern]
    negative_patterns: tuple[re.Pattern]

@dataclass(frozen=True)
class CompiledRuleset:
    tribunal_id: str
    classes: Dict[str, CompiledClass]          # por id
    procedures: Dict[str, CompiledProcedure]   # por id
    tie_breakers: List[Dict]                   # raw JSON (executados na Fase 2)
    equivalences: List[Dict]                   # raw JSON
    discard_rules: List[Dict]                  # raw JSON
    globals: Dict[str, Any]
    tabs_raw: Dict[str, Any]                   # acesso ao merge bruto
    ruleset_hash: str                          # SHA256 hex (64 chars)
    core_version: str
    tribunal_version: Optional[str]
    compiled_at: str                           # ISO 8601 UTC
    meta: Dict[str, Any]
```

**Lógica de merge implementada:**

| Função | Comportamento |
|---|---|
| `_deep_merge_dict(a, b)` | Merge recursivo; b sobrescreve a em conflito |
| `_dedupe_preserve_order(items)` | Remove duplicatas mantendo ordem de inserção |
| `_merge_pattern_lists(base, overlay, replace)` | Se replace=True: substitui. Senão: append+dedupe |
| `_merge_patterns_dict(base, overlay)` | Suporta `_replace: {"strong": true}` para replace granular por strength |
| `_merge_rule_item(base, overlay)` | Merge de 1 item: patterns via merge_patterns_dict, dicts via deep_merge, escalares via overwrite |
| `_merge_tab_by_id(base_items, overlay_items)` | Merge de lista inteira por campo `id`. Items novos são appendados, existentes são merged |
| `_merge(core, overlay)` | Orquestrador: globals (deep), meta (deep), tabs mergeable por id, tabs overlay-only (append) |

**Tabs mergeáveis (core + overlay por id):** CLASSES, PROCEDURES, TEMAS, EFEITO, RESULTADO, STANCE, ALVO, QUOTES, DESCARTE

**Tabs overlay-only (core + overlay appendados):** TIE_BREAKERS, EQUIVALENCES — permite ter tie-breakers genéricos no core E locais no overlay.

**Validação (falha rápida com RulesetCompilationError):**
- Todos regex em CLASSES.patterns.strong/weak/negative
- Todos regex em PROCEDURES.patterns.strong/weak/negative
- Todos regex em TIE_BREAKERS.when_all/when_any/when_none[].regex
- Todos regex em DESCARTE.match.pattern_all/pattern_any/guardrail_none
- Campos obrigatórios: id, label, priority, patterns, confidence_rules (classes); id, patterns (procedures)
- Mensagem de erro indica exatamente qual tab/item/pattern falhou

**Hash:** SHA256 do JSON merged (json.dumps com sort_keys=True, ensure_ascii=False), calculado ANTES da pré-compilação de regex. Garante reprodutibilidade.

**Localização dos rules/:** `Path(__file__).resolve().parents[3] / "rules"` (sobe de `src/govy/classification/` até a raiz do repo). Override via parâmetro `rules_dir` para testes.

---

### 3.4 `schemas/output.schema.json`

Contrato de saída da classificação (JSON Schema draft-07):

```json
{
  "required": ["tribunal", "doc_id", "primary_class", "rules_confidence", "rules_status", "is_suspect", "ruleset_hash"],
  "properties": {
    "tribunal": "string",
    "doc_id": "string",
    "primary_class": "string | null",
    "secondary_classes": "string[]",
    "procedures": "string[]",
    "rules_confidence": "number (0-1)",
    "rules_status": "enum: OK_RULES | LOW_CONF_RULES | UNCLASSIFIED | IRRELEVANT_CONTAS",
    "is_suspect": "boolean",
    "is_irrelevant": "boolean",
    "evidence": "array of { class_id, pattern, strength, snippet, score_delta }",
    "ruleset_hash": "string (SHA256)"
  },
  "additionalProperties": true
}
```

`additionalProperties: true` para permitir campos de debug futuros sem quebrar validação.

---

### 3.5 Testes Unitários — 17 testes, todos passando

```
$ python -m pytest tests/unit/test_compiler.py -v
17 passed in 0.24s
```

| # | Teste | O que valida |
|---|---|---|
| 1 | test_load_core_only | Core carrega sem overlay; 2 classes, 1 procedure, 1 tie-breaker (fixture) |
| 2 | test_load_with_overlay | Core + overlay merge; versions corretas |
| 3 | test_append_patterns | Overlay sem _replace faz append de patterns |
| 4 | test_replace_patterns | Overlay com `_replace: {"strong": true}` substitui lista inteira |
| 5 | test_globals_override | Deep merge de globals; overlay sobrescreve class_keep_min, preserva normalize_accents |
| 6 | test_invalid_regex_fails_fast | Regex inválido em CLASSES gera RulesetCompilationError |
| 7 | test_missing_tribunal_fails | Tribunal inexistente gera FileNotFoundError |
| 8 | test_hash_deterministic | Mesmo input → mesmo hash SHA256 (64 chars hex) |
| 9 | test_required_fields_class | Classe sem confidence_rules gera erro claro |
| 10 | test_patterns_precompiled | Todos patterns são re.Pattern (classes e procedures) |
| 11 | test_append_dedupe | Append de pattern duplicado não cria cópia |
| 12 | test_tie_breakers_merge | Core tie-breakers + overlay tie-breakers ambos presentes no resultado |
| 13 | test_tie_breaker_invalid_regex | Regex inválido em TIE_BREAKERS.when_any falha rápido |
| 14 | test_procedures_merge | Procedures fazem merge correto (append de patterns) |
| 15 | test_compiled_class_fields | CompiledClass tem todos campos esperados (id, label, priority, enabled, whitelist, confidence_rules, sources_priority) |
| 16 | test_production_core_loads | rules/core.json real: 14 classes, 1 procedure, 9+ tie-breakers, 1 discard |
| 17 | test_production_tce_sp_loads | rules/tribunals/tce-sp.json real: merge ok, patterns TCE-SP presentes, tie-breakers core+locais presentes |

Testes 1-15 usam fixtures isoladas (`tests/fixtures/core_test.json` + `overlay_test.json`) para não depender dos rules de produção.

Testes 16-17 validam os arquivos reais de produção (core.json e tce-sp.json).

---

## 4) Diferenças em Relação à Especificação Original

### 4.1 Implementado exatamente conforme pedido

- Estrutura `tabs` com CLASSES, PROCEDURES, TIE_BREAKERS, EQUIVALENCES, DESCARTE
- `confidence_rules` com strong_hit/weak_hit/neg_hit_penalty por classe
- `sources_priority` por classe
- `whitelist` flag (prestacao_contas = false)
- `exame_previo_edital` como procedure/flag, não como classe
- 14 classes conforme lista final v1
- Merge por id com append+dedupe
- Deep merge de globals
- Hash SHA256 + versionamento (core_version, tribunal_version, compiled_at)
- 9 tie-breakers genéricos core (multi-tribunal)
- Tie-breakers TCE-SP: EPE não engole representação (force_primary_class + add_procedure)
- Equivalência semântica: baseline EPE+Repr = rules Repr + procedure EPE
- Descarte de contas com guardrails de licitação (pattern_all/pattern_any/guardrail_none)
- Overlay TCE-SP com patterns locais (Representante/Representada, Diretoria de Fiscalização)

### 4.2 Decisões de implementação (variações)

| Item | Especificação original | Implementação | Razão |
|---|---|---|---|
| Convenção de replace de patterns | Duas opções mencionadas: `"replace": true` dentro de patterns OU `"_replace": {"strong": true}` | Adotado `_replace: {"strong": true}` dentro de patterns | Mais granular: permite replace por strength individualmente (ex: replace strong mas append weak) |
| TIE_BREAKERS e EQUIVALENCES no core | "Vêm só do overlay" | Core TAMBÉM pode ter TIE_BREAKERS e EQUIVALENCES; overlay appenda | Necessário para os 9 tie-breakers genéricos que valem para qualquer tribunal |
| `tabs_raw` no CompiledRuleset | Não mencionado | Adicionado | Permite acesso aos dados brutos do merge (TIE_BREAKERS, EQUIVALENCES, DESCARTE como raw JSON) sem precisar reprocessar |
| `meta` no CompiledRuleset | Mencionado mas não detalhado | Implementado com deep merge core+overlay | Rastreabilidade: ruleset_id, created_at, title |
| Validação de regex em TIE_BREAKERS e DESCARTE | Não explicitado na spec | Implementado | Falha rápida é crítica — regex inválido em tie-breaker quebraria em runtime silenciosamente |
| Tabs mergeáveis futuras | Mencionadas (TEMAS, EFEITO, RESULTADO, STANCE, ALVO, QUOTES) | Definidas no código mas sem conteúdo no core.json ainda | Infra pronta para expansão; adicionar conteúdo quando necessário sem mudar o compiler |

### 4.3 O que NÃO foi implementado (pertence a Fases 2 e 3)

| Item | Motivo | Fase |
|---|---|---|
| `score_classes()` — scoring de classes por documento | Engine de classificação = Fase 2 | 2 |
| `detect_procedures()` — detecção de procedures | Engine = Fase 2 | 2 |
| `pick_primary()` — seleção de classe primária por score+priority | Engine = Fase 2 | 2 |
| `apply_discard_rules()` — execução das regras de descarte | Engine = Fase 2 | 2 |
| `apply_actions()` — execução dos tie-breakers (upweight/downweight/force/add) | Engine = Fase 2 | 2 |
| `run_rules_engine()` — orquestrador completo do pipeline | Engine = Fase 2 | 2 |
| `is_equivalent()` — avaliador de equivalências semânticas | Divergência = Fase 2 | 2 |
| `compute_divergence()` — divergência baseline vs rules | Divergência = Fase 2 | 2 |
| `is_suspect()` — lógica de suspects baseada em rules_conf/status | Suspects = Fase 2 | 2 |
| `build_debug_payload()` — logging com top_scores, top_hits, tie_break_applied | Debug = Fase 2 | 2 |
| Spot check CLI (`--tribunal tce-sp --n 200 --random`) | Validação = Fase 2 | 2 |
| Segunda passada com rules_text para low confidence | Retry = Fase 2 | 2 |
| Golden set (~50 docs TCE-SP) | Gate de regressão = Fase 3 | 3 |
| Gates de aceitação (UNCLASSIFIED %, suspects %, distribuição) | Métricas = Fase 3 | 3 |
| `ADD_NEW_TRIBUNAL.md` — doc de onboarding | Documentação = Fase 3 | 3 |

**Nota:** As estruturas de dados para tudo acima (TIE_BREAKERS, EQUIVALENCES, DESCARTE, confidence_rules, sources_priority) já estão no JSON e acessíveis via `CompiledRuleset.tie_breakers`, `.equivalences`, `.discard_rules`, `.classes[id].confidence_rules`, etc. A Fase 2 precisa apenas implementar a lógica de execução usando essas estruturas.

---

## 5) Resultados dos Testes

```
$ python -m pytest tests/unit/test_compiler.py -v
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-9.0.2, pluggy-1.6.0

tests/unit/test_compiler.py::test_load_core_only PASSED
tests/unit/test_compiler.py::test_load_with_overlay PASSED
tests/unit/test_compiler.py::test_append_patterns PASSED
tests/unit/test_compiler.py::test_replace_patterns PASSED
tests/unit/test_compiler.py::test_globals_override PASSED
tests/unit/test_compiler.py::test_invalid_regex_fails_fast PASSED
tests/unit/test_compiler.py::test_missing_tribunal_fails PASSED
tests/unit/test_compiler.py::test_hash_deterministic PASSED
tests/unit/test_compiler.py::test_required_fields_class PASSED
tests/unit/test_compiler.py::test_patterns_precompiled PASSED
tests/unit/test_compiler.py::test_append_dedupe PASSED
tests/unit/test_compiler.py::test_tie_breakers_merge PASSED
tests/unit/test_compiler.py::test_tie_breaker_invalid_regex PASSED
tests/unit/test_compiler.py::test_procedures_merge PASSED
tests/unit/test_compiler.py::test_compiled_class_fields PASSED
tests/unit/test_compiler.py::test_production_core_loads PASSED
tests/unit/test_compiler.py::test_production_tce_sp_loads PASSED

============================= 17 passed in 0.24s ==============================
```

### Teste manual do compilador:

```python
>>> from govy.classification.compiler import load_ruleset

>>> rs = load_ruleset("core")
>>> len(rs.classes)
14
>>> len(rs.procedures)
1
>>> len(rs.tie_breakers)
9
>>> len(rs.discard_rules)
1

>>> rs = load_ruleset("tce-sp")
>>> len(rs.classes)
14
>>> len(rs.tie_breakers)
11  # 9 core + 2 tce-sp
>>> len(rs.classes["representacao"].strong_patterns)
9  # 5 core + 4 tce-sp
>>> rs.ruleset_hash[:16]
'a3b2...'  # determinístico, muda se qualquer rule mudar
```

---

## 6) Próximos Passos — Fase 2 (Pipeline)

O compilador está pronto e testado. A Fase 2 implementará o engine de classificação usando o `CompiledRuleset`:

1. **`score_classes(compiled, doc_fields)`** — scoring por classe usando confidence_rules e sources_priority
2. **`detect_procedures(compiled, doc_fields)`** — detecção de procedures com threshold
3. **`pick_primary(scores, class_defs)`** — seleção por score+priority
4. **`apply_discard_rules(compiled, doc_fields, scores, result)`** — execução de DESCARTE com guardrails
5. **`apply_actions(result, scores, actions)`** — execução de TIE_BREAKERS (upweight, downweight, force_primary_class, add_procedure, add_secondary_class, mark_irrelevant)
6. **`run_rules_engine(compiled, doc_fields)`** — orquestrador completo
7. **`is_equivalent(baseline, rules_result, compiled)`** — equivalências semânticas
8. **`compute_divergence(baseline, rules_result, compiled)`** — divergência com equivalência
9. **`is_suspect(doc, compiled)`** — suspects baseados em rules_status/rules_confidence
10. **Spot check CLI** — `--tribunal tce-sp --n 200 --random`
11. **Segunda passada** — rules_text para documentos com confidence < 0.70

Todo o pseudo-código já foi fornecido. As estruturas de dados estão prontas no CompiledRuleset.

---

## 7) Issues no Linear (Govy-KB)

| Issue | ID | Status |
|---|---|---|
| Fase 1 - Fundação: Infraestrutura de Regras | GOV-14 | Backlog (parent) |
| Criar rules/core.json | GOV-15 | Backlog (sub-issue de GOV-14) |
| Criar rules/tribunals/tce-sp.json | GOV-16 | Backlog (sub-issue de GOV-14) |
| Implementar ruleset_compiler.py | GOV-17 | Backlog (sub-issue de GOV-14) |
| Definir output schema mínimo | GOV-18 | Backlog (sub-issue de GOV-14) |
| Testes unitários do compiler | GOV-19 | Backlog (sub-issue de GOV-14) |
| Fase 2 - Pipeline: Classificador e Spot Check | GOV-20 | Backlog |
| Fase 3 - Estabilização: Qualidade e Onboarding | GOV-21 | Backlog |

Todas as sub-issues de GOV-14 foram implementadas e testadas. Status no Linear ainda não foi atualizado (pode ser feito agora).
