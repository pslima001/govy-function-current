# govy/api/extract_items.py
"""
Extracao de itens de editais - v8: HEADER + SEQUENCIA
Correcoes:
1. Mapear colunas pelo HEADER (nao por "texto mais longo")
2. Filtrar ancoras por SEQUENCIA CONTINUA (1,2,3... ate quebrar)
3. Buscar descricao na coluna correta
Custo: $0 (100% Python)
"""
import os
import re
import json
import logging
import tempfile
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
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

# Padroes para header
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
                logger.info(f"v8: Secao Proposta detectada pagina {page_num}")
                return page_num
    return 9999


# =============================================================================
# EXTRACAO DE TABELAS
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
        return [], {}
    except Exception as e:
        logger.error(f"PyMuPDF erro: {e}")
        return [], {}


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
        return [], {}
    except Exception as e:
        logger.error(f"pdfplumber erro: {e}")
        return [], {}


# =============================================================================
# v8: MAPEAMENTO DE COLUNAS POR HEADER
# =============================================================================

def mapear_colunas_por_header(header_row: List) -> Dict[str, int]:
    """Mapeia colunas pelo conteudo do header."""
    mapa = {}
    
    for idx, cell in enumerate(header_row):
        texto = str(cell or "").lower().strip()
        
        # Verificar cada tipo
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
            elif "valor" not in mapa:
                mapa["valor"] = idx
    
    return mapa


def encontrar_header(tabela: Dict) -> Tuple[int, Dict[str, int]]:
    """Encontra a linha de header e mapeia colunas."""
    rows = tabela.get("rows", [])
    
    for row_idx, row in enumerate(rows[:5]):  # Header nas primeiras 5 linhas
        texto_row = " ".join(str(c or "").lower() for c in row)
        
        # Header tem palavras-chave
        tem_item = any(p in texto_row for p in PADROES_NUMERO)
        tem_desc = any(p in texto_row for p in PADROES_DESCRICAO)
        tem_valor = any(p in texto_row for p in PADROES_VALOR)
        
        if (tem_item and tem_desc) or (tem_item and tem_valor) or (tem_desc and tem_valor):
            mapa = mapear_colunas_por_header(row)
            if mapa:
                logger.debug(f"Header encontrado na linha {row_idx}: {mapa}")
                return row_idx, mapa
    
    return -1, {}


# =============================================================================
# v8: ENCONTRAR ANCORAS COM SEQUENCIA VALIDA
# =============================================================================

def encontrar_todas_ancoras(tabelas: List[Dict], pagina_limite: int) -> List[Dict]:
    """Encontra todos os candidatos a ancora (numeros)."""
    todas_ancoras = []
    
    for tabela in tabelas:
        page_num = tabela.get("page_number", 0)
        if page_num >= pagina_limite:
            continue
        
        rows = tabela.get("rows", [])
        fonte = tabela.get("fonte", "")
        
        # Encontrar header e mapa de colunas
        header_idx, mapa_colunas = encontrar_header(tabela)
        col_numero = mapa_colunas.get("numero", 0)
        
        for row_idx, row in enumerate(rows):
            if row_idx <= header_idx:
                continue
            
            # Buscar numero na coluna mapeada OU em qualquer coluna
            for col_idx, cell in enumerate(row):
                valor = str(cell or "").strip()
                
                # Ancora = numero inteiro de 1 a 500
                match = re.match(r'^(\d{1,3})$', valor)
                if match:
                    num = int(match.group(1))
                    if 1 <= num <= 500:
                        # Priorizar se esta na coluna de numero
                        prioridade = 1 if col_idx == col_numero else 0
                        
                        todas_ancoras.append({
                            "numero": num,
                            "page": page_num,
                            "row_idx": row_idx,
                            "col_idx": col_idx,
                            "row_data": row,
                            "fonte": fonte,
                            "tabela_rows": rows,
                            "header_idx": header_idx,
                            "mapa_colunas": mapa_colunas,
                            "prioridade": prioridade,
                        })
    
    return todas_ancoras


