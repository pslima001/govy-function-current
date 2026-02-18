# Governança de Classes e Regras

Regras para manutenção do `core.json` e dos overlays por tribunal.

---

## Princípios

1. **Core é universal.** Só entra no core o que vale para todos os 27 TCEs.
2. **Overlay é local.** Variações específicas de um tribunal ficam no overlay.
3. **Overlay não pode contradizer o core.** Pode estender, nunca degradar.
4. **Toda mudança no core requer bump de version.**

---

## O que o Core define

| Elemento | Descrição |
|----------|-----------|
| Classes (CLASSES) | As 14 classes universais de documentos de licitação/contratos |
| Procedures (PROCEDURES) | Flags de procedimento (ex: exame_previo_edital) |
| TIE_BREAKERS | Regras de desempate universais |
| EQUIVALENCES | Regras de equivalência baseline vs rules |
| DESCARTE | Regras de descarte (documentos irrelevantes) |
| Globals | Thresholds de confiança, flags de normalização, configuração de quotes |

---

## O que o Overlay pode fazer

### Permitido

| Ação | Exemplo |
|------|---------|
| **Adicionar patterns** a uma classe existente | TCE-SP adiciona `\\bREPRESENTANTE(S)?:\\b` à classe `representacao` |
| **Substituir patterns** com `_replace` | Overlay substitui toda a lista `strong` de uma classe |
| **Adicionar TIE_BREAKERS locais** | TCE-SP adiciona `tce_sp_epe_does_not_override_representacao` |
| **Adicionar EQUIVALENCES locais** | TCE-SP adiciona equivalência EPE+Repr |
| **Sobrescrever chaves de globals** | Overlay muda `text_head_chars` de 5000 para 6000 |
| **Adicionar patterns a PROCEDURES** | Overlay reforça patterns do `exame_previo_edital` |

### Proibido

| Ação | Motivo |
|------|--------|
| **Criar classes novas** | Classes são universais; se um tribunal precisa de uma classe nova, ela deve ser avaliada para inclusão no core |
| **Remover classes do core** | Use `enabled: false` no overlay se necessário, mas não delete |
| **Alterar `id` de classes** | IDs são chave de referência em tie-breakers, equivalences, e no output |
| **Alterar `priority` base de classes** | Priority é universal; use tie-breakers para ajustes locais |
| **Alterar `confidence_rules` de classes** | Regras de confiança são calibradas globalmente |
| **Alterar `whitelist` de classes** | Whitelist/blacklist é decisão do core |
| **Criar PROCEDURES novos** | Procedures são universais; avalie inclusão no core |
| **Modificar DESCARTE do core** | Regras de descarte são universais |

### Zona cinza (requer justificativa)

| Ação | Quando permitir |
|------|-----------------|
| Sobrescrever `sources_priority` de uma classe | Quando o tribunal tem estrutura de documento diferente |
| Desabilitar uma classe (`enabled: false`) | Quando a classe não se aplica ao tribunal |
| Adicionar DESCARTE local | Quando o tribunal tem documentos irrelevantes específicos |

---

## Processo de mudança no Core

### Adição de classe

1. Identificar que a classe aparece em pelo menos 3 TCEs diferentes
2. Definir patterns iniciais (strong, weak, negative)
3. Calibrar `confidence_rules` contra golden set
4. Adicionar TIE_BREAKERS se necessário para desambiguação
5. Bump `version` do core
6. Rodar testes de regressão contra todos os overlays

### Modificação de patterns

1. Verificar impacto em todos os overlays existentes
2. Rodar golden set antes e depois (se disponível)
3. Se pattern era usado por overlay como base para append, verificar que dedupe funciona
4. Bump `version` do core

### Adição de TIE_BREAKER

1. Verificar que não conflita com tie-breakers existentes (priority única)
2. Verificar que classes/procedures referenciados existem
3. Testar com documentos representativos
4. Bump `version` do core

---

## Versionamento

- Core: `version` no `core.json` (semver: MAJOR.MINOR.PATCH)
  - MAJOR: mudança quebrante (remoção de classe, mudança de schema)
  - MINOR: nova classe, novo tie-breaker, nova equivalência
  - PATCH: ajuste de patterns, calibração de thresholds
- Overlay: `version` no overlay JSON (independente do core)
- Hash: `ruleset_hash` no output identifica unicamente a combinação core+overlay compilada

---

## Inventário de Classes (v1.0.0)

| ID | Label | Priority | Whitelist | Descrição |
|----|-------|----------|-----------|-----------|
| cautelar | Cautelar / Liminar | 90 | sim | Ação urgente para suspender ato |
| representacao | Representação / Denúncia | 80 | sim | Denúncia formal sobre irregularidades |
| pedido_reconsideracao | Pedido de Reconsideração | 78 | sim | Pedido de revisão de decisão |
| embargos_declaracao | Embargos de Declaração | 75 | sim | Recurso para esclarecer decisão |
| sancoes | Sanções | 72 | sim | Inidoneidade, suspensão, multa |
| recurso_ordinario | Recurso Ordinário | 70 | sim | Recurso padrão contra decisão |
| agravo | Agravo | 68 | sim | Recurso contra decisão interlocutória |
| termo_rescisao | Termo de Rescisão | 65 | sim | Rescisão contratual |
| contrato_gestao | Contrato de Gestão / OS | 60 | sim | Contratos com organizações sociais |
| convenios_parcerias | Convênios / Parcerias | 55 | sim | Convênios e termos de colaboração |
| relatorio_fiscalizacao | Relatório / Auditoria / Inspeção | 50 | sim | Relatórios de fiscalização |
| acompanhamento | Acompanhamento | 40 | sim | Fiscalização concomitante |
| contratos | Contratos (execução / genérico) | 20 | sim | Contratos, aditivos, reajustes |
| prestacao_contas | Prestação de Contas | 10 | **não** | Contas anuais (irrelevante para licitantes) |

---

## Inventário de Procedures (v1.0.0)

| ID | Label | Descrição |
|----|-------|-----------|
| exame_previo_edital | Exame Prévio de Edital | Análise preventiva de edital (coexiste com classe) |
