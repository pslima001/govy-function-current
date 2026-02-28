# Analise Estrategica de Dados — Govy

> Documento gerado a partir de analise profunda do codebase. Fevereiro/2026.

---

## 1. Mapa do que o Govy ja possui hoje

| Camada | O que faz | Arquivos-chave |
|--------|-----------|----------------|
| **Parse de editais** | Extrai texto + tabelas de PDFs via Azure DI | `govy/api/parse_layout.py` |
| **Parametros basicos (4)** | Objeto, Prazo Entrega, Prazo Pagamento, Locais de Entrega | `govy/extractors/` |
| **Parametros amplos (32)** | Consorcio, Subcontratacao, Garantias, Sustentabilidade, etc. — 100% regex, custo zero | `govy/extractors/parametros_amplos/` |
| **Extracao de itens** | Itens de licitacao com CATMAT/CATSER, qtde, valores | `govy/extractors/items/` |
| **KB Jurisprudencia** | Acordaos TCE/TCU parseados: ementa, dispositivo, effect, partes | `govy/api/tce_parser_v3.py` |
| **Busca hibrida KB** | Vector + semantic + text com fallback de jurisdicao e modo | `govy/api/kb_search.py` |
| **Doutrina** | Chunks semanticos de livros juridicos com sanitizacao | `govy/doctrine/` |
| **Legislacao** | Pipeline de ingestao de leis/decretos/INs com chunking estrutural | `govy/legal/pipeline.py`, `packages/govy_kb_legal/` |
| **Multi-LLM** | 5 LLMs votam no melhor candidato extraido | `govy/api/consult_llms.py` |
| **Monitoramento GovBR** | Watch runner para novas normas | `govy/legal/watch_runner.py` |

---

## 2. Dados dificeis de replicar por concorrentes

Estes sao dados que criam **moats** (barreiras competitivas) porque exigem tempo acumulado, curadoria humana especializada, ou efeito de rede.

### 2.1 Grafo de Jurisprudencia Cruzada com Legislacao

**O que e:** Hoje o `tce_parser_v3.py` ja extrai `references` e `linked_processes` de acordaos, e o pipeline de legislacao ja tem a tabela `legal_relation` (revoga, altera, regulamenta). Mas esses dois grafos estao **desconectados**.

**Oportunidade:** Cruzar automaticamente:
- Acordao TCE-SP 123/2024 → cita Art. 75, IV da Lei 14.133/2021
- Mesmo Art. 75 foi alterado pelo Decreto X → o acórdão pode estar desatualizado
- Quantos acórdãos citam o mesmo dispositivo → "autoridade" do artigo

**Por que e dificil de replicar:**
- Requer os dois lados (jurisprudencia + legislacao) ja parseados e normalizados
- A extração de citacoes legais dentro de acórdãos (regex + NLP) exige tuning continuo
- O grafo so fica rico com **volume**: centenas de milhares de acórdãos x milhares de dispositivos
- Cada mes que passa sem que um concorrente comece, e mais um mes de vantagem acumulada

**Dados derivados:**
- `artigo_mais_controverso[etapa][uf]` — quais artigos geram mais litígio
- `tendencia_jurisprudencial[artigo][ano]` — se esta RIGORIZA ou FLEXIBILIZA ao longo do tempo
- `risco_vigencia` — alerta quando legislação citada em acórdão foi revogada/alterada

### 2.2 Historico de Parametros por Orgao Comprador

**O que e:** Cada edital que o Govy processa gera 36+ parametros extraidos. Se o sistema armazenar esses parametros indexados por orgao (CNPJ, UASG, etc.), ao longo do tempo constroi um perfil de comportamento de cada orgao comprador.

**Por que e dificil de replicar:**
- E um **dado acumulativo**: so existe se voce processou os editais historicos daquele orgao
- Quanto mais editais processados, mais preciso o perfil
- Concorrentes precisariam reprocessar anos de PDFs para ter algo similar

**Dados derivados:**
- `perfil_orgao[uasg]` — "este orgao sempre exige visita tecnica, nunca aceita consorcio, prazo medio de pagamento 30 dias"
- `anomalia_edital` — "este edital exige garantia de 10%, mas o historico do orgao e 5%"
- `benchmark_orgao` — comparar parametros de um edital contra a media do orgao, da UF, e nacional

