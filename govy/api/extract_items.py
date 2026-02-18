# govy/api/extract_items.py
"""
Extracao de itens de editais - v27: FALLBACK CABECALHO ESTRUTURADO + TABELAS CONTINUACAO
Estrategia:
1. PyMuPDF    -> tabelas estruturadas
2. pdfplumber -> tabelas estruturadas  
3. TEXTO      -> regex em texto corrido
Consenso: item valido se 2+ camadas concordam
Custo: $0 (100% Python)

v27 MUDANCAS:
- RECUPERA logica da v15: fallback para cabecalho estruturado
- Detecta tabelas por cabecalho (DESCRICAO + UNIDADE obrigatorios)
- Detecta tabelas de CONTINUACAO (sem cabecalho mas mesma estrutura)
- Fallback ativado quando metodo principal retorna poucos itens ou titulos de secao
- REGRA CRITICA: novas regras NUNCA devem eliminar regras que funcionavam

HIERARQUIA DE EXTRACAO:
1. Primeiro: numeros sequenciais (1, 2, 3...) - metodo original
2. Fallback: cabecalho estruturado (DESCRICAO + UNIDADE) - se 1 falhou
   - Inclui tabelas com cabecalho
   - Inclui tabelas de continuacao (sem cabecalho)

v14 FIXES (mantidos):
- Corrigido bug de celulas quebradas onde primeira letra ficava separada
- Limite de itens aumentado para 800
"""
import os
import re
import json
import logging
import tempfile
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict, Counter
import azure.functions as func
from govy.utils.azure_clients import get_blob_service_client

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTES
# =============================================================================

# v12: Aumentado para 800 itens
MAX_ITEM_NUMBER = 800

SECOES_PROPOSTA = [
    "modelo de proposta comercial",
    "modelo de proposta de precos",
    "formulario de proposta",
    "minuta de contrato",
    "minuta do contrato",
]

PADROES_NUMERO = ["item", "#", "seq", "num"]
PADROES_DESCRICAO = ["descri", "especifica", "produto", "material", "servico", "objeto", "denomina", "medicamento", "nome"]
PADROES_UNIDADE = ["unid", "un.", "uf", "u.f", "u.m"]
PADROES_QUANTIDADE = ["qtd", "quant", "qde", "qtde"]
PADROES_VALOR = ["valor", "preco", "unit", "total", "vlr", "p."]
PADROES_CATMAT = ["catmat", "catser", "codigo"]

# v12: Unidades para ignorar na reconstrucao
UNIDADES_IGNORAR = {'FRS', 'CP', 'AMP', 'TB', 'UN', 'CX', 'CAPS', 'ML', 'MG', 'SCH', 'FLAC.', 'FR/AM', 'FR', 'UNID'}

# =============================================================================
# v27: CONSTANTES PARA CABECALHO ESTRUTURADO
# =============================================================================

# Cabecalho DESCRICAO (obrigatorio)
# Nota: sem acentos para evitar problemas de encoding Windows
CABECALHO_DESCRICAO = [
    "descricao", "especificacao", "procedimento", "servico", "produto", 
    "objeto", "denominacao", "nome", "item"
]

# Cabecalho UNIDADE (opcional)  
CABECALHO_UNIDADE = [
    "unidade", "unid", "un", "und", "u.m", "medida",
    # Valores tipicos de unidade
    "frasco", "cp", "comprimido", "tubo", "tb", "metro", "quilo", "kg",
    "caixa", "cx", "peca", "pc", "bisnaga", "capsula",
    "seringa", "envelope", "ampola", "creme", "dragea",
    "litro", "lt", "ml", "mililitro", "kit", "duzia", "dz",
    "milheiro", "bobina", "blister", "rolo", "cartela", "tambor",
    "galao", "saco", "lata", "barril", "grama", "g",
    "mm", "milimetro", "cm", "centimetro",
    "watt", "w", "kw", "kwh", "frasco-ampola", "diaria", "hora", "hr", "h"
]

# Cabecalho IDENTIFICACAO (opcional)
CABECALHO_IDENTIFICACAO = [
    "codigo", "cod", "item", "ref", "referencia",
    "catser", "catmat", "sigtap"
]

# Cabecalho QUANTIDADE (opcional)
CABECALHO_QUANTIDADE = [
    "quantidade", "quant", "qtde", "qtd", "qt", "qde"
]

# Cabecalho VALOR (opcional)
CABECALHO_VALOR = [
    "valor", "preco", "unit", "unitario",
    "total", "custo", "vlr"
]


# =============================================================================
# DETECCAO DE SECAO (TR vs PROPOSTA)
# =============================================================================

def detectar_pagina_limite_proposta(texto_por_pagina: Dict[int, str]) -> int:
    for page_num in sorted(texto_por_pagina.keys()):
        texto = texto_por_pagina[page_num].lower()
        for marcador in SECOES_PROPOSTA:
            if marcador in texto:
                logger.info(f"v12: Secao Proposta detectada pagina {page_num}")
                return page_num
    return 9999


# =============================================================================
# v12: RECONSTRUCAO DE DESCRICAO (FIX CELULAS QUEBRADAS)
# =============================================================================

