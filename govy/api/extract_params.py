# govy/api/extract_params.py
"""
Handler para extracao de parametros de editais.

Este handler usa os extractors em govy/extractors/ para extrair:
- e001: Prazo de Entrega
- pg001: Prazo de Pagamento
- o001: Objeto da Licitacao
- l001: Locais de Entrega

Ultima atualizacao: 20/01/2026
MODIFICADO: l001 candidatos agora vem das tabelas (nao do texto)
"""
import os
import json
import logging
import re

import azure.functions as func

logger = logging.getLogger(__name__)


def _extrair_numero_pagina(texto_completo: str, contexto: str) -> int:
    """
    Tenta identificar o numero da pagina onde o contexto foi encontrado.
    """
    patterns = [
        r'p[aá]gina\s+(\d+)',
        r'p[aá]g\.\s*(\d+)',
        r'fls?\.\s*(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, contexto, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def _extrair_clausula(contexto: str) -> str:
    """
    Tenta identificar a clausula/item onde o valor foi encontrado.
    """
    patterns = [
        r'(?:item|cl[aá]usula|clausula|se[cç][aã]o|secao|artigo)\s+([\d\.]+)',
        r'\b(\d+\.\d+(?:\.\d+)?)\b',
    ]

    for pattern in patterns:
        match = re.search(pattern, contexto, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def _normalizar_confianca(score: int) -> float:
    """
    Normaliza o score para uma confianca entre 0 e 1.
    """
    if score <= 0:
        return 0.0
    return min(1.0, score / 15.0)


def _criar_candidato_escolhido(result, texto_completo: str = None) -> dict:
    """
    Cria o objeto candidato_escolhido com todos os detalhes.

    Args:
        result: ExtractResult do extractor (com .value)
        texto_completo: Texto completo do documento

    Returns:
        Dicionario com estrutura do candidato escolhido
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

    if contexto:
        pagina = _extrair_numero_pagina(texto_completo or "", contexto)
        if pagina:
            candidato["pagina"] = pagina

    if contexto:
        clausula = _extrair_clausula(contexto)
        if clausula:
            candidato["clausula"] = clausula

    return candidato


def _criar_candidato_escolhido_lista(result, texto_completo: str = None) -> dict:
    """
    Cria o objeto candidato_escolhido para ExtractResultList (l001).

    Args:
        result: ExtractResultList do extractor (com .values - lista)
        texto_completo: Texto completo do documento

    Returns:
        Dicionario com estrutura do candidato escolhido
    """
    if not result or not result.values:
        return None

    valor_principal = result.values[0] if result.values else None
    contexto = result.evidence[:500] if result.evidence else None

    candidato = {
        "valor": valor_principal,
        "todos_valores": result.values,
        "total": len(result.values),
        "score": result.score,
        "confianca": _normalizar_confianca(result.score),
        "contexto": contexto,
    }

    if contexto:
        pagina = _extrair_numero_pagina(texto_completo or "", contexto)
        if pagina:
            candidato["pagina"] = pagina

    if contexto:
        clausula = _extrair_clausula(contexto)
        if clausula:
            candidato["clausula"] = clausula

    return candidato


def handle_extract_params(req: func.HttpRequest) -> func.HttpResponse:
    """
    Extrai parametros de um edital ja parseado.

    Espera JSON: {"blob_name": "uploads/xxx.pdf"}

    Returns:
        JSON com parametros extraidos incluindo candidatos escolhidos
    """
    try:
        # Obtem blob_name do body
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
        from govy.extractors.e001_entrega import extract_e001_multi
        from govy.extractors.pg001_pagamento import extract_pg001_multi
        from govy.extractors.o001_objeto import extract_o001_multi

        # Importa Azure SDK
        from govy.utils.azure_clients import get_blob_service_client

        # Configuracoes
        container_name = os.environ.get("BLOB_CONTAINER_NAME", "editais-teste")

        # Determina o nome do arquivo parsed
        if blob_name.endswith("_parsed.json"):
            parsed_blob_name = blob_name
        else:
            parsed_blob_name = blob_name.replace(".pdf", "_parsed.json")

        # Baixa o JSON parseado
        blob_service = get_blob_service_client()
        blob_client = blob_service.get_blob_client(
            container=container_name,
            blob=parsed_blob_name
        )

        try:
            parsed_data = json.loads(blob_client.download_blob().readall())
        except Exception as e:
            logger.info(f"Arquivo parseado nao encontrado, executando parse_layout automaticamente...")
            try:
                from govy.api.parse_layout import handle_parse_layout
                
                class FakeRequest:
                    def get_json(self):
                        return {"blob_name": blob_name}
                
                parse_result = handle_parse_layout(FakeRequest())
                
                if parse_result.status_code != 200:
                    return func.HttpResponse(
                        json.dumps({
                            "error": "Falha ao parsear documento automaticamente",
                            "details": parse_result.get_body().decode()
                        }),
                        status_code=500,
                        mimetype="application/json"
                    )
                
                parsed_data = json.loads(blob_client.download_blob().readall())
                logger.info("Parse automatico concluido com sucesso")
                
            except Exception as parse_error:
                return func.HttpResponse(
                    json.dumps({
                        "error": "Arquivo parseado nao encontrado e falha no parse automatico",
                        "hint": "Verifique se o PDF foi enviado corretamente",
                        "details": str(parse_error)
                    }),
                    status_code=500,
                    mimetype="application/json"
                )

        texto_completo = parsed_data.get("texto_completo", "")
        tables_norm = parsed_data.get("tables_norm", [])

        logger.info(f"Extraindo parametros de {blob_name} ({len(texto_completo)} chars)")

        # =================================================================
        # EXTRACAO DOS PARAMETROS
        # =================================================================

        parametros = {}

        # E001 - Prazo de Entrega
        try:
            result_e001 = extract_e001(texto_completo)
            candidato = _criar_candidato_escolhido(result_e001, texto_completo)
            candidatos_e001 = extract_e001_multi(texto_completo, max_candidatos=3)

            parametros["e001"] = {
                "label": "Prazo de Entrega",
                "encontrado": result_e001.value is not None,
                "valor": result_e001.value,
                "score": result_e001.score,
                "evidencia": result_e001.evidence[:500] if result_e001.evidence else None,
                "candidatos": [
                    {"valor": c.value, "score": c.score, "context": c.context}
                    for c in candidatos_e001
                ]
            }

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
            candidatos_pg001 = extract_pg001_multi(texto_completo, max_candidatos=3)

            parametros["pg001"] = {
                "label": "Prazo de Pagamento",
                "encontrado": result_pg001.value is not None,
                "valor": result_pg001.value,
                "score": result_pg001.score,
                "evidencia": result_pg001.evidence[:500] if result_pg001.evidence else None,
                "candidatos": [
                    {"valor": c.value, "score": c.score, "context": c.context}
                    for c in candidatos_pg001
                ]
            }

            if candidato:
                parametros["pg001"]["candidato_escolhido"] = candidato

        except Exception as e:
            logger.error(f"Erro em pg001: {e}")
            parametros["pg001"] = {
                "label": "Prazo de Pagamento",
                "encontrado": False,
                "erro": str(e)
            }

        # O001 - Objeto da Licitacao
        try:
            result_o001 = extract_o001(texto_completo)
            candidato = _criar_candidato_escolhido(result_o001, texto_completo)
            candidatos_o001 = extract_o001_multi(texto_completo, max_candidatos=3)

            parametros["o001"] = {
                "label": "Objeto da Licitacao",
                "encontrado": result_o001.value is not None,
                "valor": result_o001.value,
                "score": result_o001.score,
                "evidencia": result_o001.evidence[:500] if result_o001.evidence else None,
                "candidatos": [
                    {"valor": c.value, "score": c.score, "context": c.context}
                    for c in candidatos_o001
                ]
            }

            if candidato:
                parametros["o001"]["candidato_escolhido"] = candidato

        except Exception as e:
            logger.error(f"Erro em o001: {e}")
            parametros["o001"] = {
                "label": "Objeto da Licitacao",
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

            # Se nao encontrou em tabelas, tenta no texto
            if not result_l001 or not result_l001.values:
                result_l001 = extract_l001(texto_completo)

            # Cria candidato escolhido para lista
            candidato = _criar_candidato_escolhido_lista(result_l001, texto_completo) if result_l001 else None

            # Para l001, os candidatos sao os proprios valores extraidos das tabelas
            # (limitamos a 10 para nao sobrecarregar a UI)
            candidatos_l001 = []
            if result_l001 and result_l001.values:
                for valor in result_l001.values[:10]:
                    candidatos_l001.append({
                        "valor": valor,
                        "score": result_l001.score,
                        "context": valor
                    })

            parametros["l001"] = {
                "label": "Locais de Entrega",
                "encontrado": len(result_l001.values) > 0 if result_l001 else False,
                "valor": result_l001.values[0] if result_l001 and result_l001.values else None,
                "total_locais": len(result_l001.values) if result_l001 else 0,
                "score": result_l001.score if result_l001 else 0,
                "evidencia": result_l001.evidence[:500] if result_l001 and result_l001.evidence else None,
                "candidatos": candidatos_l001
            }

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
