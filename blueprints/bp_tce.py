import json
import logging

import azure.functions as func

bp = func.Blueprint()


@bp.function_name(name="parse_tce_pdf")
@bp.queue_trigger(arg_name="msg", queue_name="parse-tce-queue", connection="AzureWebJobsStorage")
def parse_tce_pdf(msg: func.QueueMessage) -> None:
    msg_text = msg.get_body().decode("utf-8")
    logging.info(f"[parse-tce-queue] Recebida msg: {msg_text[:200]}")
    from govy.api.tce_queue_handler import handle_parse_tce_pdf
    result = handle_parse_tce_pdf(msg_text)
    status = result.get("status", "unknown")
    if status == "success":
        logging.info(f"[parse-tce-queue] OK: {result.get('blob_path')}")
    elif status in ("skipped", "terminal_skip"):
        logging.warning(f"[parse-tce-queue] Pulado: {result.get('blob_path')} - {result.get('reason', status)}")
    elif status == "error":
        logging.error(f"[parse-tce-queue] ERRO: {result.get('blob_path')} - {result.get('error')}")
        raise RuntimeError(f"parse_tce_pdf failed: {result.get('error')}")
    else:
        logging.warning(f"[parse-tce-queue] Status desconhecido '{status}': {result.get('blob_path')}")


@bp.function_name(name="enqueue_tce")
@bp.route(route="kb/juris/enqueue-tce", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def enqueue_tce(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json() if req.get_body() else {}
    except ValueError:
        body = {}
    from govy.api.tce_queue_handler import handle_enqueue_tce
    result = handle_enqueue_tce(body)
    msgs = result.get("messages", [])
    if msgs:
        import os
        from azure.storage.queue import QueueClient
        qc = QueueClient.from_connection_string(os.environ["AzureWebJobsStorage"], "parse-tce-queue")  # ALLOW_CONNECTION_STRING_OK
        try:
            qc.create_queue()
        except Exception:
            pass
        for m in msgs:
            qc.send_message(json.dumps(m, ensure_ascii=False))
        logging.info(f"[enqueue-tce] {len(msgs)} msgs enfileiradas via SDK")
    return func.HttpResponse(json.dumps(result, ensure_ascii=False), status_code=200, mimetype="application/json")