def reconstruir_descricao_v12(row: List, col_numero: int, mapa: Dict[str, int] = None) -> Optional[str]:
    """
    v12 FIX: Reconstruir descricao quando esta quebrada em multiplas celulas.
    
    Problema detectado em PDFs com cota principal/reservada:
    - Col 7: 'A\n('
    - Col 8: 'CEBROFILINA XAROPE AD. 100ML'
    - Resultado errado: 'CEBROFILINA' (sem o A)
    
    Solucao: Detectar padrao de letra isolada e juntar corretamente.
    """
    
    partes_descricao = []
    letra_isolada = None
    
    for idx, cell in enumerate(row):
        if idx == col_numero:
            continue
        
        texto = str(cell or "").strip()
        
        if not texto:
            continue
        
        # Ignorar valores numericos puros (quantidades, valores)
        if re.match(r'^[\d,.\s]+$', texto):
            continue
        
        # Ignorar unidades isoladas
        if texto.upper() in UNIDADES_IGNORAR:
            continue
        
        # v12 FIX: Detectar letra isolada com quebra de linha
        # Padrao: 'A\n(' ou 'M\n(' etc
        match_letra = re.match(r'^([A-Z])\s*[\n(]', texto)
        if match_letra:
            letra_isolada = match_letra.group(1)
            continue
        
        # Se tem letra isolada pendente, prefixar
        if letra_isolada:
            texto = letra_isolada + texto
            letra_isolada = None
        
        partes_descricao.append(texto)
    
    if not partes_descricao:
        return None
    
    # Juntar partes
    descricao = " ".join(partes_descricao)
    
    # Limpar quebras de linha e espacos multiplos
    descricao = re.sub(r'\n', ' ', descricao)
    descricao = re.sub(r'\s+', ' ', descricao).strip()
    
    # Remover parenteses vazios ou incompletos no inicio
    descricao = re.sub(r'^\s*\(\s*', '', descricao)
    
    # v12: Limpar sufixo de participacao grudado
    # "100MLAMPLA PARTICIPACAO" -> "100ML (AMPLA PARTICIPACAO"
    descricao = re.sub(r'(\d+(?:MG|ML|MG/ML|UI|MCG))(AMPLA|COTA)', r'\1 (\2', descricao)
    
    return descricao if len(descricao) >= 8 else None


# =============================================================================
# EXTRACAO DE TABELAS - PYMUPDF
# =============================================================================

def extrair_tabelas_pymupdf(pdf_path: str) -> Tuple[List[Dict], Dict[int, str]]:
    try:
        import fitz
        doc = fitz.open(pdf_path)
        tabelas = []
        texto_por_pagina = {}
        
        for page_num, page in enumerate(doc, 1):
            texto_por_pagina[page_num] = page.get_text("text")
            try:
                for table in page.find_tables():
                    dados = table.extract()
                    if dados and len(dados) >= 2:
                        tabelas.append({
                            "page_number": page_num,
                            "rows": dados,
                            "fonte": "pymupdf"
                        })
            except Exception as e:
                logger.warning(f"PyMuPDF erro pagina {page_num}: {e}")
        
        doc.close()
        logger.info(f"PyMuPDF: {len(tabelas)} tabelas")
        return tabelas, texto_por_pagina
    except ImportError:
        logger.warning("PyMuPDF nao disponivel")
        return [], {}
    except Exception as e:
        logger.error(f"PyMuPDF erro: {e}")
        return [], {}


# =============================================================================
# EXTRACAO DE TABELAS - PDFPLUMBER
# =============================================================================

def extrair_tabelas_pdfplumber(pdf_path: str) -> Tuple[List[Dict], Dict[int, str]]:
    try:
        import pdfplumber
        tabelas = []
        texto_por_pagina = {}
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                texto_por_pagina[page_num] = page.extract_text() or ""
                try:
                    for table in page.extract_tables():
                        if table and len(table) >= 2:
                            tabelas.append({
                                "page_number": page_num,
                                "rows": table,
                                "fonte": "pdfplumber"
                            })
                except Exception as e:
                    logger.warning(f"pdfplumber erro pagina {page_num}: {e}")
        
        logger.info(f"pdfplumber: {len(tabelas)} tabelas")
        return tabelas, texto_por_pagina
    except ImportError:
        logger.warning("pdfplumber nao disponivel")
        return [], {}
    except Exception as e:
        logger.error(f"pdfplumber erro: {e}")
        return [], {}


# =============================================================================
# v11: EXTRACAO POR TEXTO/REGEX (3a CAMADA)
# =============================================================================

