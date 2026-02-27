import json
import logging

import azure.functions as func

bp = func.Blueprint()


@bp.function_name(name="legal_watch_timer")
@bp.timer_trigger(arg_name="timer", schedule="0 0 6 * * *")
def legal_watch_timer(timer: func.TimerRequest) -> None:
    """Monitora listas gov.br/compras diariamente, detecta mudancas e ingere novos normativos."""
    from govy.legal.watch_runner import watch_govbr_all
    result = watch_govbr_all(skip_recent_hours=20)
    logging.info(
        "legal_watch_timer: %d novos, %d erros, %d listas processadas",
        result["total_new"],
        result["total_errors"],
        len(result["all_stats"]),
    )


@bp.function_name(name="legal_watch_run")
@bp.route(route="legal/watch/run", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def legal_watch_run(req: func.HttpRequest) -> func.HttpResponse:
    """
    Dispara watch de uma lista especifica gov.br/compras.
    Ideal para seed inicial (1 lista por chamada, sem timeout).

    Body JSON:
        list_url_filter: str  (obrigatorio) - URL ou trecho da URL da lista
        limit: int            (opcional, default=0=todos)
        dry_run: bool         (opcional, default=false)
        skip_ingest: bool     (opcional, default=false)

    Exemplo:
        {"list_url_filter": "instrucoes-normativas", "limit": 0}
    """
    from govy.legal.watch_runner import watch_govbr_all

    try:
        body = req.get_json() if req.get_body() else {}
    except ValueError:
        body = {}

    list_url_filter = body.get("list_url_filter")
    if not list_url_filter:
        return func.HttpResponse(
            json.dumps({"error": "list_url_filter obrigatorio"}, ensure_ascii=False),
            status_code=400,
            mimetype="application/json",
        )

    limit = body.get("limit", 0)
    dry_run = body.get("dry_run", False)
    skip_ingest = body.get("skip_ingest", False)

    logging.info(
        "legal_watch_run: filter=%s, limit=%d, dry_run=%s",
        list_url_filter, limit, dry_run,
    )

    try:
        result = watch_govbr_all(
            list_url_filter=list_url_filter,
            limit=limit,
            dry_run=dry_run,
            skip_ingest=skip_ingest,
        )
    except ValueError as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}, ensure_ascii=False),
            status_code=404,
            mimetype="application/json",
        )

    response = {
        "total_new": result["total_new"],
        "total_errors": result["total_errors"],
        "timestamp": result["timestamp"],
        "lists": [
            {
                "url": s["list_url"],
                "kind": s["kind"],
                "status_hint": s["status_hint"],
                "total_items": s["total_items"],
                "new": s["new"],
                "updated": s["updated"],
                "skipped": s["skipped"],
                "errors": s["errors"],
            }
            for s in result["all_stats"]
        ],
    }

    return func.HttpResponse(
        json.dumps(response, ensure_ascii=False, indent=2),
        status_code=200,
        mimetype="application/json",
    )