def filtrar_por_sequencia_continua(ancoras: List[Dict]) -> List[Dict]:
    """Filtra ancoras mantendo apenas sequencia continua (1,2,3...)."""
    
    # Agrupar por numero
    ancoras_por_numero = defaultdict(list)
    for a in ancoras:
        ancoras_por_numero[a["numero"]].append(a)
    
    numeros = sorted(ancoras_por_numero.keys())
    
    if not numeros or 1 not in numeros:
        logger.warning("v8: Sequencia nao comeca em 1")
        return []
    
    # Encontrar sequencia continua
    sequencia_valida = set()
    for n in range(1, max(numeros) + 1):
        if n in numeros:
            sequencia_valida.add(n)
        else:
            # Tolerar ate 2 gaps
            if n + 1 in numeros or n + 2 in numeros:
                continue
            else:
                break  # Sequencia quebrou de vez
    
    logger.info(f"v8: Sequencia valida 1-{max(sequencia_valida) if sequencia_valida else 0}")
    
    # Selecionar melhor ancora para cada numero da sequencia
    ancoras_finais = []
    for num in sorted(sequencia_valida):
        candidatos = ancoras_por_numero[num]
        # Preferir: prioridade alta + mais dados na linha
        melhor = max(candidatos, key=lambda x: (
            x["prioridade"],
            sum(1 for c in x["row_data"] if c)
        ))
        ancoras_finais.append(melhor)
    
    return ancoras_finais


# =============================================================================
# v8: RECONSTRUIR ITEM COM COLUNA CORRETA
# =============================================================================

def buscar_descricao(tabela_rows: List, row_idx: int, mapa: Dict[str, int], col_numero: int) -> Optional[str]:
    """Busca descricao na coluna correta, ou na linha anterior se vazia."""
    
    col_desc = mapa.get("descricao")
    row = tabela_rows[row_idx]
    
    # Tentar coluna mapeada
    if col_desc is not None and col_desc < len(row):
        texto = str(row[col_desc] or "").strip()
        texto = re.sub(r'\s+', ' ', texto)
        if len(texto) >= 10:
            return texto
    
    # Tentar encontrar texto longo na linha (ignorando coluna de numero)
    for idx, cell in enumerate(row):
        if idx == col_numero:
            continue
        texto = str(cell or "").strip()
        texto = re.sub(r'\s+', ' ', texto)
        # Deve ser longo e nao parecer unidade/valor
        if len(texto) >= 15 and not re.match(r'^[\d,.\s]+$', texto):
            # Verificar se nao eh unidade
            texto_lower = texto.lower()
            unidades = ["frasco", "comprimido", "bisnaga", "envelope", "capsula", "ampola", "ml", "mg", "un", "und"]
            eh_so_unidade = any(texto_lower.startswith(u) and len(texto) < 20 for u in unidades)
            if not eh_so_unidade:
                return texto
    
    # Buscar na linha ANTERIOR
    if row_idx > 0:
        row_ant = tabela_rows[row_idx - 1]
        
        # Primeiro tentar coluna de descricao
        if col_desc is not None and col_desc < len(row_ant):
            texto = str(row_ant[col_desc] or "").strip()
            texto = re.sub(r'\s+', ' ', texto)
            if len(texto) >= 10:
                return texto
        
        # Depois qualquer texto longo
        for idx, cell in enumerate(row_ant):
            texto = str(cell or "").strip()
            texto = re.sub(r'\s+', ' ', texto)
            if len(texto) >= 15 and not re.match(r'^[\d,.\s]+$', texto):
                return texto
    
    return None


def buscar_campo(row: List, mapa: Dict[str, int], campo: str, col_numero: int) -> Optional[str]:
    """Busca um campo especifico na linha."""
    col = mapa.get(campo)
    
    if col is not None and col < len(row):
        valor = str(row[col] or "").strip()
        if valor:
            return valor
    
    return None


def reconstruir_item(ancora: Dict) -> Dict:
    """Reconstroi item a partir da ancora usando mapa de colunas."""
    
    numero = ancora["numero"]
    row_idx = ancora["row_idx"]
    col_idx = ancora["col_idx"]
    row_data = ancora["row_data"]
    tabela_rows = ancora["tabela_rows"]
    page = ancora["page"]
    fonte = ancora["fonte"]
    mapa = ancora.get("mapa_colunas", {})
    
    item = {
        "numero_item": str(numero),
        "lote": None,
        "descricao": None,
        "quantidade": None,
        "unidade": None,
        "valor_unitario": None,
        "valor_total": None,
        "codigo_catmat": None,
        "codigo_catser": None,
        "_meta": {"page": page, "row": row_idx, "fonte": fonte}
    }
    
    # Buscar descricao (logica especial)
    item["descricao"] = buscar_descricao(tabela_rows, row_idx, mapa, col_idx)
    
    # Buscar outros campos
    item["quantidade"] = buscar_campo(row_data, mapa, "quantidade", col_idx)
    item["unidade"] = buscar_campo(row_data, mapa, "unidade", col_idx)
    item["codigo_catmat"] = buscar_campo(row_data, mapa, "catmat", col_idx)
    
    valor_unit = buscar_campo(row_data, mapa, "valor_unit", col_idx)
    valor_total = buscar_campo(row_data, mapa, "valor_total", col_idx)
    item["valor_unitario"] = valor_unit
    item["valor_total"] = valor_total
    
    return item