def extrair_itens_por_texto(texto_por_pagina: Dict[int, str], pagina_limite: int) -> List[Dict]:
    """
    Extrai itens do texto corrido usando regex.
    """
    
    itens = []
    
    # Padroes de regex para encontrar itens no texto
    padroes = [
        re.compile(r'^\s*(\d{1,3})\s*[.\-)]\s*([A-Z][A-Z\s\d,./\-()%+]+)', re.MULTILINE),
        re.compile(r'[Ii]tem\s*(\d{1,3})\s*[:\-]\s*([A-Z][A-Za-z\s\d,./\-()%+]+)', re.MULTILINE),
        re.compile(r'^(\d{1,3})\s+([A-Z]{3,}[A-Z\s\d,./\-()%+]{10,})', re.MULTILINE),
    ]
    
    texto_completo = ""
    for page_num in sorted(texto_por_pagina.keys()):
        if page_num < pagina_limite:
            texto_completo += texto_por_pagina[page_num] + "\n"
    
    itens_encontrados = {}
    
    for padrao in padroes:
        matches = padrao.findall(texto_completo)
        for match in matches:
            num_str, descricao = match
            num = int(num_str)
            
            if 1 <= num <= MAX_ITEM_NUMBER:
                descricao = descricao.strip()
                descricao = re.sub(r'\s+', ' ', descricao)
                descricao = re.sub(r'\s+\d+[.,]\d{2}\s*$', '', descricao)
                descricao = re.sub(r'\s+\d{3,}\s*$', '', descricao)
                
                if len(descricao) >= 10:
                    if num not in itens_encontrados or len(descricao) > len(itens_encontrados[num]):
                        itens_encontrados[num] = descricao
    
    numeros = set(itens_encontrados.keys())
    if 1 not in numeros or 2 not in numeros:
        logger.info("v12 TEXTO: sequencia nao comeca em 1,2")
        return []
    
    sequencia_valida = set()
    for n in range(1, max(numeros) + 1):
        if n in numeros:
            sequencia_valida.add(n)
        else:
            if (n + 1) in numeros or (n + 2) in numeros:
                continue
            else:
                break
    
    for num in sorted(sequencia_valida):
        if num in itens_encontrados:
            itens.append({
                "numero_item": str(num),
                "descricao": itens_encontrados[num],
                "quantidade": None,
                "unidade": None,
                "valor_unitario": None,
                "valor_total": None,
                "codigo_catmat": None,
                "_fonte": "texto",
            })
    
    logger.info(f"v12 TEXTO: {len(itens)} itens extraidos")
    return itens


# =============================================================================
# MAPEAMENTO DE COLUNAS POR HEADER
# =============================================================================

def mapear_colunas_por_header(header_row: List) -> Dict[str, int]:
    mapa = {}
    
    for idx, cell in enumerate(header_row):
        texto = str(cell or "").lower().strip()
        
        if any(p in texto for p in PADROES_NUMERO) and "numero" not in mapa:
            mapa["numero"] = idx
        elif any(p in texto for p in PADROES_DESCRICAO) and "descricao" not in mapa:
            mapa["descricao"] = idx
        elif any(p in texto for p in PADROES_UNIDADE) and "unidade" not in mapa:
            mapa["unidade"] = idx
        elif any(p in texto for p in PADROES_QUANTIDADE) and "quantidade" not in mapa:
            mapa["quantidade"] = idx
        elif any(p in texto for p in PADROES_CATMAT) and "catmat" not in mapa:
            mapa["catmat"] = idx
        elif any(p in texto for p in PADROES_VALOR):
            if "valor_unit" not in mapa and "unit" in texto:
                mapa["valor_unit"] = idx
            elif "valor_total" not in mapa and "total" in texto:
                mapa["valor_total"] = idx
    
    return mapa


def encontrar_header(tabela: Dict) -> Tuple[int, Dict[str, int]]:
    rows = tabela.get("rows", [])
    
    for row_idx, row in enumerate(rows[:5]):
        texto_row = " ".join(str(c or "").lower() for c in row)
        
        tem_item = any(p in texto_row for p in PADROES_NUMERO)
        tem_desc = any(p in texto_row for p in PADROES_DESCRICAO)
        tem_valor = any(p in texto_row for p in PADROES_VALOR)
        
        if (tem_item and tem_desc) or (tem_item and tem_valor) or (tem_desc and tem_valor):
            mapa = mapear_colunas_por_header(row)
            if mapa:
                return row_idx, mapa
    
    return -1, {}


# =============================================================================
# EXTRACAO DE ITENS POR TABELA - v12
# =============================================================================

def buscar_campo(row: List, mapa: Dict[str, int], campo: str) -> Optional[str]:
    col = mapa.get(campo)
    if col is not None and col < len(row):
        valor = str(row[col] or "").strip()
        if valor:
            return valor
    return None


def extrair_itens_de_tabelas(tabelas: List[Dict], pagina_limite: int, fonte: str) -> List[Dict]:
    """v12: Extrai itens de tabelas com fix para celulas quebradas."""
    
    todas_ancoras = []
    
    for tabela in tabelas:
        page_num = tabela.get("page_number", 0)
        if page_num >= pagina_limite:
            continue
        
        rows = tabela.get("rows", [])
        header_idx, mapa = encontrar_header(tabela)
        
        for row_idx, row in enumerate(rows):
            if row_idx <= header_idx:
                continue
            
            for col_idx, cell in enumerate(row):
                valor = str(cell or "").strip()
                match = re.match(r'^(\d{1,3})$', valor)
                if match:
                    num = int(match.group(1))
                    if 1 <= num <= MAX_ITEM_NUMBER:
                        todas_ancoras.append({
                            "numero": num,
                            "page": page_num,
                            "row_idx": row_idx,
                            "col_idx": col_idx,
                            "row_data": row,
                            "tabela_rows": rows,
                            "mapa": mapa,
                        })
    
    # Filtrar por sequencia continua
    numeros = set(a["numero"] for a in todas_ancoras)
    if 1 not in numeros or 2 not in numeros:
        return []
    
    sequencia_valida = set()
    for n in range(1, max(numeros) + 1):
        if n in numeros:
            sequencia_valida.add(n)
        else:
            if (n + 1) in numeros or (n + 2) in numeros:
                continue
            else:
                break
    
    # Agrupar por numero
    ancoras_por_numero = defaultdict(list)
    for a in todas_ancoras:
        if a["numero"] in sequencia_valida:
            ancoras_por_numero[a["numero"]].append(a)
    
    # Extrair itens
    itens = []
    for num in sorted(sequencia_valida):
        if num not in ancoras_por_numero:
            continue
        
        candidatos = ancoras_por_numero[num]
        ancora = max(candidatos, key=lambda x: sum(1 for c in x["row_data"] if c))
        
        # v12: Usar nova funcao de reconstrucao
        descricao = reconstruir_descricao_v12(
            ancora["row_data"],
            ancora["col_idx"],
            ancora["mapa"]
        )
        
        if descricao and len(descricao) >= 8:
            item = {
                "numero_item": str(num),
                "descricao": descricao,
                "quantidade": buscar_campo(ancora["row_data"], ancora["mapa"], "quantidade"),
                "unidade": buscar_campo(ancora["row_data"], ancora["mapa"], "unidade"),
                "valor_unitario": buscar_campo(ancora["row_data"], ancora["mapa"], "valor_unit"),
                "valor_total": buscar_campo(ancora["row_data"], ancora["mapa"], "valor_total"),
                "codigo_catmat": buscar_campo(ancora["row_data"], ancora["mapa"], "catmat"),
                "_fonte": fonte,
                "_page": ancora["page"],
            }
            itens.append(item)
    
    return itens


