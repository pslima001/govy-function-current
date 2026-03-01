# govy/copilot/bi_request_store.py
"""
Persistência de BiRequestDraft em Azure Blob Storage.

Path padrão: kb-content/bi/requests/YYYY-MM-DD/{request_id}.json
Idempotente: mesmo request_id = mesmo blob (overwrite).
"""
import json
import logging
from typing import Optional

from govy.copilot.contracts import BiRequestDraft

logger = logging.getLogger(__name__)

CONTAINER_NAME = "kb-content"
BLOB_PREFIX = "bi/requests"


def _build_blob_path(draft: BiRequestDraft) -> str:
    """Gera path: bi/requests/YYYY-MM-DD/{request_id}.json"""
    date_part = draft.created_at_utc[:10]  # YYYY-MM-DD
    return f"{BLOB_PREFIX}/{date_part}/{draft.request_id}.json"


def store_bi_request_draft(draft: BiRequestDraft) -> Optional[str]:
    """
    Persiste o draft em Blob Storage.

    Returns:
        blob_path se sucesso, None se falha.
    """
    blob_path = _build_blob_path(draft)
    payload = json.dumps(draft.to_dict(), ensure_ascii=False, indent=2)

    try:
        from govy.utils.azure_clients import get_container_client

        container = get_container_client(CONTAINER_NAME)
        blob = container.get_blob_client(blob_path)
        blob.upload_blob(payload, overwrite=True, content_settings=_json_content_settings())
        logger.info(f"bi_request_draft persistido: {CONTAINER_NAME}/{blob_path}")
        return f"{CONTAINER_NAME}/{blob_path}"
    except Exception as e:
        logger.error(f"Falha ao persistir bi_request_draft: {e}")
        return None


def _json_content_settings():
    """Content settings para blob JSON."""
    from azure.storage.blob import ContentSettings
    return ContentSettings(content_type="application/json; charset=utf-8")
