# govy/api/extract_params.py
"""
Handler para extração de parâmetros de editais.

Este handler usa os extractors em govy/extractors/ para extrair:
- e001: Prazo de Entrega
- pg001: Prazo de Pagamento
- o001: Objeto da Licitação
- l001: Locais de Entrega

Última atualização: 15/01/2026
MODIFICADO: Adicionado retorno de candidatos escolhidos com detalhes
"""
import os
import json
import logging
import re

import azure.functions as func

logger = logging.getLogger(__name__)


def _extrair_numero_pagina(texto_completo: str, contexto: str) -> int:
    """
    Tenta identificar o número da página onde o contexto foi encontrado.
    
    Estratégia simples: procura por padrões como "Página X" ou similares
    próximos ao contexto.
    """
    # Procura por padrões comuns de numeração de página
    patterns = [
        r'p[aá]gina\s+(\d+)',
        r'p[aá]g\.\s*(\d+)',
        r'fls?\.\s*(\d+)',
    ]
    
    # Tenta encontrar no próprio contexto
    for pattern in patterns:
        match = re.search(pattern, contexto, re.IGNORECASE)
        if match:
            return int(match.group(1))
    
    # Se não encontrou, retorna None
    return None


def _extrair_clausula(contexto: str) -> str:
    """
    Tenta identificar a cláusula/item onde o valor foi encontrado.
    
    Procura por padrões como:
    - "Item 5.1"
    - "Cláusula 3.2"
    - "5.1.1"
    """
    patterns = [
        r'(?:item|cláusula|clausula|seção|secao|artigo)\s+([\d\.]+)',
        r'\b(\d+\.\d+(?:\.\d+)?)\b',  # Padrão numérico tipo 5.1 ou 5.1.1
    ]
    
    for pattern in patterns:
        match = re.search(pattern, contexto, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return None


def _normalizar_confianca(score: int) -> float:
    """
    Normaliza o score para uma confiança entre 0 e 1.
    
    Score típico varia de 0 a ~15-20.
    Mapeamos para escala 0-1 com saturação em score=15.
    """
    if score <= 0:
        return 0.0
    
    # Mapeia linearmente até score 15 = confiança 1.0
    # Scores maiores também ficam em 1.0
    return min(1.0, score / 15.0)


def _criar_candidato_escolhido(result, texto_completo: str = None) -> dict:
    """
    Cria o objeto candidato_escolhido com todos os detalhes.
    
    Args:
        result: ExtractResult do extractor
        texto_completo: Texto completo do documento (para extração de página)
    
    Returns:
        Dicionário com estrutura do candidato escolhido
    """
    if not result or not result.value:
        return None
    
    contexto = result.evidence[:500] if result.evidence else None
    
    candidato = {
        "valor": result.value,
        "score": result.score,
        "confianca": _normalizar_confianca(result.score),
        "contexto": contexto,
    }
    
    # Tenta extrair página
    if contexto:
        pagina = _extrair_numero_pagina(texto_completo or "", contexto)
        if pagina:
            candidato["pagina"] = pagina
    
    # Tenta extrair cláusula
    if contexto:
        clausula = _extrair_clausula(contexto)
        if clausula:
            candidato["clausula"] = clausula
    
    return candidato


def handle_extract_params(req: func.HttpRequest) -> func.HttpResponse:
    """
    Extrai parâmetros de um edital já parseado.

    Espera JSON: {"blob_name": "uploads/xxx.pdf"}

    O blob_name pode ser:
    - O PDF original (vai buscar o _parsed.json correspondente)
    - O arquivo _parsed.json diretamente

    Returns:
        JSON com parâmetros extraídos incluindo candidatos escolhidos
    """
    try:
        # Obtém blob_name do body
        try:
            body = req.get_json()
            blob_name = body.get("blob_name") if body else None
        except Exception:
            blob_name = None

        if not blob_name:
            return func.HttpResponse(
                json.dumps({"error": "Envie JSON: {\"blob_name\": \"arquivo.pdf\"}"}),
                status_code=400,
                mimetype="application/json"
            )

        # Importa extractors
        from govy.extractors import (
            extract_e001,
            extract_pg001,
            extract_o001,
            extract_l001_from_tables_norm,
            extract_l001,
        )

        # Importa Azure SDK
        from azure.storage.blob import BlobServiceClient

        # Configurações
        conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        container_name = os.environ.get("BLOB_CONTAINER_NAME", "editais-teste")

        if not conn_str:
            return func.HttpResponse(
                json.dumps({"error": "AZURE_STORAGE_CONNECTION_STRING não configurada"}),
                status_code=500,
                mimetype="application/json"
            )

        # Determina o nome do arquivo parsed
        if blob_name.endswith("_parsed.json"):
            parsed_blob_name = blob_name
        else:
            parsed_blob_name = blob_name.replace(".pdf", "_parsed.json")

        # Baixa o JSON parseado
        blob_service = BlobServiceClient.from_connection_string(conn_str)
        blob_client = blob_service.get_blob_client(
            container=container_name,
            blob=parsed_blob_name
        )

        try:
            parsed_data = json.loads(blob_client.download_blob().readall())
        except Exception as e:
            return func.HttpResponse(
                json.dumps({
                    "error": f"Arquivo parseado não encontrado: {parsed_blob_name}",
                    "hint": "Execute parse_layout primeiro",
                    "details": str(e)
                }),
                status_code=404,
                mimetype="application/json"
            )

        texto_completo = parsed_data.get("texto_completo", "")
        tables_norm = parsed_data.get("tables_norm", [])

        logger.info(f"Extraindo parâmetros de {blob_name} ({len(texto_completo)} chars)")

        # =================================================================
        # EXTRAÇÃO DOS PARÂMETROS
        # =================================================================

        parametros = {}

        # E001 - Prazo de Entrega
        try:
            result_e001 = extract_e001(texto_completo)
            candidato = _criar_candidato_escolhido(result_e001, texto_completo)
            
            parametros["e001"] = {
                "label": "Prazo de Entrega",
                "encontrado": result_e001.value is not None,
                "valor": result_e001.value,
                "score": result_e001.score,
                "evidencia": result_e001.evidence[:500] if result_e001.evidence else None
            }
            
            # 🆕 Adiciona candidato escolhido
            if candidato:
                parametros["e001"]["candidato_escolhido"] = candidato
                
        except Exception as e:
            logger.error(f"Erro em e001: {e}")
            parametros["e001"] = {
                "label": "Prazo de Entrega",
                "encontrado": False,
                "erro": str(e)
            }

        # PG001 - Prazo de Pagamento
        try:
            result_pg001 = extract_pg001(texto_completo)
            candidato = _criar_candidato_escolhido(result_pg001, texto_completo)
            
            parametros["pg001"] = {
                "label": "Prazo de Pagamento",
                "encontrado": result_pg001.value is not None,
                "valor": result_pg001.value,
                "score": result_pg001.score,
                "evidencia": result_pg001.evidence[:500] if result_pg001.evidence else None
            }
            
            # 🆕 Adiciona candidato escolhido
            if candidato:
                parametros["pg001"]["candidato_escolhido"] = candidato
                
        except Exception as e:
            logger.error(f"Erro em pg001: {e}")
            parametros["pg001"] = {
                "label": "Prazo de Pagamento",
                "encontrado": False,
                "erro": str(e)
            }

        # O001 - Objeto da Licitação
        try:
            result_o001 = extract_o001(texto_completo)
            candidato = _criar_candidato_escolhido(result_o001, texto_completo)
            
            parametros["o001"] = {
                "label": "Objeto da Licitação",
                "encontrado": result_o001.value is not None,
                "valor": result_o001.value,
                "score": result_o001.score,
                "evidencia": result_o001.evidence[:500] if result_o001.evidence else None
            }
            
            # 🆕 Adiciona candidato escolhido
            if candidato:
                parametros["o001"]["candidato_escolhido"] = candidato
                
        except Exception as e:
            logger.error(f"Erro em o001: {e}")
            parametros["o001"] = {
                "label": "Objeto da Licitação",
                "encontrado": False,
                "erro": str(e)
            }

        # L001 - Locais de Entrega
        # Tenta primeiro via tabelas, depois via texto
        try:
            result_l001 = None

            # Tenta extrair de tabelas primeiro (mais preciso)
            if tables_norm:
                result_l001 = extract_l001_from_tables_norm(tables_norm)

            # Se não encontrou em tabelas, tenta no texto
            if not result_l001 or not result_l001.values:
                result_l001 = extract_l001(texto_completo)

            candidato = _criar_candidato_escolhido(result_l001, texto_completo) if result_l001 else None

            parametros["l001"] = {
                "label": "Locais de Entrega",
                "encontrado": len(result_l001.values) > 0 if result_l001 else False,
                "valor": result_l001.values[0] if result_l001 and result_l001.values else None,
                "total_locais": len(result_l001.values) if result_l001 else 0,
                "score": result_l001.score if result_l001 else 0,
                "evidencia": result_l001.evidence[:500] if result_l001 and result_l001.evidence else None
            }
            
            # 🆕 Adiciona candidato escolhido
            if candidato:
                parametros["l001"]["candidato_escolhido"] = candidato
                
        except Exception as e:
            logger.error(f"Erro em l001: {e}")
            parametros["l001"] = {
                "label": "Locais de Entrega",
                "encontrado": False,
                "erro": str(e)
            }

        # =================================================================
        # RESPOSTA
        # =================================================================

        # Conta quantos parâmetros foram encontrados
        encontrados = sum(1 for p in parametros.values() if p.get("encontrado", False))

        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "blob_name": blob_name,
                "parametros": parametros,
                "resumo": {
                    "total_parametros": len(parametros),
                    "encontrados": encontrados,
                    "taxa_sucesso": f"{encontrados}/{len(parametros)}"
                }
            }, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        logger.exception("Erro no extract_params")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )