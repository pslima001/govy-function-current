# Govy - Extractors Regex-Only (31 parâmetros)

Módulo de extração de parâmetros de editais usando apenas regex (custo zero de LLM).

## Instalação

```bash
unzip govy_regex_extractors.zip -d govy/
mv govy/govy_regex_extractors govy/regex_extractors
```

## Uso

```python
from govy.regex_extractors import extract_all, extract_single, PARAMETROS_REGEX

# Extrair todos os parâmetros
resultados = extract_all(texto_edital)

for codigo, res in resultados.items():
    if res['encontrado']:
        print(f"{res['label']}: {res['valor']} ({res['confianca']})")

# Extrair um único parâmetro
resultado = extract_single('r_validade_proposta', texto_edital)
```

## Estrutura de Resposta

```python
{
    "encontrado": bool,      # Se encontrou o parâmetro
    "valor": str,            # Valor extraído (ex: "60 dias", "SIM", "ITEM")
    "confianca": str,        # "alta", "media", "baixa"
    "evidencia": str,        # Trecho do texto onde encontrou
    "detalhes": dict,        # Informações adicionais
    "label": str,            # Nome amigável
    "pergunta": str          # Pergunta associada
}
```

## Taxa de Extração

### Métricas Gerais (8 documentos testados)
- **Taxa geral**: 43% (106/248 extrações)
- **Taxa efetiva** (excluindo parâmetros inexistentes): 51%
- **Taxa em Pregões**: 60%
- **Taxa em Pregões** (apenas parâmetros existentes): 81%

### Em Pregões Eletrônicos (60% geral)

**100% de extração (15 parâmetros):**
- Inversão das Fases
- Validade da Proposta
- Prazo para Assinatura
- Tipo de Licitação (Item/Lote)
- Garantia de Execução
- Capital/Patrimônio Mínimo
- Reequilíbrio Econômico
- Vigência do Contrato
- Prorrogação
- Atestado Técnico
- Modalidade de Empreitada
- Subcontratação
- Consórcio
- Programa de Integridade
- Obrigações Acessórias

**67% de extração (3 parâmetros):**
- Visita Técnica
- Garantia do Objeto
- Sustentabilidade

**33% de extração (5 parâmetros):**
- Prazo para Esclarecimentos
- Antecipação de Pagamento
- Certificação Ambiental
- Preferência Local
- Matriz de Riscos

**0% - Não existem nos documentos testados (8 parâmetros):**
- Exigência de Amostra
- Prova de Conceito
- Garantia de Proposta
- Quantitativo Mínimo Atestado
- Margem Recicláveis
- Responsabilidade Social
- Margem Nacional
- Escritório Local

### Notas

- **Dispensas Eletrônicas**: ~29% (documentos simplificados)
- **Termo de Referência**: ~45%
- Parâmetros com 0% simplesmente não existem nos editais testados
- Se `confianca == "baixa"`, considere validação adicional com LLM

## Lista de Parâmetros

| Código | Label | Tipo |
|--------|-------|------|
| r_inversao_fases | Inversão das Fases | SIM/NÃO |
| r_validade_proposta | Validade da Proposta | X dias |
| r_prazo_esclarecimento | Prazo para Esclarecimentos | X dias úteis |
| r_prazo_assinatura | Prazo para Assinatura | X dias |
| r_visita_tecnica | Visita Técnica | OBRIGATÓRIA/FACULTATIVA/NÃO |
| r_amostra | Exigência de Amostra | SIM/NÃO/CONDICIONAL |
| r_prova_conceito | Prova de Conceito | SIM/NÃO |
| r_tipo_licitacao | Tipo de Licitação | ITEM/LOTE |
| r_garantia_proposta | Garantia de Proposta | SIM/NÃO (%) |
| r_garantia_execucao | Garantia de Execução | SIM/NÃO (%) |
| r_capital_minimo | Capital/Patrimônio Mínimo | SIM/NÃO (%) |
| r_antecipacao_pgto | Antecipação de Pagamento | SIM/NÃO |
| r_reequilibrio | Reequilíbrio Econômico | SIM/NÃO (índice) |
| r_vigencia_contrato | Vigência do Contrato | X meses/dias |
| r_prorrogacao | Prorrogação | SIM/NÃO |
| r_atestado_tecnico | Atestado Técnico | SIM/NÃO |
| r_quant_minimo_atestado | Quantitativo Mínimo Atestado | SIM/NÃO (%) |
| r_garantia_objeto | Garantia do Objeto | X meses |
| r_empreitada | Modalidade de Empreitada | PREÇO GLOBAL/UNITÁRIO/TAREFA |
| r_subcontratacao | Subcontratação | SIM/NÃO/PARCIAL |
| r_consorcio | Consórcio | SIM/NÃO |
| r_sustentabilidade | Sustentabilidade | SIM/NÃO |
| r_margem_reciclavel | Margem Recicláveis | SIM/NÃO |
| r_certificacao_ambiental | Certificação Ambiental | SIM/NÃO |
| r_programa_integridade | Programa de Integridade | SIM/NÃO |
| r_responsabilidade_social | Responsabilidade Social | SIM/NÃO |
| r_preferencia_local | Preferência Local | SIM/NÃO |
| r_margem_nacional | Margem Nacional | SIM/NÃO (%) |
| r_escritorio_local | Escritório Local | SIM/NÃO |
| r_matriz_riscos | Matriz de Riscos | SIM/NÃO |
| r_obrigacoes_acessorias | Obrigações Acessórias | Lista |

## Funcionalidades

- `fix_encoding()`: Corrige problemas de encoding UTF-8/Latin-1
- `extract_all()`: Extrai todos os 31 parâmetros
- `extract_single()`: Extrai um parâmetro específico
- Níveis de confiança para decisão de validação LLM