### 2.3 Base Curada de Doutrina Semantica

**O que e:** O `govy/doctrine/semantic.py` ja faz algo raro: extrai chunks semanticos de doutrina com `tese_neutra`, `explicacao_conceitual`, `limites_e_cuidados`, `argument_role`, tudo sanitizado (sem revelar autor, sem citar tribunal, sem afirmar consenso).

**Por que e dificil de replicar:**
- Requer **livros especializados** como fonte (nao e dado publico scrapeable)
- A sanitizacao (remover autorias, consensos, mencoes a tribunais) e um pipeline complexo e unico
- Os red flags (`LINGUAGEM_NAO_NEUTRA`, `AUTORIA_REMOVIDA`) + review humano criam qualidade crescente
- A classificacao `COMPLETO/PARCIAL/INCERTO` + `argument_role` e um schema proprietario

### 2.4 Mapa de Partes e Empresas Envolvidas em Decisoes

**O que e:** O `extract_partes()` no `tce_parser_v3.py` ja extrai partes (CONTRATANTE, CONTRATADA, RESPONSAVEL, ADVOGADO, etc.) com classificacao (PUBLICA/PRIVADA/PF), CNPJ/CPF, e cargo.

**Oportunidade de cruzamento:**
- Empresa X foi sancionada em 3 acórdãos do TCE-SP e 1 do TCU
- O prefeito Y foi responsavel em 5 processos irregulares
- A empresa Z ganhou 80% das licitacoes do orgao W (sinal de direcionamento?)

**Por que e dificil de replicar:**
- Exige parsing de alta qualidade dos cabecalhos de acórdãos (regex fino + heurísticas)
- O cruzamento so funciona com volume (deduplica por CNPJ)
- Nenhum concorrente esta fazendo isso de forma automatizada

---

## 3. Dados que aumentam a capacidade de analise das licitacoes

### 3.1 Score de Risco do Edital (Risk Score)

**O que e:** Combinar os 36+ parametros extraidos em um **score unico de risco** para o licitante.

**Como construir (ja tem os dados):**

| Fator de risco | Fonte no Govy | Peso sugerido |
|----------------|---------------|---------------|
| Exige visita tecnica obrigatoria | `r_visita_tecnica` | +15 |
| Garantia de execucao > 5% | `r_garantia_execucao` | +10 |
| Prazo de entrega < 5 dias | `e001_entrega` | +20 |
| Nao permite consorcio | `r_consorcio` | +5 |
| Exige capital minimo | `r_capital_minimo` | +10 |
| Exige escritorio local | `r_escritorio_local` | +15 |
| Exige certificacao ambiental | `r_certificacao_ambiental` | +8 |
| Inversao de fases | `r_inversao_fases` | -5 (favorece) |
| Subcontratacao permitida | `r_subcontratacao` | -5 (favorece) |
| Jurisprudencia indica RIGORIZA para parametro | `kb_search` | +10 por parametro |

**Resultado:** "Este edital tem Risk Score 72/100 — alto risco para PMEs."

### 3.2 Checklist Automatico de Habilitacao

**O que e:** A partir dos parametros extraidos, gerar automaticamente o checklist de documentos que o licitante precisa apresentar.

**Dados ja disponiveis:**
- `r_atestado_tecnico` → "Precisa de atestado"
- `r_quant_minimo_atestado` → "Minimo de X% do quantitativo"
- `r_garantia_proposta` → "Precisa apresentar garantia de proposta"
- `r_capital_minimo` → "Precisa comprovar capital de R$ X"
- `r_certificacao_ambiental` → "Precisa de ISO 14001"
- `r_programa_integridade` → "Precisa de programa de integridade"

**Dados a criar:**
- Cruzar com `kb_search(scenario=1/2)` para cada parametro → "TCE-SP ja flexibilizou essa exigencia" ou "TCU determina que e obrigatorio"

### 3.3 Analise Comparativa (Benchmark)

**O que e:** Comparar os parametros de um edital especifico contra:
1. Media do mesmo orgao comprador (historico)
2. Media da mesma UF
3. Media nacional para o mesmo tipo de objeto

**Dados necessarios (parcialmente existem):**
- Os 36 parametros extraidos → ja existem
- Classificacao do objeto (CATMAT/CATSER) → `item_extractor.py` ja extrai
- Armazenamento historico indexado por orgao/UF/objeto → **precisa criar**

