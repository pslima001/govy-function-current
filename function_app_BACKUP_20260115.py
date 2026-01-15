import sys
import os
import json
import traceback
import re
import azure.functions as func

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

app = func.FunctionApp()

@app.function_name(name="ping")
@app.route(route="ping", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def ping(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("pong", status_code=200)


@app.function_name(name="extract_params")
@app.route(route="extract_params", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_params(req: func.HttpRequest) -> func.HttpResponse:
    """
    Handler REAL para extração de parâmetros de editais.
    Implementado por ChatGPT 5.2 - 14/01/2026
    CORRIGIDO: 14/01/2026 - 21:00 (3 bugs críticos)
    DEBUG: 14/01/2026 - 22:30 (adicionado retorno de texto)
    """
    try:
        # Imports dentro da função (conforme especificado)
        from azure.storage.blob import BlobServiceClient
        from azure.ai.documentintelligence import DocumentIntelligenceClient
        from azure.core.credentials import AzureKeyCredential

        # =========================
        # 1. Validar request
        # =========================
        try:
            body = req.get_json()
        except Exception:
            body = None

        blob_name = body.get("blob_name") if isinstance(body, dict) else None
        if not blob_name:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "error": "blob_name is required",
                    "blob_name": None
                }),
                status_code=400,
                mimetype="application/json"
            )

        # =========================
        # 2. Download do PDF
        # =========================
        conn_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        container_name = os.getenv("BLOB_CONTAINER_NAME", "editais-teste")

        if not conn_str:
            raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING not set")

        blob_service = BlobServiceClient.from_connection_string(conn_str)
        container_client = blob_service.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)

        try:
            pdf_bytes = blob_client.download_blob().readall()
        except Exception:
            return func.HttpResponse(
                json.dumps({
                    "status": "error",
                    "error": f"Blob not found: {blob_name}",
                    "blob_name": blob_name
                }),
                status_code=404,
                mimetype="application/json"
            )

        # =========================
        # 3. Extração de texto (Document Intelligence)
        # =========================
        di_endpoint = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT")
        di_key = os.getenv("DOCUMENT_INTELLIGENCE_KEY")

        if not di_endpoint or not di_key:
            raise RuntimeError("DOCUMENT_INTELLIGENCE_ENDPOINT or KEY not set")

        di_client = DocumentIntelligenceClient(
            endpoint=di_endpoint,
            credential=AzureKeyCredential(di_key)
        )

        poller = di_client.begin_analyze_document(
            "prebuilt-read",
            pdf_bytes
        )
        result = poller.result(timeout=180)

        # ✅ CORREÇÃO 1: EXTRAÇÃO ROBUSTA DE TEXTO
        chunks = []

        if hasattr(result, "pages"):
            for page in result.pages:
                for line in page.lines:
                    if line.content:
                        chunks.append(line.content)

        if not chunks and hasattr(result, "paragraphs"):
            for p in result.paragraphs:
                if p.content:
                    chunks.append(p.content)

        texto = "\n".join(chunks)

        # DEBUG: Ver texto extraído
        print("=== DEBUG TEXTO EXTRAÍDO (PRIMEIROS 3000 CHARS) ===")
        print(texto[:3000])
        print("=== DEBUG TEXTO EXTRAÍDO (FIM) ===")
        
        # DEBUG: Verificar se texto está vazio
        if len(texto) < 100:
            import logging
            logging.error(f"ALERTA: TEXTO MUITO CURTO! Apenas {len(texto)} caracteres extraídos")

        # =========================
        # 4. Carregar patterns.json
        # =========================
        patterns_path = os.path.join(ROOT, "patterns.json")

        with open(patterns_path, "r", encoding="utf-8") as f:
            patterns = json.load(f)

        # =========================
        # 5. Função de extração CORRIGIDA
        # =========================
        def extrair_parametro(texto: str, config: dict) -> dict:
            score_base = 0.0
            melhor_match = None
            melhor_contexto = None
            melhor_score = 0.0

            texto_lower = texto.lower()
            
            # ✅ CORREÇÃO 2: NORMALIZAR TEXTO
            texto_norm = re.sub(r"\s+", " ", texto)

            # Contexto global
            for termo in config.get("termos_positivos", []):
                if termo.lower() in texto_lower:
                    score_base += config.get("peso_contexto_positivo", 0)

            for termo in config.get("termos_negativos", []):
                if termo.lower() in texto_lower:
                    score_base += config.get("peso_contexto_negativo", 0)

            # Regex
            for pattern in config.get("regex_patterns", []):
                # ✅ CORREÇÃO 3: USAR re.DOTALL
                for match in re.finditer(pattern, texto_norm, re.IGNORECASE | re.DOTALL):
                    valor = match.group(1) if match.lastindex else match.group(0)

                    start = max(0, match.start() - 60)
                    end = min(len(texto_norm), match.end() + 60)
                    contexto = texto_norm[start:end].strip()

                    if len(contexto) > 200:
                        contexto = contexto[:200] + "..."

                    # ✅ CORREÇÃO 4: BÔNUS POR REGEX MATCH
                    score_local = score_base + 5.0

                    # Sinônimos
                    for _, sinonimos in config.get("sinonimos", {}).items():
                        for s in sinonimos:
                            if s.lower() in contexto.lower():
                                score_local += config.get("peso_sinonimo", 0)

                    if melhor_match is None or score_local > melhor_score:
                        melhor_match = valor
                        melhor_contexto = contexto
                        melhor_score = score_local

            confianca = min(1.0, max(0.0, melhor_score / 10.0))

            return {
                "encontrado": melhor_match is not None,
                "valor": melhor_match,
                "confianca": confianca if melhor_match else 0.0,
                "contexto": melhor_contexto
            }

        # =========================
        # 6. Aplicar extractors
        # =========================
        parametros = {}
        for pid in ["e001", "pg001", "o001", "l001"]:
            cfg = patterns.get(pid)
            if not cfg:
                parametros[pid] = {
                    "encontrado": False,
                    "valor": None,
                    "confianca": 0.0,
                    "contexto": None
                }
            else:
                parametros[pid] = extrair_parametro(texto, cfg)

        # =========================
        # 7. Response final COM DEBUG
        # =========================
        return func.HttpResponse(
            json.dumps({
                "status": "success",
                "blob_name": blob_name,
                "parametros": parametros,
                "debug_info": {
                    "texto_length": len(texto),
                    "texto_preview": texto[:1000] if texto else "(vazio)",
                    "chunks_count": len(chunks),
                    "has_pages": hasattr(result, "pages"),
                    "has_paragraphs": hasattr(result, "paragraphs")
                }
            }, ensure_ascii=False),
            status_code=200,
            mimetype="application/json"
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }),
            status_code=500,
            mimetype="application/json"
        )


@app.function_name(name="parse_layout")
@app.route(route="parse_layout", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "stub_ok", "function": "parse_layout"}),
        status_code=200,
        mimetype="application/json"
    )


@app.function_name(name="upload_edital")
@app.route(route="upload_edital", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "stub_ok", "function": "upload_edital"}),
        status_code=200,
        mimetype="application/json"
    )