# =============================================================================
# v11: CONSENSO REAL COM 3 CAMADAS
# =============================================================================

def consenso_real(itens_por_fonte: Dict[str, List[Dict]], min_votos: int = 2) -> Tuple[List[Dict], Dict]:
    """
    CONSENSO REAL: item valido se aparece em min_votos fontes.
    VOTACAO: descricao escolhida por maioria ou mais completa.
    """
    
    itens_por_numero = defaultdict(list)
    
    for fonte, itens in itens_por_fonte.items():
        for item in itens:
            num = item.get("numero_item")
            if num:
                itens_por_numero[num].append({
                    "fonte": fonte,
                    "item": item
                })
    
    itens_finais = []
    estatisticas = {"aceitos": 0, "rejeitados": 0, "por_votos": {1: 0, 2: 0, 3: 0}}
    
    for num in sorted(itens_por_numero.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        candidatos = itens_por_numero[num]
        fontes_unicas = list(set(c["fonte"] for c in candidatos))
        n_fontes = len(fontes_unicas)
        
        estatisticas["por_votos"][min(n_fontes, 3)] = estatisticas["por_votos"].get(min(n_fontes, 3), 0) + 1
        
        if n_fontes >= min_votos:
            estatisticas["aceitos"] += 1
            
            descricoes = [c["item"]["descricao"] for c in candidatos if c["item"].get("descricao")]
            
            if descricoes:
                contagem = Counter(descricoes)
                mais_comum, votos = contagem.most_common(1)[0]
                
                if votos >= 2:
                    descricao_final = mais_comum
                else:
                    descricao_final = max(descricoes, key=len)
            else:
                continue
            
            item_final = {
                "numero_item": num,
                "lote": None,
                "descricao": descricao_final,
                "quantidade": None,
                "unidade": None,
                "valor_unitario": None,
                "valor_total": None,
                "codigo_catmat": None,
                "codigo_catser": None,
                "_meta": {
                    "fontes": fontes_unicas,
                    "n_fontes": n_fontes,
                    "consenso": True
                }
            }
            
            for c in candidatos:
                it = c["item"]
                for campo in ["quantidade", "unidade", "valor_unitario", "valor_total", "codigo_catmat"]:
                    if not item_final.get(campo) and it.get(campo):
                        item_final[campo] = it[campo]
            
            itens_finais.append(item_final)
        else:
            estatisticas["rejeitados"] += 1
    
    logger.info(f"v14 CONSENSO: aceitos={estatisticas['aceitos']}, rejeitados={estatisticas['rejeitados']}")
    logger.info(f"v14 VOTOS: {estatisticas['por_votos']}")
    
    # v14 FIX: Ordenar por numero_item antes de retornar
    itens_finais = sorted(itens_finais, key=lambda x: int(x.get('numero_item', 0)))
    
    return itens_finais, estatisticas




# =============================================================================
# v14: VALIDACAO POS-CONSENSO
# =============================================================================

def detectar_anomalias(itens: List[Dict]) -> Dict:
    """
    Detecta anomalias que indicam erro de mapeamento de colunas.
    
    Anomalias detectadas:
    1. Mesmo numero_item com descricoes muito diferentes (duplicata)
    2. Descricao aparece em multiplos numeros (erro de atribuicao)
    3. Saltos grandes para tras na sequencia (ex: 520, 521, 1, 522)
    """
    anomalias = {
        "duplicatas_numero": [],
        "descricoes_repetidas": [],
        "saltos_sequencia": [],
        "numeros_suspeitos": []
    }
    
    # 1. Detectar duplicatas de numero_item
    numeros_vistos = {}
    for item in itens:
        num = item.get("numero_item", "")
        desc = item.get("descricao", "")[:50]
        if num in numeros_vistos:
            anomalias["duplicatas_numero"].append({
                "numero": num,
                "desc1": numeros_vistos[num],
                "desc2": desc
            })
        else:
            numeros_vistos[num] = desc
    
    # 2. Detectar descricoes que aparecem com numeros muito diferentes
    desc_para_numeros = {}
    for item in itens:
        num = int(item.get("numero_item", 0)) if item.get("numero_item", "").isdigit() else 0
        # Normalizar descricao (primeiras 30 chars, uppercase, sem espacos extras)
        desc_norm = " ".join(item.get("descricao", "")[:30].upper().split())
        if desc_norm:
            if desc_norm not in desc_para_numeros:
                desc_para_numeros[desc_norm] = []
            desc_para_numeros[desc_norm].append(num)
    
    for desc, nums in desc_para_numeros.items():
        if len(nums) > 1:
            # Verificar se os numeros sao muito distantes
            nums_sorted = sorted(nums)
            max_gap = max(nums_sorted[i+1] - nums_sorted[i] for i in range(len(nums_sorted)-1))
            if max_gap > 100:  # Gap maior que 100 indica erro
                anomalias["descricoes_repetidas"].append({
                    "descricao": desc,
                    "numeros": nums,
                    "max_gap": max_gap
                })
    
    # 3. Detectar saltos para tras na sequencia original
    numeros_em_ordem = [int(i.get("numero_item", 0)) for i in itens if i.get("numero_item", "").isdigit()]
    for i in range(1, len(numeros_em_ordem)):
        atual = numeros_em_ordem[i]
        anterior = numeros_em_ordem[i-1]
        # Se o numero atual e muito menor que o anterior (salto para tras)
        if atual < anterior - 50:
            anomalias["saltos_sequencia"].append({
                "posicao": i,
                "de": anterior,
                "para": atual
            })
    
    # 4. Detectar numeros suspeitos (muito pequenos que aparecem no meio/fim)
    if numeros_em_ordem:
        mediana = sorted(numeros_em_ordem)[len(numeros_em_ordem)//2]
        for i, num in enumerate(numeros_em_ordem):
            # Numero muito pequeno (< 10) aparecendo depois de numeros grandes (> 100)
            if num < 10 and i > 0:
                max_anterior = max(numeros_em_ordem[:i])
                if max_anterior > 100:
                    anomalias["numeros_suspeitos"].append({
                        "numero": num,
                        "posicao_lista": i,
                        "max_anterior": max_anterior
                    })
    
    # Remover listas vazias
    return {k: v for k, v in anomalias.items() if v}


def corrigir_anomalias(itens: List[Dict], anomalias: Dict) -> Tuple[List[Dict], Dict]:
    """
    Tenta corrigir anomalias detectadas.
    
    Estrategia conservadora:
    - So corrige se tiver alta confianca
    - Remove itens claramente errados ao inves de tentar reatribuir
    - Loga tudo para aprendizado
    """
    itens_corrigidos = itens.copy()
    correcoes = {
        "itens_removidos": [],
        "itens_mantidos_com_aviso": []
    }
    
    # Corrigir numeros suspeitos: remover itens com numero muito baixo 
    # que aparecem no meio de numeros altos
    if "numeros_suspeitos" in anomalias:
        numeros_para_remover = set()
        for susp in anomalias["numeros_suspeitos"]:
            num = str(susp["numero"])
            # So remove se o numero for < 10 e aparece depois de > 500
            if susp["numero"] < 10 and susp["max_anterior"] > 500:
                numeros_para_remover.add(num)
                correcoes["itens_removidos"].append({
                    "numero": num,
                    "motivo": f"Numero {num} aparece apos itens > {susp['max_anterior']}, provavelmente erro de mapeamento"
                })
        
        if numeros_para_remover:
            itens_corrigidos = [i for i in itens_corrigidos 
                               if i.get("numero_item") not in numeros_para_remover]
    
    # Marcar descricoes repetidas com aviso (nao remove, mas sinaliza)
    if "descricoes_repetidas" in anomalias:
        for rep in anomalias["descricoes_repetidas"]:
            correcoes["itens_mantidos_com_aviso"].append({
                "descricao": rep["descricao"],
                "numeros": rep["numeros"],
                "aviso": "Mesma descricao em numeros distantes - verificar manualmente"
            })
    
    return itens_corrigidos, correcoes


def validar_pos_consenso(itens: List[Dict], estatisticas: Dict) -> Tuple[List[Dict], Dict]:
    """
    v14: Camada de validacao pos-consenso.
    
    1. Detecta anomalias
    2. Tenta corrigir com alta confianca
    3. Loga tudo para aprendizado futuro
    """
    anomalias = detectar_anomalias(itens)
    
    if anomalias:
        logger.warning(f"v14 ANOMALIAS DETECTADAS: {anomalias}")
        
        itens_corrigidos, correcoes = corrigir_anomalias(itens, anomalias)
        
        if correcoes["itens_removidos"]:
            logger.info(f"v14 CORRECOES: Removidos {len(correcoes['itens_removidos'])} itens suspeitos")
        
        estatisticas_atualizadas = {
            **estatisticas,
            "anomalias_detectadas": anomalias,
            "correcoes_aplicadas": correcoes
        }
        
        return itens_corrigidos, estatisticas_atualizadas
    
    return itens, estatisticas


# =============================================================================
# v27: FALLBACK CABECALHO ESTRUTURADO + TABELAS CONTINUACAO
# =============================================================================

def normalizar_texto_cabecalho(texto: str) -> str:
    """Normaliza texto para comparacao de cabecalho."""
    if not texto:
        return ""
    texto = texto.lower().strip()
    # Remover acentos
    acentos = {
        '\xe1': 'a', '\xe0': 'a', '\xe3': 'a', '\xe2': 'a',
        '\xe9': 'e', '\xe8': 'e', '\xea': 'e',
        '\xed': 'i', '\xec': 'i', '\xee': 'i',
        '\xf3': 'o', '\xf2': 'o', '\xf5': 'o', '\xf4': 'o',
        '\xfa': 'u', '\xf9': 'u', '\xfb': 'u',
        '\xe7': 'c'
    }
    for ac, sem in acentos.items():
        texto = texto.replace(ac, sem)
    return texto


def detectar_cabecalho_estruturado(row: List) -> Tuple[bool, Dict[str, int]]:
    """
    v27: Detecta se uma linha e cabecalho de tabela de itens.
    
    Criterio:
    - DESCRICAO obrigatorio
    - Pelo menos 1 opcional: UNIDADE, VALOR, QUANTIDADE, IDENTIFICACAO
    
    Nota: editais de servicos podem nao ter UNIDADE (ex: CISAMURES)
    """
    mapa = {}
    tem_descricao = False
    tem_opcional = False
    
    for idx, cell in enumerate(row):
        texto = normalizar_texto_cabecalho(str(cell or ""))
        if not texto:
            continue
        
        # Verificar DESCRICAO (obrigatorio)
        if "descricao" not in mapa:
            for padrao in CABECALHO_DESCRICAO:
                if normalizar_texto_cabecalho(padrao) in texto:
                    mapa["descricao"] = idx
                    tem_descricao = True
                    break
        
        # Verificar UNIDADE (opcional)
        if "unidade" not in mapa:
            for padrao in CABECALHO_UNIDADE:
                if normalizar_texto_cabecalho(padrao) in texto:
                    mapa["unidade"] = idx
                    tem_opcional = True
                    break
        
        # Verificar IDENTIFICACAO (opcional)
        if "identificacao" not in mapa:
            for padrao in CABECALHO_IDENTIFICACAO:
                if normalizar_texto_cabecalho(padrao) in texto:
                    mapa["identificacao"] = idx
                    tem_opcional = True
                    break
        
        # Verificar QUANTIDADE (opcional)
        if "quantidade" not in mapa:
            for padrao in CABECALHO_QUANTIDADE:
                if normalizar_texto_cabecalho(padrao) in texto:
                    mapa["quantidade"] = idx
                    tem_opcional = True
                    break
        
        # Verificar VALOR (opcional)
        if "valor" not in mapa:
            for padrao in CABECALHO_VALOR:
                if normalizar_texto_cabecalho(padrao) in texto:
                    mapa["valor"] = idx
                    tem_opcional = True
                    break
    
    # Criterio: DESCRICAO + pelo menos 1 opcional
    is_valid = tem_descricao and tem_opcional
    return is_valid, mapa


def linha_e_cabecalho_ou_vazia(row: List) -> bool:
    """
    v27: Verifica se linha e cabecalho repetido ou vazia.
    """
    conteudo = [str(c or "").strip() for c in row]
    if not any(conteudo):
        return True
    
    texto_row = " ".join(conteudo).lower()
    
    # Linha de titulo de especialidade
    if "especialidade:" in texto_row:
        return True
    
    # Linha de cabecalho
    if ("codigo" in texto_row or "codigo" in texto_row) and "especifica" in texto_row:
        return True
    
    # Celulas merged (todas iguais)
    celulas_unicas = set(c for c in conteudo if c)
    if len(celulas_unicas) == 1 and len(conteudo) > 1:
        return True
    
    return False


def detectar_tabela_continuacao(rows: List[List]) -> Tuple[bool, Dict[str, int]]:
    """
    v27: Detecta tabelas de continuacao (sem cabecalho mas com dados validos).
    
    Criterios:
    - NAO tem cabecalho nas primeiras linhas
    - Primeira coluna: identificador curto (<30 chars)
    - Segunda coluna: texto descritivo (>5 chars)
    - Pelo menos 2 linhas com essa estrutura
    """
    if len(rows) < 1:
        return False, {}
    
    # Verificar se NAO tem cabecalho nas primeiras linhas
    for row in rows[:2]:
        texto_row = " ".join(str(c or "") for c in row).lower()
        if ("codigo" in texto_row or "codigo" in texto_row) and "especifica" in texto_row:
            return False, {}  # Tem cabecalho, nao e continuacao
    
    # Verificar estrutura das linhas de dados
    linhas_validas = 0
    
    for row in rows[:5]:
        if len(row) < 2:
            continue
        
        col0 = str(row[0] or "").strip()
        col1 = str(row[1] or "").strip()
        
        # Pular linhas de titulo
        if "especialidade:" in col0.lower():
            continue
        
        # Col0: identificador (nao vazio, nao muito longo)
        if not col0 or len(col0) < 2 or len(col0) > 30:
            continue
        
        # Col1: texto descritivo (minimo 5 chars)
        if not col1 or len(col1) < 5:
            continue
        
        linhas_validas += 1
    
    # Se pelo menos 2 linhas tem estrutura valida
    if linhas_validas >= 2:
        mapa = {
            "identificacao": 0,
            "descricao": 1,
        }
        # Tentar encontrar coluna de valor
        for row in rows[:3]:
            for idx in range(2, min(5, len(row))):
                cell = str(row[idx] or "")
                if "r$" in cell.lower() or re.match(r'^[\d,.\s]+$', cell.strip()):
                    mapa["valor"] = idx
                    break
            if "valor" in mapa:
                break
        
        return True, mapa
    
    return False, {}


def extrair_itens_tabela_estruturada(rows: List[List], header_idx: int, mapa: Dict[str, int], 
                                      contador_item: int) -> Tuple[List[Dict], int]:
    """
    v27: Extrai itens de uma tabela estruturada.
    Cada linha de dados = 1 item.
    """
    itens = []
    
    for row_idx, row in enumerate(rows):
        if row_idx <= header_idx:
            continue
        
        if linha_e_cabecalho_ou_vazia(row):
            continue
        
        # Extrair dados
        identificador = ""
        if "identificacao" in mapa and mapa["identificacao"] < len(row):
            identificador = str(row[mapa["identificacao"]] or "").strip()
        
        descricao = ""
        if "descricao" in mapa and mapa["descricao"] < len(row):
            descricao = str(row[mapa["descricao"]] or "").strip()
        
        # Pular se descricao vazia ou muito curta
        if not descricao or len(descricao) < 3:
            continue
        
        # Usar identificador ou contador como numero_item
        numero_item = identificador if identificador else str(contador_item)
        
        item = {
            "numero_item": numero_item,
            "lote": None,
            "descricao": descricao.replace('\n', ' ').strip(),
            "quantidade": None,
            "unidade": None,
            "valor_unitario": None,
            "valor_total": None,
            "codigo_catmat": None,
            "codigo_catser": None,
            "_meta": {
                "fontes": ["estruturado"],
                "n_fontes": 1,
                "consenso": True,
                "metodo": "cabecalho_estruturado"
            }
        }
        
        # Extrair campos opcionais
        if "unidade" in mapa and mapa["unidade"] < len(row):
            item["unidade"] = str(row[mapa["unidade"]] or "").strip() or None
        
        if "quantidade" in mapa and mapa["quantidade"] < len(row):
            item["quantidade"] = str(row[mapa["quantidade"]] or "").strip() or None
        
        if "valor" in mapa and mapa["valor"] < len(row):
            valor = str(row[mapa["valor"]] or "").strip()
            if valor:
                item["valor_unitario"] = valor
        
        itens.append(item)
        contador_item += 1
    
    return itens, contador_item


def pipeline_fallback_estruturado(tabelas: List[Dict]) -> Tuple[List[Dict], Dict]:
    """
    v27: Pipeline de fallback para tabelas estruturadas.
    
    Usado quando metodo principal (numeros sequenciais) retorna poucos itens.
    
    Processa:
    1. Tabelas com cabecalho estruturado (DESCRICAO + UNIDADE)
    2. Tabelas de continuacao (sem cabecalho mas mesma estrutura)
    """
    logger.info("v27: Iniciando fallback cabecalho estruturado")
    
    todos_itens = []
    contador_item = 1
    stats = {
        "tabelas_com_cabecalho": 0,
        "tabelas_continuacao": 0,
        "tabelas_ignoradas": 0
    }
    
    for tabela in tabelas:
        rows = tabela.get("rows", [])
        if not rows:
            continue
        
        # Tentar detectar cabecalho estruturado
        header_idx = -1
        mapa = {}
        
        for i, row in enumerate(rows[:5]):
            is_valid, detected_mapa = detectar_cabecalho_estruturado(row)
            if is_valid:
                header_idx = i
                mapa = detected_mapa
                break
        
        if header_idx >= 0:
            # Tabela com cabecalho
            stats["tabelas_com_cabecalho"] += 1
            itens, contador_item = extrair_itens_tabela_estruturada(
                rows, header_idx, mapa, contador_item
            )
            todos_itens.extend(itens)
        else:
            # Tentar como tabela de continuacao
            is_continuacao, mapa_cont = detectar_tabela_continuacao(rows)
            if is_continuacao:
                stats["tabelas_continuacao"] += 1
                itens, contador_item = extrair_itens_tabela_estruturada(
                    rows, -1, mapa_cont, contador_item
                )
                todos_itens.extend(itens)
            else:
                stats["tabelas_ignoradas"] += 1
    
    logger.info(f"v27: Fallback extraiu {len(todos_itens)} itens")
    logger.info(f"v27: Stats = {stats}")
    
    return todos_itens, stats


def deve_usar_fallback(itens_finais: List[Dict]) -> bool:
    """
    v27: Decide se deve usar fallback estruturado.
    
    Criterios:
    - Poucos itens extraidos (< 10)
    - Itens parecem ser titulos de secao (descricoes curtas ou palavras tipicas)
    """
    if len(itens_finais) < 10:
        return True
    
    # Verificar se itens parecem ser titulos de secao
    palavras_secao = [
        "anexo", "habilitacao", "procedimento", "credenciamento",
        "documentacao", "disposicoes", "objeto",
        "fundamentacao", "impugnacao"
    ]
    
    itens_suspeitos = 0
    for item in itens_finais[:20]:  # Verificar primeiros 20
        desc = item.get("descricao", "").lower()
        
        # Descricao muito curta
        if len(desc) < 30:
            itens_suspeitos += 1
            continue
        
        # Contem palavras tipicas de secao
        for palavra in palavras_secao:
            if palavra in desc:
                itens_suspeitos += 1
                break
    
    # Se mais de 50% dos itens sao suspeitos, usar fallback
    if len(itens_finais) > 0 and itens_suspeitos / len(itens_finais) > 0.5:
        logger.info(f"v27: {itens_suspeitos}/{len(itens_finais)} itens parecem titulos de secao")
        return True
    
    return False


# =============================================================================
# PIPELINE PRINCIPAL v27
# =============================================================================

def extrair_itens_pdf(pdf_path: str) -> Dict:
    logger.info("=== EXTRACT_ITEMS v27: FALLBACK CABECALHO ESTRUTURADO ===")
    
    tabelas_pymupdf, texto_pymupdf = extrair_tabelas_pymupdf(pdf_path)
    tabelas_pdfplumber, texto_pdfplumber = extrair_tabelas_pdfplumber(pdf_path)
    
    texto_por_pagina = texto_pymupdf or texto_pdfplumber or {}
    
    pagina_limite = detectar_pagina_limite_proposta(texto_por_pagina)
    logger.info(f"v27: Pagina limite = {pagina_limite}")
    
    itens_por_fonte = {}
    camadas_disponiveis = []
    
    if tabelas_pymupdf:
        itens_pymupdf = extrair_itens_de_tabelas(tabelas_pymupdf, pagina_limite, "pymupdf")
        itens_por_fonte["pymupdf"] = itens_pymupdf
        camadas_disponiveis.append("pymupdf")
        logger.info(f"PyMuPDF: {len(itens_pymupdf)} itens")
    
    if tabelas_pdfplumber:
        itens_pdfplumber = extrair_itens_de_tabelas(tabelas_pdfplumber, pagina_limite, "pdfplumber")
        itens_por_fonte["pdfplumber"] = itens_pdfplumber
        camadas_disponiveis.append("pdfplumber")
        logger.info(f"pdfplumber: {len(itens_pdfplumber)} itens")
    
    if texto_por_pagina:
        itens_texto = extrair_itens_por_texto(texto_por_pagina, pagina_limite)
        if itens_texto:
            itens_por_fonte["texto"] = itens_texto
            camadas_disponiveis.append("texto")
            logger.info(f"TEXTO: {len(itens_texto)} itens")
    
    n_camadas = len(camadas_disponiveis)
    
    # v27: Tentar metodo principal primeiro
    itens_finais = []
    stats_consenso = {}
    usou_fallback = False
    stats_fallback = {}
    
    if n_camadas > 0:
        min_votos = 2 if n_camadas >= 2 else 1
        itens_finais, stats_consenso = consenso_real(itens_por_fonte, min_votos)
        itens_finais, stats_consenso = validar_pos_consenso(itens_finais, stats_consenso)
    
    # v27: Verificar se deve usar fallback
    if deve_usar_fallback(itens_finais):
        logger.info("v27: Ativando fallback cabecalho estruturado")
        
        # Usar tabelas do PyMuPDF para fallback (mais confiavel)
        tabelas_fallback = tabelas_pymupdf or tabelas_pdfplumber or []
        
        if tabelas_fallback:
            itens_fallback, stats_fallback = pipeline_fallback_estruturado(tabelas_fallback)
            
            # Usar fallback se encontrou MAIS itens
            if len(itens_fallback) > len(itens_finais):
                logger.info(f"v27: Fallback encontrou mais itens ({len(itens_fallback)} > {len(itens_finais)})")
                itens_finais = itens_fallback
                usou_fallback = True
                camadas_disponiveis = ["estruturado"]
                n_camadas = 1
    
    # Resultado final
    if not itens_finais:
        return {
            "success": False,
            "error": "Nenhum item extraido (metodo principal e fallback falharam)",
            "total_itens": 0,
            "itens": []
        }
    
    # Calcular estatisticas
    numeros = []
    for item in itens_finais:
        num_str = item.get("numero_item", "")
        if num_str.isdigit():
            numeros.append(int(num_str))
    
    max_num = max(numeros) if numeros else 0
    numeros_esperados = set(range(1, max_num + 1)) if max_num else set()
    numeros_encontrados = set(numeros)
    faltando = numeros_esperados - numeros_encontrados
    
    resultado = {
        "success": True,
        "total_itens": len(itens_finais),
        "pagina_limite_proposta": pagina_limite,
        "itens": itens_finais,
        "estatisticas": {
            "camadas_disponiveis": camadas_disponiveis,
            "n_camadas": n_camadas,
            "usou_fallback": usou_fallback,
            "por_camada": {
                "pymupdf": len(itens_por_fonte.get("pymupdf", [])),
                "pdfplumber": len(itens_por_fonte.get("pdfplumber", [])),
                "texto": len(itens_por_fonte.get("texto", [])),
            },
            "consenso": stats_consenso,
            "max_numero": max_num,
            "numeros_faltando": sorted(faltando)[:20] if faltando else [],
            "cobertura": f"{len(numeros_encontrados)}/{max_num}" if max_num else "N/A"
        }
    }
    
    if usou_fallback:
        resultado["estatisticas"]["fallback"] = stats_fallback
    
    return resultado


# =============================================================================
# AZURE FUNCTION
# =============================================================================

def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("=== EXTRACT_ITEMS v27 ===")
    
    try:
        req_body = req.get_json()
        blob_name = req_body.get("blob_name")
        
        if not blob_name:
            return func.HttpResponse(
                json.dumps({"success": False, "error": "blob_name obrigatorio"}),
                status_code=400,
                mimetype="application/json"
            )
        
        blob_service = get_blob_service_client()
        container = blob_service.get_container_client(
            os.environ.get("BLOB_CONTAINER_NAME", "editais-teste")
        )
        
        pdf_blob = container.get_blob_client(blob_name)
        
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_blob.download_blob().readall())
            tmp_path = tmp.name
        
        try:
            resultado = extrair_itens_pdf(tmp_path)
            resultado["blob_name"] = blob_name
        finally:
            os.unlink(tmp_path)
        
        logger.info(f"v12: {resultado.get('total_itens', 0)} itens")
        
        return func.HttpResponse(
            json.dumps(resultado, ensure_ascii=False, default=str),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logger.error(f"Erro: {e}", exc_info=True)
        return func.HttpResponse(
            json.dumps({"success": False, "error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )


handle_extract_items = main