### 3.4 Linha do Tempo Juridica do Edital

**O que e:** Para cada clausula relevante do edital, mostrar:
1. Qual artigo de lei fundamenta a clausula
2. Se esse artigo ja foi objeto de decisao TCE/TCU
3. Se a decisao RIGORIZA ou FLEXIBILIZA a interpretacao
4. Se existe doutrina relevante sobre o tema

**Dados ja disponiveis:**
- `kb_search` com `scenario` e `procedural_stage`
- `legal_chunk` + `legal_provision` para legislacao
- `doctrine semantic chunks` para doutrina
- `effect` (RIGORIZA/FLEXIBILIZA/CONDICIONAL)

**O que falta:** O conector automatico "clausula do edital → dispositivo legal → jurisprudencia"

### 3.5 Deteccao de Clausulas Restritivas a Competitividade

**O que e:** O `tce_parser_v3.py` ja tem `CLAIM_PATTERNS` que detectam:
- `RESTRICAO_COMPETITIVIDADE`
- `PRAZO_EXIGUO`
- `PESQUISA_PRECO_INSUFICIENTE`
- `DOCUMENTO_NOVO_DILIGENCIA`
- `DISPENSA_INEXIGIBILIDADE`
- `PARECER_JURIDICO_GENERICO`

**Oportunidade:** Aplicar esses mesmos patterns **no texto do edital** (nao so em acórdãos), para alertar o licitante: "Esta clausula do edital pode ser impugnada — veja 3 acórdãos que anularam clausulas similares."

---

## 4. Dados que aumentam a produtividade

### 4.1 Templates de Impugnacao/Recurso Pre-Preenchidos

**O que e:** Quando o sistema detecta uma clausula restritiva, pode gerar automaticamente um rascunho de impugnacao citando:
- O dispositivo legal violado (ex: Art. 9 da Lei 14.133/2021)
- Jurisprudencia favoravel (ex: Acórdão TCU 1234/2023)
- Doutrina de suporte (chunk semantico relevante)

**Dados ja disponiveis:**
- `claim_patterns` para detectar o tipo de irregularidade
- `kb_search(scenario=1, uf=X)` para jurisprudencia favoravel
- `legal_chunk` para citacao exata do dispositivo legal
- `doctrine chunks` para fundamentacao doutrinaria

### 4.2 Match Automatico Edital → Empresa

**O que e:** Com base nos itens extraidos (`item_extractor.py` com CATMAT/CATSER), nos locais de entrega (`l001`), e nos requisitos de habilitacao, fazer match com um perfil de empresa pre-cadastrado.

**Dados a criar:**
- Perfil da empresa: CNAE, UF, capital social, certificacoes, atestados
- Motor de match: item CATMAT/CATSER x CNAE, locais de entrega x UF, requisitos x capacidade

**Resultado:** "3 novas licitacoes compativeis com sua empresa hoje."

### 4.3 Monitoramento de Mudancas Legislativas com Impacto

**O que e:** O `watch_runner.py` ja monitora o GovBR. Mas pode ir alem:
- Nova IN publicada → rodar `legal_chunker` → cruzar com `legal_relation` → identificar quais acórdãos na KB ficam potencialmente desatualizados → alertar clientes que usaram esses acórdãos

**Dados ja disponiveis:**
- `legal_source` com `status_hint` e `ingest_status`
- `legal_relation` com tipos (revoga, altera, regulamenta)
- `is_current` nos acórdãos (calculado por ano)

**O que falta:** A automacao do fluxo "nova norma → impacto na KB → alerta"

### 4.4 Dicionario de Termos Licitatorios Contextualizado

**O que e:** Ja existe um endpoint `govy/api/dicionario_api.py`. Pode ser enriquecido com:
- Definicao doutrinaria (chunks com `argument_role=DEFINICAO`)
- Jurisprudencia que definiu o termo
- Artigo de lei que cria/regulamenta o conceito
- Exemplos praticos de editais que usam o termo

### 4.5 API de Pre-Analise Instantanea

**O que e:** Pipeline que em 1 chamada recebe o PDF e retorna:
1. Todos os 36 parametros extraidos (regex, custo zero)
2. Risk Score
3. Checklist de habilitacao
4. Top 3 alertas jurisprudenciais
5. Itens com classificacao CATMAT/CATSER

**Dados ja existem** — falta apenas a orquestracao em um endpoint unico.

---

## 5. Matriz de priorizacao

| Iniciativa | Impacto | Dificuldade | Moat | Prioridade |
|-----------|---------|-------------|------|-----------|
| Score de Risco do Edital | Alto | Baixa (dados ja existem) | Medio | **P0** |
| Checklist Automatico de Habilitacao | Alto | Baixa | Medio | **P0** |
| API de Pre-Analise Instantanea | Alto | Baixa (orquestracao) | Baixo | **P0** |
| Historico de Parametros por Orgao | Alto | Media (precisa storage) | **Alto** | **P1** |
| Deteccao de Clausulas Restritivas no Edital | Alto | Media (adaptar claim_patterns) | Alto | **P1** |
| Grafo Jurisprudencia x Legislacao | Muito Alto | Alta | **Muito Alto** | **P1** |
| Match Edital → Empresa | Alto | Media | Medio | **P2** |
| Mapa de Partes/Empresas | Alto | Media | **Muito Alto** | **P2** |
| Templates de Impugnacao | Alto | Alta (requer curadoria) | Alto | **P2** |
| Benchmark Comparativo | Medio | Media | Alto | **P2** |
| Linha do Tempo Juridica | Medio | Alta | Alto | **P3** |
| Monitoramento de Impacto Legislativo | Medio | Alta | Alto | **P3** |
| Dicionario Contextualizado | Baixo | Baixa | Baixo | **P3** |

---

## 6. Dados que podem ser cruzados HOJE (sem nova infraestrutura)

Estes cruzamentos usam apenas dados que o Govy ja extrai:

### 6.1 Parametro do edital x Jurisprudencia

```
Para cada parametro extraido (ex: r_garantia_execucao = "5%"):
  → kb_search(query="garantia de execucao 5%", scenario=2, uf=UF_do_edital)
  → Retorna acórdãos relevantes com effect=RIGORIZA ou FLEXIBILIZA
  → Gera: "TCE-SP ja considerou 5% abusivo em 2 decisoes"
```

### 6.2 Partes de acórdãos x Partes de acórdãos

```
Para cada empresa extraida em partes_privadas de um acórdão:
  → Buscar CNPJ em todos os outros acórdãos
  → Construir: "Empresa X foi sancionada 3x, absolvida 1x"
  → Alerta: se essa empresa aparece como licitante no edital atual
```

### 6.3 Objeto do edital x Itens extraidos

```
Objeto extraido pelo o001 (ex: "aquisicao de medicamentos"):
  → Cruzar com itens do item_extractor (CATMAT especificos)
  → Validar se os itens sao coerentes com o objeto declarado
  → Detectar: "Objeto diz medicamentos mas item 5 e equipamento medico"
```

### 6.4 Dispositivo legal citado x Vigencia

```
Acórdão cita "Art. 30, II da Lei 8.666/93":
  → legal_relation mostra: Lei 8.666 foi revogada pela Lei 14.133/2021
  → Alerta: "Este acórdão cita legislacao revogada — verificar aplicabilidade"
```

---

## 7. Resumo executivo

O Govy ja possui uma **infraestrutura de dados excepcionalmente rica** que poucos concorrentes tem:

1. **36+ parametros extraidos por edital** (4 com LLM, 32 com regex puro)
2. **KB de jurisprudencia** com parser deterministico de alta qualidade
3. **Doutrina semantica** com sanitizacao e classificacao unicas
4. **Legislacao estruturada** com relacoes e vigencia
5. **Extracao de itens** com CATMAT/CATSER
6. **Extracao de partes** com classificacao de tipo

As maiores oportunidades de **moat competitivo** estao em:
- **Cruzar esses dados entre si** (jurisprudencia x legislacao x parametros x orgao)
- **Acumular dados historicos** por orgao comprador (efeito de rede temporal)
- **Manter e expandir a base de doutrina** (ativo proprietario)

As maiores oportunidades de **produtividade** estao em:
- **Score de risco** e **checklist automatico** (impacto imediato, dados ja existem)
- **Pre-analise instantanea** em um unico endpoint (orquestracao simples)
- **Match edital-empresa** (requer perfil de empresa, mas items ja existem)
