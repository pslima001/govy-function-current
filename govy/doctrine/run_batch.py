from __future__ import annotations
import json
import logging
import os
from typing import Dict, Any
from azure.storage.blob import BlobServiceClient
from govy.doctrine.pipeline import DoctrineIngestRequest, ingest_doctrine_process_once

logger = logging.getLogger(__name__)

def _load_manifest(path: str) -> Dict[str, Any]:
    """Manifest opcional com metadados por arquivo."""
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _merge_meta(defaults: Dict[str, Any], file_meta: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(defaults or {})
    out.update(file_meta or {})
    return out

def main() -> None:
    logging.basicConfig(level=logging.INFO)
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    if not conn:
        raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING não configurada")
    container_source = os.getenv("DOCTRINE_CONTAINER_SOURCE", "doutrina")
    container_processed = os.getenv("DOCTRINE_CONTAINER_PROCESSED", "doutrina-processed")
    manifest_path = os.getenv("DOCTRINE_MANIFEST_JSON", "")
    force_reprocess = os.getenv("DOCTRINE_FORCE_REPROCESS", "false").lower() == "true"
    blob_service = BlobServiceClient.from_connection_string(conn)
    manifest = _load_manifest(manifest_path)
    defaults = manifest.get("default", {})
    file_map = manifest.get("files", {})
    src_container = blob_service.get_container_client(container_source)
    blobs = [b.name for b in src_container.list_blobs() if b.name.lower().endswith(".docx")]
    logger.info(f"Encontrados {len(blobs)} DOCX em container {container_source}")
    ok = 0
    skipped = 0
    fail = 0
    for blob_name in blobs:
        meta = _merge_meta(defaults, file_map.get(blob_name, {}))
        req = DoctrineIngestRequest(
            blob_name=blob_name,
            etapa_processo=str(meta.get("etapa_processo", "habilitacao")),
            tema_principal=str(meta.get("tema_principal", "habilitacao")),
            autor=str(meta.get("autor", "")),
            obra=str(meta.get("obra", "")),
            edicao=str(meta.get("edicao", "")),
            ano=int(meta.get("ano", 0) or 0),
            capitulo=str(meta.get("capitulo", "")),
            secao=str(meta.get("secao", "")),
            force_reprocess=force_reprocess,
        )
        try:
            res = ingest_doctrine_process_once(
                blob_service=blob_service,
                container_source=container_source,
                container_processed=container_processed,
                req=req,
            )
            if res.get("status") == "already_processed":
                skipped += 1
            else:
                ok += 1
        except Exception as e:
            logger.error(f"Falha ao processar {blob_name}: {e}")
            fail += 1
    logger.info(f"Batch finalizado. processed={ok} already_processed={skipped} failed={fail}")

if __name__ == "__main__":
    main()