# =============================================================================
# VALIDACAO E CONSENSO
# =============================================================================

def validar_item(item: Dict) -> bool:
    """Item valido = tem numero + descricao."""
    tem_numero = item.get("numero_item")
    tem_descricao = item.get("descricao") and len(item["descricao"]) >= 8
    return bool(tem_numero and tem_descricao)


def consenso_itens(itens_lista: List[Dict]) -> List[Dict]:
    """Agrupa itens por numero e seleciona o mais completo."""
    itens_por_numero = defaultdict(list)
    
    for item in itens_lista:
        num = item.get("numero_item")
        if num:
            itens_por_numero[num].append(item)
    
    itens_finais = []
    for num in sorted(itens_por_numero.keys(), key=lambda x: int(x) if x.isdigit() else 999):
        candidatos = itens_por_numero[num]
        
        def score(it):
            campos = sum(1 for k, v in it.items() if v and not k.startswith("_"))
            desc_len = len(it.get("descricao") or "")
            return campos * 100 + desc_len
        
        melhor = max(candidatos, key=score)
        melhor["_consenso"] = len(candidatos)
        itens_finais.append(melhor)
    
    return itens_finais


# =============================================================================
# PIPELINE PRINCIPAL v8
# =============================================================================

def extrair_itens_pdf(pdf_path: str) -> Dict:
    logger.info("=== EXTRACT_ITEMS v8: HEADER + SEQUENCIA ===")
    
    # 1. Extrair tabelas com AMBAS as bibliotecas
    tabelas_pymupdf, texto_pymupdf = extrair_tabelas_pymupdf(pdf_path)
    tabelas_pdfplumber, texto_pdfplumber = extrair_tabelas_pdfplumber(pdf_path)
    
    todas_tabelas = tabelas_pymupdf + tabelas_pdfplumber
    texto_por_pagina = texto_pymupdf or texto_pdfplumber or {}
    
    if not todas_tabelas:
        return {
            "success": False,
            "error": "Nenhuma tabela encontrada",
            "total_itens": 0,
            "itens": []
        }
    
    # 2. Detectar limite de pagina
    pagina_limite = detectar_pagina_limite_proposta(texto_por_pagina)
    logger.info(f"v8: Pagina limite = {pagina_limite}")
    
    # 3. Encontrar TODAS as ancoras
    todas_ancoras = encontrar_todas_ancoras(todas_tabelas, pagina_limite)
    logger.info(f"v8: {len(todas_ancoras)} candidatos a ancora")
    
    # 4. Filtrar por SEQUENCIA CONTINUA
    ancoras_validas = filtrar_por_sequencia_continua(todas_ancoras)
    logger.info(f"v8: {len(ancoras_validas)} ancoras na sequencia")
    
    if not ancoras_validas:
        return {
            "success": False,
            "error": "Nenhuma sequencia de itens encontrada",
            "total_itens": 0,
            "itens": []
        }
    
    # 5. Reconstruir cada item
    todos_itens = []
    for ancora in ancoras_validas:
        item = reconstruir_item(ancora)
        if validar_item(item):
            todos_itens.append(item)
    
    logger.info(f"v8: {len(todos_itens)} itens reconstruidos")
    
    # 6. Consenso
    itens_finais = consenso_itens(todos_itens)
    
    # 7. Estatisticas
    numeros = [int(i["numero_item"]) for i in itens_finais if i["numero_item"].isdigit()]
    max_num = max(numeros) if numeros else 0
    numeros_esperados = set(range(1, max_num + 1))
    numeros_encontrados = set(numeros)
    faltando = numeros_esperados - numeros_encontrados
    
    logger.info(f"v8: {len(itens_finais)} itens finais, faltando: {sorted(faltando)[:10]}")
    
    return {
        "success": True,
        "total_itens": len(itens_finais),
        "pagina_limite_proposta": pagina_limite,
        "itens": itens_finais,
        "estatisticas": {
            "ancoras_candidatas": len(todas_ancoras),
            "ancoras_sequencia": len(ancoras_validas),
            "itens_validos": len(todos_itens),
            "itens_finais": len(itens_finais),
            "max_numero": max_num,
            "numeros_faltando": sorted(faltando)[:20] if faltando else [],
            "cobertura": f"{len(numeros_encontrados)}/{max_num}" if max_num else "N/A"
        }
    }


# =============================================================================
# AZURE FUNCTION
# =============================================================================

def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("=== EXTRACT_ITEMS v8 ===")
    
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
        
        logger.info(f"v8: {resultado.get('total_itens', 0)} itens")
        
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

