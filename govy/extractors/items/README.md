# 📦 GOVY Items Extractor

Módulo de extração de itens/produtos/serviços de editais de licitação.

**Versão:** 1.0.0 | **Atualização:** 22/01/2026

---

## 🎯 Objetivo

Extrair os produtos e serviços (itens) que serão contratados pelo governo em editais de licitação, de forma eficiente e com baixo custo, identificando apenas as páginas/tabelas relevantes antes do processamento completo.

---

## 🏗️ Arquitetura

```
PDF Bruto
    ↓
[1. PAGE SCANNER] ← Scan leve (custo ~ZERO)
    - Identifica páginas candidatas
    - Detecta seções de Termo de Referência
    - Conta indicadores-chave
    ↓
[2. TABLE SCORER] ← Scoring de tabelas
    - Classifica tabelas por probabilidade
    - Aplica regras de FORTE CANDIDATO
    ↓
[3. ITEM EXTRACTOR] ← Extração dos itens
    - Mapeia colunas automaticamente
    - Extrai todos os itens (1 a 400+)
    - Detecta descrições mesmo em colunas ambíguas
```

---

## ✅ Regras de FORTE CANDIDATO

| Regra | Descrição | Score |
|-------|-----------|-------|
| **Regra 1** | "Valor Unitário" + "Valor Total" juntos | 1.0 |
| **Regra 2** | É TABELA + ≥3 indicadores | 0.9 |
| **Regra 3** | Dentro de TR + É TABELA + ≥2 indicadores | 0.85 |
| **Regra 4** | ≥4 indicadores mesmo sem estrutura clara | 0.8 |

---

## 🔑 Indicadores Reconhecidos

### Estrutura
- Lote, Item, Descrição, Especificação

### Quantificação
- Qtde, Quantidade, Un., Unidade, Quant.

### Valores
- Valor Unitário, Valor Total, P.Unit, P.Total, Valor Estimado

### Códigos (específicos governo)
- CATMAT, CATSER, Código SIMPAS, Código GMS

---

## 📂 Estrutura do Módulo

```
govy_items_extractor/
├── __init__.py          # Exportações do módulo
├── constants.py         # Indicadores e configurações
├── page_scanner.py      # Scan leve de páginas (pré-filtro)
├── table_scorer.py      # Scoring de tabelas
├── item_extractor.py    # Extração dos itens
├── main.py              # Integração e CLI
└── README.md            # Esta documentação
```

---

## 🚀 Uso

### Linha de Comando

```bash
# Processar documento JSON (já parseado pelo Azure DI)
python main.py documento_parsed.json

# Modo silencioso
python main.py documento_parsed.json --quiet
```

### Como Módulo Python

```python
from govy_items_extractor import processar_documento, processar_arquivo

# Processar arquivo JSON
resultado = processar_arquivo("edital_parsed.json", verbose=True)

# Ou processar dados diretamente
import json
with open("edital_parsed.json") as f:
    json_data = json.load(f)

resultado = processar_documento(json_data, verbose=False)

# Acessar itens extraídos
print(f"Total: {resultado.total_itens}")
for item in resultado.itens:
    print(f"- {item.numero}: {item.descricao}")
```

---

## 📊 Estrutura de Saída

### ResultadoExtracao

```python
@dataclass
class ResultadoExtracao:
    itens: List[ItemLicitacao]       # Lista de itens extraídos
    total_itens: int                  # Total de itens
    paginas_processadas: List[int]    # Páginas onde encontrou itens
    tabelas_processadas: int          # Número de tabelas processadas
    erros: List[str]                  # Erros ocorridos
```

### ItemLicitacao

```python
@dataclass
class ItemLicitacao:
    numero: Optional[str]             # Número do item/lote
    descricao: str                    # Descrição do produto/serviço
    quantidade: Optional[str]         # Quantidade
    unidade: Optional[str]            # Unidade de medida
    valor_unitario: Optional[str]     # Valor unitário
    valor_total: Optional[str]        # Valor total
    codigo_catmat: Optional[str]      # Código CATMAT
    codigo_catser: Optional[str]      # Código CATSER
    lote: Optional[str]               # Número do lote
    outros: Dict[str, str]            # Campos adicionais não mapeados
    
    # Metadados
    page_number: int                  # Página onde foi extraído
    table_index: int                  # Índice da tabela
    row_index: int                    # Linha na tabela
    confianca: float                  # Score de confiança (0-1)
```

---

## 💡 Heurísticas Inteligentes

### Detecção de Descrição Ambígua

O módulo detecta quando uma coluna chamada "UNIDADE" contém na verdade descrições, não unidades de medida.

**Exemplo problemático:**
| ITEM | UNIDADE | QTD |
|------|---------|-----|
| 01 | Unidade Móvel de Saúde | 1 |
| 02 | Unidade Móvel Odontológica | 1 |

O módulo verifica se o conteúdo é texto longo (>10 chars) e não é uma unidade válida (UN, KG, etc.), reclassificando automaticamente como descrição.

### Fallback por Conteúdo

Se nenhuma coluna de descrição for identificada pelo header, o módulo encontra a coluna com o texto mais longo que não seja numérico.

---

## 📈 Métricas de Performance

| Documento | Páginas | Tabelas | Itens Extraídos |
|-----------|---------|---------|-----------------|
| Pregão Eletrônico (68 pág) | 68 | 7 | 119 |
| Dispensa Eletrônica (63 pág) | 63 | 8 | 13 |
| Contratação Direta (14 pág) | 14 | 2 | 1 |

---

## 🔧 Dependências

- Python 3.11+
- Nenhuma dependência externa (usa apenas stdlib)

---

## 📝 Próximos Passos

1. **Integração com Azure Functions** - Endpoint `/extract_items`
2. **Parse seletivo de páginas** - Processar apenas páginas candidatas
3. **Normalização de itens** - Via LLM para categorização
4. **Cache de resultados** - Evitar reprocessamento

---

## 📞 Contato

**Projeto:** GOVY  
**Módulo:** Items Extractor  
**Responsável:** Paulo Souza
