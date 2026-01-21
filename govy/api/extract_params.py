# govy/api/extract_params.py
"""
Handler para extracao de parametros de editais.
VERSAO 3.0 - Integra consulta a multiplas LLMs para consenso
Ultima atualizacao: 21/01/2026
"""
import os
import json
import logging
import re

import azure.functions as func

logger = logging.getLogger(__name__)


def _extrair_clausula(contexto: str) -> str:
    if not contexto:
        return None
    patterns = [
        r'(?:item|clausula|secao|artigo)\s+([\d\.]+)',
        r'\b(\d+\.\d+(?:\.\d+)?)\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, contexto, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _normalizar_confianca(score: int) -> float:
    if score <= 0:
        return 0.0
    return min(1.0, score / 15.0)


def _criar_candidato_escolhido(result, texto_completo: str = None) -> dict:
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
        clausula = _extrair_clausula(contexto)
        if clausula:
            candidato["clausula"] = clausula
    return candidato


def _criar_candidato_escolhido_lista(result, texto_completo: str = None) -> dict:
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
        clausula = _extrair_clausula(contexto)
        if clausula:
            candidato["clausula"] = clausula
    return candidato


def handle_extract_params(req: func.HttpRequest) -> func.HttpResponse:
    try:
        try:
            body = req.get_json()
            blob_name = body.get("blob_name") if body else None
            usar_llm = body.get("usar_llm", True) if body else True
        except Exception:
            blob_name = None
            usar_llm = True

        if not blob_name:
            return func.HttpResponse(
                json.dumps({"error": "Envie JSON: {\"blob_name\": \"arquivo.pdf\"}"}),
                status_code=400,
                mimetype="application/json"
            )

        from govy.extractors import (
            extract_e001,
            extract_e001_multi,
            extract_pg001,
            extract_pg001_multi,
            extract_o001,
            extract_o001_multi,
            extract_l001_from_tables_norm,
            extract_l001,
        )
        from govy.utils.multi_llm import consultar_llms, obter_api_keys
        from azure.storage.blob import BlobServiceClient

        conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        container_name = os.environ.get("BLOB_CONTAINER_NAME", "editais-teste")

        if not conn_str:
            return func.HttpResponse(
                json.dumps({"error": "AZURE_STORAGE_CONNECTION_STRING nao configurada"}),
                status_code=500,
                mimetype="application/json"
            )

        if blob_name.endswith("_parsed.json"):
            parsed_blob_name = blob_name
        else:
            parsed_blob_name = blob_name.replace(".pdf", "_parsed.json")

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
                    "error": f"Arquivo parseado nao encontrado: {parsed_blob_name}",
                    "hint": "Execute parse_layout primeiro",
                    "details": str(e)
                }),
                status_code=404,
                mimetype="application/json"
            )

        texto_completo = parsed_data.get("texto_completo", "")
        tables_norm = parsed_data.get("tables_norm", [])

        logger.info(f"Extraindo parametros de {blob_name} ({len(texto_completo)} chars)")

        api_keys = obter_api_keys() if usar_llm else {}
        parametros = {}

        # E001 - Prazo de Entrega
        try:
            result_e001 = extract_e001(texto_completo)
            candidatos_e001 = extract_e001_multi(texto_completo, max_candidatos=3)
            candidatos_list = [{"value": c.value, "score": c.score, "context": c.context} for c in candidatos_e001]

            valor_final = result_e001.value
            llm_result = None

            if usar_llm and candidatos_list:
                llm_result = consultar_llms("e001", candidatos_list, api_keys)
                if llm_result.valor_final:
                    valor_final = llm_result.valor_final

            parametros["e001"] = {
                "label": "Prazo de Entrega",
                "encontrado": valor_final is not None,
                "valor": valor_final,
                "score": result_e001.score,
                "evidencia": result_e001.evidence[:500] if result_e001.evidence else None,
                "candidatos": candidatos_list,
            }
            if llm_result:
                parametros["e001"]["llm_consenso"] = {
                    "vencedor": llm_result.candidato_vencedor,
                    "votos": llm_result.votos,
                    "confianca": llm_result.confianca_media,
                }

        except Exception as e:
            logger.error(f"Erro em e001: {e}")
            parametros["e001"] = {"label": "Prazo de Entrega", "encontrado": False, "erro": str(e)}

        # PG001 - Prazo de Pagamento
        try:
            result_pg001 = extract_pg001(texto_completo)
            candidatos_pg001 = extract_pg001_multi(texto_completo, max_candidatos=3)
            candidatos_list = [{"value": c.value, "score": c.score, "context": c.context} for c in candidatos_pg001]

            valor_final = result_pg001.value
            llm_result = None

            if usar_llm and candidatos_list:
                llm_result = consultar_llms("pg001", candidatos_list, api_keys)
                if llm_result.valor_final:
                    valor_final = llm_result.valor_final

            parametros["pg001"] = {
                "label": "Prazo de Pagamento",
                "encontrado": valor_final is not None,
                "valor": valor_final,
                "score": result_pg001.score,
                "evidencia": result_pg001.evidence[:500] if result_pg001.evidence else None,
                "candidatos": candidatos_list,
            }
            if llm_result:
                parametros["pg001"]["llm_consenso"] = {
                    "vencedor": llm_result.candidato_vencedor,
                    "votos": llm_result.votos,
                    "confianca": llm_result.confianca_media,
                }

        except Exception as e:
            logger.error(f"Erro em pg001: {e}")
            parametros["pg001"] = {"label": "Prazo de Pagamento", "encontrado": False, "erro": str(e)}

        # O001 - Objeto da Licitacao
        try:
            result_o001 = extract_o001(texto_completo)
            candidatos_o001 = extract_o001_multi(texto_completo, max_candidatos=3)
            candidatos_list = [{"value": c.value, "score": c.score, "context": c.context} for c in candidatos_o001]

            valor_final = result_o001.value
            llm_result = None

            if usar_llm and candidatos_list:
                llm_result = consultar_llms("o001", candidatos_list, api_keys)
                if llm_result.valor_final:
                    valor_final = llm_result.valor_final

            parametros["o001"] = {
                "label": "Objeto da Licitacao",
                "encontrado": valor_final is not None,
                "valor": valor_final,
                "score": result_o001.score,
                "evidencia": result_o001.evidence[:500] if result_o001.evidence else None,
                "candidatos": candidatos_list,
            }
            if llm_result:
                parametros["o001"]["llm_consenso"] = {
                    "vencedor": llm_result.candidato_vencedor,
                    "votos": llm_result.votos,
                    "confianca": llm_result.confianca_media,
                }

        except Exception as e:
            logger.error(f"Erro em o001: {e}")
            parametros["o001"] = {"label": "Objeto da Licitacao", "encontrado": False, "erro": str(e)}

        # L001 - Locais de Entrega (nao usa LLM, sao multiplos valores)
        try:
            result_l001 = None
            if tables_norm:
                result_l001 = extract_l001_from_tables_norm(tables_norm)
            if not result_l001 or not result_l001.values:
                result_l001 = extract_l001(texto_completo)

            candidato = _criar_candidato_escolhido_lista(result_l001, texto_completo) if result_l001 else None

            candidatos_l001 = []
            if result_l001 and result_l001.values:
                for valor in result_l001.values[:10]:
                    candidatos_l001.append({
                        "value": valor,
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
            parametros["l001"] = {"label": "Locais de Entrega", "encontrado": False, "erro": str(e)}

        encontrados = sum(1 for p in parametros.values() if p.get("encontrado", False))

        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "blob_name": blob_name,
                "usar_llm": usar_llm,
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