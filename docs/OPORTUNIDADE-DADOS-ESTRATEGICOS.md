# Oportunidade: Analise Estrategica de Dados — Govy

> **Status:** Oportunidade identificada
> **Data:** 2026-02-28
> **Contexto:** Analise de ativos de dados existentes, cruzamentos possiveis e priorizacao estrategica

---

## O que o Govy ja possui hoje

| Camada | O que faz |
|--------|-----------|
| **Parse de editais** | Extrai texto + tabelas de PDFs via Azure DI |
| **4 parametros basicos** | Objeto, Prazo Entrega, Prazo Pagamento, Locais de Entrega |
| **32 parametros amplos** | Consorcio, Subcontratacao, Garantias, Sustentabilidade, etc. — 100% regex, custo zero |
| **Extracao de itens** | Itens de licitacao com CATMAT/CATSER, qtde, valores |
| **KB Jurisprudencia** | Acordaos TCE/TCU parseados: ementa, dispositivo, effect, partes |
| **Busca hibrida KB** | Vector + semantic + text com fallback de jurisdicao |
| **Doutrina** | Chunks semanticos de livros juridicos com sanitizacao |
| **Legislacao** | Pipeline de ingestao de leis/decretos/INs com chunking estrutural |
| **Multi-LLM** | 5 LLMs votam no melhor candidato extraido |
| **Monitoramento GovBR** | Watch runner para novas normas |

---

## 1. DADOS DIFICEIS DE REPLICAR POR CONCORRENTES

### 1.1 Grafo de Jurisprudencia Cruzada com Legislacao

Hoje o parser de acordaos ja extrai `references` e `linked_processes`, e o pipeline de legislacao ja tem a tabela `legal_relation` (revoga, altera, regulamenta). Mas esses dois grafos estao **desconectados**.

**Oportunidade:** Cruzar automaticamente:
- Acordao TCE-SP 123/2024 cita Art. 75, IV da Lei 14.133/2021
- Mesmo Art. 75 foi alterado pelo Decreto X → o acordao pode estar desatualizado
- Quantos acordaos citam o mesmo dispositivo → "autoridade" do artigo

**Por que e dificil de replicar:**
- Requer os dois lados (jurisprudencia + legislacao) ja parseados e normalizados
- A extracao de citacoes legais dentro de acordaos exige tuning continuo
- O grafo so fica rico com **volume**: centenas de milhares de acordaos x milhares de dispositivos
- Cada mes que passa sem que um concorrente comece, e mais um mes de vantagem acumulada

**Dados derivados:**
- `artigo_mais_controverso[etapa][uf]` — quais artigos geram mais litigio
- `tendencia_jurisprudencial[artigo][ano]` — se esta RIGORIZA ou FLEXIBILIZA ao longo do tempo
- `risco_vigencia` — alerta quando legislacao citada em acordao foi revogada/alterada

---

### 1.2 Historico de Parametros por Orgao Comprador

Cada edital processado gera 36+ parametros. Se armazenar indexados por orgao (CNPJ, UASG), ao longo do tempo constroi um **perfil de comportamento** de cada orgao comprador.

**Por que e dificil de replicar:**
- E um dado **acumulativo**: so existe se voce processou os editais historicos daquele orgao
- Quanto mais editais processados, mais preciso o perfil
- Concorrentes precisariam reprocessar anos de PDFs

**Dados derivados:**
- `perfil_orgao[uasg]` — "este orgao sempre exige visita tecnica, nunca aceita consorcio, prazo medio de pagamento 30 dias"
- `anomalia_edital` — "este edital exige garantia de 10%, mas o historico do orgao e 5%"
- `benchmark_orgao` — comparar parametros contra a media do orgao, da UF, e nacional

---

### 1.3 Base Curada de Doutrina Semantica

O sistema ja extrai chunks semanticos de doutrina com `tese_neutra`, `explicacao_conceitual`, `limites_e_cuidados`, `argument_role`, tudo sanitizado (sem revelar autor, sem citar tribunal, sem afirmar consenso).

**Por que e dificil de replicar:**
- Requer **livros especializados** como fonte (nao e dado publico scrapeable)
- A sanitizacao e um pipeline complexo e unico
- Os red flags + review humano criam qualidade crescente
- O schema de classificacao e proprietario

---

### 1.4 Mapa de Partes e Empresas em Decisoes

O `extract_partes()` ja extrai partes (CONTRATANTE, CONTRATADA, RESPONSAVEL, ADVOGADO) com classificacao (PUBLICA/PRIVADA/PF), CNPJ/CPF e cargo.

**Cruzamentos possiveis:**
- Empresa X foi sancionada em 3 acordaos do TCE-SP e 1 do TCU
- O prefeito Y foi responsavel em 5 processos irregulares
- A empresa Z ganhou 80% das licitacoes do orgao W (sinal de direcionamento?)

**Por que e dificil de replicar:**
- Exige parsing de alta qualidade dos cabecalhos de acordaos
- O cruzamento so funciona com volume (deduplica por CNPJ)
- Nenhum concorrente esta fazendo isso de forma automatizada

---

## 2. DADOS QUE AUMENTAM A CAPACIDADE DE ANALISE

### 2.1 Score de Risco do Edital

Combinar os 36+ parametros em um **score unico de risco**:

| Fator de risco | Fonte | Peso |
|---|---|---|
| Exige visita tecnica obrigatoria | `r_visita_tecnica` | +15 |
| Garantia de execucao > 5% | `r_garantia_execucao` | +10 |
| Prazo de entrega < 5 dias | `e001_entrega` | +20 |
| Nao permite consorcio | `r_consorcio` | +5 |
| Exige capital minimo | `r_capital_minimo` | +10 |
| Exige escritorio local | `r_escritorio_local` | +15 |
| Inversao de fases | `r_inversao_fases` | -5 (favorece) |
| Subcontratacao permitida | `r_subcontratacao` | -5 (favorece) |
| Jurisprudencia indica RIGORIZA | `kb_search` | +10 por param |

**Resultado:** "Este edital tem Risk Score 72/100 — alto risco para PMEs."

---

### 2.2 Checklist Automatico de Habilitacao

A partir dos parametros extraidos, gerar automaticamente o checklist de documentos:
- `r_atestado_tecnico` → "Precisa de atestado"
- `r_capital_minimo` → "Precisa comprovar capital de R$ X"
- `r_certificacao_ambiental` → "Precisa de ISO 14001"
- Cruzar com `kb_search` → "TCE-SP ja flexibilizou essa exigencia"

---

### 2.3 Deteccao de Clausulas Restritivas a Competitividade

O parser de acordaos ja tem `CLAIM_PATTERNS` que detectam restricao a competitividade, prazo exiguo, pesquisa de preco insuficiente, etc.

**Oportunidade:** Aplicar esses mesmos patterns **no texto do edital** para alertar: "Esta clausula pode ser impugnada — veja 3 acordaos que anularam clausulas similares."

---

### 2.4 Analise Comparativa (Benchmark)

Comparar os parametros de um edital contra:
1. Media do mesmo orgao (historico)
2. Media da mesma UF
3. Media nacional para o mesmo tipo de objeto

---

## 3. DADOS QUE AUMENTAM A PRODUTIVIDADE

### 3.1 Templates de Impugnacao Pre-Preenchidos

Quando detecta clausula restritiva, gerar rascunho de impugnacao citando:
- Dispositivo legal violado
- Jurisprudencia favoravel
- Doutrina de suporte

**Todos os dados ja existem** no sistema.

---

### 3.2 Match Automatico Edital → Empresa

Com base nos itens (CATMAT/CATSER), locais de entrega, e requisitos de habilitacao, fazer match com perfil de empresa pre-cadastrado.

**Resultado:** "3 novas licitacoes compativeis com sua empresa hoje."

---

### 3.3 API de Pre-Analise Instantanea

Pipeline que em 1 chamada recebe o PDF e retorna:
1. Todos os 36 parametros (regex, custo zero)
2. Risk Score
3. Checklist de habilitacao
4. Top 3 alertas jurisprudenciais
5. Itens com CATMAT/CATSER

**Dados ja existem** — falta apenas orquestrar em endpoint unico.

---

### 3.4 Monitoramento de Impacto Legislativo

Nova IN publicada → rodar chunker → cruzar com `legal_relation` → identificar quais acordaos na KB ficam desatualizados → alertar clientes.

---

## 4. CRUZAMENTOS POSSIVEIS HOJE (sem nova infraestrutura)

**Parametro do edital x Jurisprudencia:**
Para cada parametro extraido (ex: garantia 5%) → buscar na KB → "TCE-SP ja considerou 5% abusivo em 2 decisoes"

**Partes de acordaos x Partes de acordaos:**
Buscar CNPJ em todos os acordaos → "Empresa X foi sancionada 3x, absolvida 1x"

**Objeto do edital x Itens:**
Validar se itens sao coerentes com o objeto declarado

**Dispositivo legal citado x Vigencia:**
Acordao cita Lei 8.666 → `legal_relation` mostra que foi revogada pela 14.133 → alerta

---

## 5. MATRIZ DE PRIORIZACAO

| Iniciativa | Impacto | Moat | Prioridade |
|---|---|---|---|
| Score de Risco do Edital | Alto | Medio | **P0** |
| Checklist de Habilitacao | Alto | Medio | **P0** |
| API Pre-Analise Instantanea | Alto | Baixo | **P0** |
| Historico por Orgao | Alto | **Alto** | **P1** |
| Clausulas Restritivas no Edital | Alto | Alto | **P1** |
| Grafo Juris x Legislacao | Muito Alto | **Muito Alto** | **P1** |
| Match Edital → Empresa | Alto | Medio | **P2** |
| Mapa de Partes/Empresas | Alto | **Muito Alto** | **P2** |
| Templates de Impugnacao | Alto | Alto | **P2** |
| Benchmark Comparativo | Medio | Alto | **P2** |
| Linha do Tempo Juridica | Medio | Alto | **P3** |
| Monitoramento Impacto Legisl. | Medio | Alto | **P3** |
| Dicionario Contextualizado | Baixo | Baixo | **P3** |

---

**Resumo:** O Govy ja possui uma infraestrutura de dados excepcionalmente rica. As maiores oportunidades de **moat** estao em cruzar esses dados entre si e acumular historico. As maiores oportunidades de **produtividade imediata** (P0) usam dados que ja existem — falta apenas orquestrar.
