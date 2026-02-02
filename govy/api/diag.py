import os
import json
import traceback
import azure.functions as func


def handle_diag(req: func.HttpRequest) -> func.HttpResponse:
    """
    Diagnóstico simples do ambiente:
      - verifica existência da pasta govy
      - testa imports principais (inclui doutrina)
      - mostra variáveis relevantes (sem expor segredos)
    """
    lines = []

    # Step 1: Imports básicos
    try:
        import govy  # noqa: F401
        lines.append("Step 1: Imports OK")
    except Exception as e:
        lines.append(f"Step 1: Imports FAILED: {type(e).__name__}: {e}")

    # Step 2: Container / env (só presença, sem valores)
    try:
        have_storage = bool(os.getenv("AZURE_STORAGE_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage"))
        lines.append(f"Step 2: Storage env present: {have_storage}")
    except Exception as e:
        lines.append(f"Step 2: Env check FAILED: {type(e).__name__}: {e}")

    # Step 3: Imports de endpoints principais (antigos)
    def _check_import(mod: str) -> str:
        try:
            __import__(mod)
            return "SUCCESS"
        except Exception as e:
            return f"FAILED: {type(e).__name__}: {e}"

    lines.append(f"IMPORT govy.api.diag: {_check_import('govy.api.diag')}")
    lines.append(f"IMPORT govy.api.upload_edital: {_check_import('govy.api.upload_edital')}")
    lines.append(f"IMPORT govy.api.parse_layout: {_check_import('govy.api.parse_layout')}")
    lines.append(f"IMPORT govy.api.extract_params: {_check_import('govy.api.extract_params')}")

    # Step 4: Imports de doutrina (novos)
    lines.append(f"IMPORT govy.api.upload_doctrine: {_check_import('govy.api.upload_doctrine')}")
    lines.append(f"IMPORT govy.api.upload_doctrine_b64: {_check_import('govy.api.upload_doctrine_b64')}")
    lines.append(f"IMPORT govy.api.ingest_doctrine: {_check_import('govy.api.ingest_doctrine')}")
    lines.append(f"IMPORT govy.doctrine.reader_docx: {_check_import('govy.doctrine.reader_docx')}")
    lines.append(f"IMPORT govy.doctrine.pipeline: {_check_import('govy.doctrine.pipeline')}")

    # Extra: presença de containers (nomes apenas)
    lines.append(f"DOCTRINE_CONTAINER_NAME set: {bool(os.getenv('DOCTRINE_CONTAINER_NAME'))}")
    lines.append(f"DOCTRINE_PROCESSED_CONTAINER_NAME set: {bool(os.getenv('DOCTRINE_PROCESSED_CONTAINER_NAME'))}")

    return func.HttpResponse("\n".join(lines), status_code=200, mimetype="text/plain")

