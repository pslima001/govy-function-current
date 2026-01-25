# govy/api/extract_items.py
"""
Extracao de itens de editais - v11: 3 CAMADAS (tabelas + texto)
Estrategia:
1. PyMuPDF    -> tabelas estruturadas
2. pdfplumber -> tabelas estruturadas  
3. TEXTO      -> regex em texto corrido
Consenso: item valido se 2+ camadas concordam
Custo: $0 (100% Python)
"""
import os
import re
import json
import logging
import tempfile
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict, Counter
import azure.functions as func
from azure.storage.blob import BlobServiceClient

logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTES
# =============================================================================

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


# =============================================================================
# DETECCAO DE SECAO (TR vs PROPOSTA)
# =============================================================================

def detectar_pagina_limite_proposta(texto_por_pagina: Dict[int, str]) -> int:
    for page_num in sorted(texto_por_pagina.keys()):
        texto = texto_por_pagina[page_num].lower()
        for marcador in SECOES_PROPOSTA:
            if marcador in texto:
                logger.info(f"v11: Secao Proposta detectada pagina {page_num}")
                return page_num
    return 9999


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
    Padroes detectados:
    - "1. DESCRICAO"
    - "Item 1 - DESCRICAO"
    - "1 DESCRICAO COM MAIUSCULAS"
    - "01. DESCRICAO"
    """
    
    itens = []
    
    # Padroes de item no texto
    padroes = [
        # "1. DESCRICAO" ou "01. DESCRICAO"
        re.compile(r'^\s*(\d{1,3})\s*[.\-â€“)]\s*([A-ZÃÃ‰ÃÃ“ÃšÃ‚ÃŠÃ”ÃƒÃ•Ã‡][A-ZÃÃ‰ÃÃ“ÃšÃ‚ÃŠÃ”ÃƒÃ•Ã‡\s\d,./\-()%+]+)', re.MULTILINE),
        # "Item 1: DESCRICAO" ou "Item 1 - DESCRICAO"
        re.compile(r'[Ii]tem\s*(\d{1,3})\s*[:\-â€“]\s*([A-ZÃÃ‰ÃÃ“ÃšÃ‚ÃŠÃ”ÃƒÃ•Ã‡][A-Za-zÃ¡Ã©Ã­Ã³ÃºÃ¢ÃªÃ´Ã£ÃµÃ§\s\d,./\-()%+]+)', re.MULTILINE),
        # Numero no inicio da linha seguido de texto em maiusculas
        re.compile(r'^(\d{1,3})\s+([A-ZÃÃ‰ÃÃ“ÃšÃ‚ÃŠÃ”ÃƒÃ•Ã‡]{3,}[A-ZÃÃ‰ÃÃ“ÃšÃ‚ÃŠÃ”ÃƒÃ•Ã‡\s\d,./\-()%+]{10,})', re.MULTILINE),
    ]
    
    # Coletar texto das paginas validas
    texto_completo = ""
    for page_num in sorted(texto_por_pagina.keys()):
        if page_num < pagina_limite:
            texto_completo += texto_por_pagina[page_num] + "\n"
    
    # Encontrar matches
    itens_encontrados = {}
    
    for padrao in padroes:
        matches = padrao.findall(texto_completo)
        for match in matches:
            num_str, descricao = match
            num = int(num_str)
            
            # Filtrar: 1-500, descricao >= 10 chars
            if 1 <= num <= 500:
                descricao = descricao.strip()
                descricao = re.sub(r'\s+', ' ', descricao)
                
                # Limpar descricao (remover valores, quantidades no final)
                descricao = re.sub(r'\s+\d+[.,]\d{2}\s*$', '', descricao)
                descricao = re.sub(r'\s+\d{3,}\s*$', '', descricao)
                
                if len(descricao) >= 10:
                    # Guardar se nao existe ou se esta eh mais longa
                    if num not in itens_encontrados or len(descricao) > len(itens_encontrados[num]):
                        itens_encontrados[num] = descricao
    
    # Filtrar por sequencia continua
    numeros = set(itens_encontrados.keys())
    if 1 not in numeros or 2 not in numeros:
        logger.info("v11 TEXTO: sequencia nao comeca em 1,2")
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
    
    # Montar lista de itens
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
    
    logger.info(f"v11 TEXTO: {len(itens)} itens extraidos")
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
# EXTRACAO DE ITENS POR TABELA
# =============================================================================

def buscar_descricao(tabela_rows: List, row_idx: int, mapa: Dict[str, int], col_numero: int) -> Optional[str]:
    col_desc = mapa.get("descricao")
    row = tabela_rows[row_idx]
    
    if col_desc is not None and col_desc < len(row):
        texto = str(row[col_desc] or "").strip()
        texto = re.sub(r'\s+', ' ', texto)
        if len(texto) >= 10:
            return texto
    
    for idx, cell in enumerate(row):
        if idx == col_numero:
            continue
        texto = str(cell or "").strip()
        texto = re.sub(r'\s+', ' ', texto)
        if len(texto) >= 15 and not re.match(r'^[\d,.\s]+$', texto):
            texto_lower = texto.lower()
            unidades = ["frasco", "comprimido", "bisnaga", "envelope", "capsula", "ampola"]
            eh_so_unidade = any(texto_lower.startswith(u) and len(texto) < 20 for u in unidades)
            if not eh_so_unidade:
                return texto
    
    if row_idx > 0:
        row_ant = tabela_rows[row_idx - 1]
        if col_desc is not None and col_desc < len(row_ant):
            texto = str(row_ant[col_desc] or "").strip()
            texto = re.sub(r'\s+', ' ', texto)
            if len(texto) >= 10:
                return texto
        for idx, cell in enumerate(row_ant):
            texto = str(cell or "").strip()
            texto = re.sub(r'\s+', ' ', texto)
            if len(texto) >= 15 and not re.match(r'^[\d,.\s]+$', texto):
                return texto
    
    return None


def buscar_campo(row: List, mapa: Dict[str, int], campo: str) -> Optional[str]:
    col = mapa.get(campo)
    if col is not None and col < len(row):
        valor = str(row[col] or "").strip()
        if valor:
            return valor
    return None


def extrair_itens_de_tabelas(tabelas: List[Dict], pagina_limite: int, fonte: str) -> List[Dict]:
    """Extrai itens de tabelas de uma biblioteca especifica."""
    
    todas_ancoras = []
    
    for tabela in tabelas:
        page_num = tabela.get("page_number", 0)
        if page_num >= pagina_limite:
            continue
        
        rows = tabela.get("rows", [])
        header_idx, mapa = encontrar_header(tabela)
        col_numero = mapa.get("numero", 0)
        
        for row_idx, row in enumerate(rows):
            if row_idx <= header_idx:
                continue
            
            for col_idx, cell in enumerate(row):
                valor = str(cell or "").strip()
                match = re.match(r'^(\d{1,3})$', valor)
                if match:
                    num = int(match.group(1))
                    if 1 <= num <= 500:
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
        
        descricao = buscar_descricao(
            ancora["tabela_rows"],
            ancora["row_idx"],
            ancora["mapa"],
            ancora["col_idx"]
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
    
    # Agrupar por numero_item
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
        
        # CONSENSO: precisa de min_votos fontes
        if n_fontes >= min_votos:
            estatisticas["aceitos"] += 1
            
            # VOTACAO para descricao
            descricoes = [c["item"]["descricao"] for c in candidatos if c["item"].get("descricao")]
            
            if descricoes:
                # Tentar maioria
                contagem = Counter(descricoes)
                mais_comum, votos = contagem.most_common(1)[0]
                
                if votos >= 2:
                    descricao_final = mais_comum
                else:
                    # Sem maioria: escolher mais longa
                    descricao_final = max(descricoes, key=len)
            else:
                continue
            
            # Montar item final
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
            
            # Preencher outros campos (primeiro nao-nulo)
            for c in candidatos:
                it = c["item"]
                for campo in ["quantidade", "unidade", "valor_unitario", "valor_total", "codigo_catmat"]:
                    if not item_final.get(campo) and it.get(campo):
                        item_final[campo] = it[campo]
            
            itens_finais.append(item_final)
        else:
            estatisticas["rejeitados"] += 1
    
    logger.info(f"v11 CONSENSO: aceitos={estatisticas['aceitos']}, rejeitados={estatisticas['rejeitados']}")
    logger.info(f"v11 VOTOS: {estatisticas['por_votos']}")
    
    return itens_finais, estatisticas


# =============================================================================
# PIPELINE PRINCIPAL v11
# =============================================================================

def extrair_itens_pdf(pdf_path: str) -> Dict:
    logger.info("=== EXTRACT_ITEMS v11: 3 CAMADAS (tabelas + texto) ===")
    
    # 1. Extrair tabelas com PyMuPDF e pdfplumber
    tabelas_pymupdf, texto_pymupdf = extrair_tabelas_pymupdf(pdf_path)
    tabelas_pdfplumber, texto_pdfplumber = extrair_tabelas_pdfplumber(pdf_path)
    
    texto_por_pagina = texto_pymupdf or texto_pdfplumber or {}
    
    # 2. Detectar limite de pagina
    pagina_limite = detectar_pagina_limite_proposta(texto_por_pagina)
    logger.info(f"v11: Pagina limite = {pagina_limite}")
    
    # 3. Extrair itens com CADA CAMADA
    itens_por_fonte = {}
    camadas_disponiveis = []
    
    # Camada 1: PyMuPDF
    if tabelas_pymupdf:
        itens_pymupdf = extrair_itens_de_tabelas(tabelas_pymupdf, pagina_limite, "pymupdf")
        itens_por_fonte["pymupdf"] = itens_pymupdf
        camadas_disponiveis.append("pymupdf")
        logger.info(f"PyMuPDF: {len(itens_pymupdf)} itens")
    
    # Camada 2: pdfplumber
    if tabelas_pdfplumber:
        itens_pdfplumber = extrair_itens_de_tabelas(tabelas_pdfplumber, pagina_limite, "pdfplumber")
        itens_por_fonte["pdfplumber"] = itens_pdfplumber
        camadas_disponiveis.append("pdfplumber")
        logger.info(f"pdfplumber: {len(itens_pdfplumber)} itens")
    
    # Camada 3: TEXTO/REGEX
    if texto_por_pagina:
        itens_texto = extrair_itens_por_texto(texto_por_pagina, pagina_limite)
        if itens_texto:
            itens_por_fonte["texto"] = itens_texto
            camadas_disponiveis.append("texto")
            logger.info(f"TEXTO: {len(itens_texto)} itens")
    
    n_camadas = len(camadas_disponiveis)
    
    if n_camadas == 0:
        return {
            "success": False,
            "error": "Nenhuma camada conseguiu extrair itens",
            "total_itens": 0,
            "itens": []
        }
    
    # 4. CONSENSO REAL
    # Se 3 camadas: exigir 2 votos
    # Se 2 camadas: exigir 2 votos
    # Se 1 camada: aceitar 1 voto
    min_votos = 2 if n_camadas >= 2 else 1
    
    itens_finais, stats_consenso = consenso_real(itens_por_fonte, min_votos)
    
    # 5. Estatisticas
    numeros = [int(i["numero_item"]) for i in itens_finais if i["numero_item"].isdigit()]
    max_num = max(numeros) if numeros else 0
    numeros_esperados = set(range(1, max_num + 1))
    numeros_encontrados = set(numeros)
    faltando = numeros_esperados - numeros_encontrados
    
    return {
        "success": True,
        "total_itens": len(itens_finais),
        "pagina_limite_proposta": pagina_limite,
        "itens": itens_finais,
        "estatisticas": {
            "camadas_disponiveis": camadas_disponiveis,
            "n_camadas": n_camadas,
            "min_votos_exigidos": min_votos,
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


# =============================================================================
# AZURE FUNCTION
# =============================================================================

def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("=== EXTRACT_ITEMS v11 ===")
    
    try:
        req_body = req.get_json()
        blob_name = req_body.get("blob_name")
        
        if not blob_name:
            return func.HttpResponse(
                json.dumps({"success": False, "error": "blob_name obrigatorio"}),
                status_code=400,
                mimetype="application/json"
            )
        
        conn_str = os.environ.get("AzureWebJobsStorage")
        blob_service = BlobServiceClient.from_connection_string(conn_str)
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
        
        logger.info(f"v11: {resultado.get('total_itens', 0)} itens")
        
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

