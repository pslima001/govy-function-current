import json

import azure.functions as func

bp = func.Blueprint()


@bp.function_name(name="upload_doctrine")
@bp.route(route="upload_doctrine", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_doctrine(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.upload_doctrine import handle_upload_doctrine
    return handle_upload_doctrine(req)


@bp.function_name(name="upload_doctrine_b64")
@bp.route(route="upload_doctrine_b64", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_doctrine_b64(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.upload_doctrine_b64 import handle_upload_doctrine_b64
    return handle_upload_doctrine_b64(req)


@bp.function_name(name="ingest_doctrine")
@bp.route(route="ingest_doctrine", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def ingest_doctrine(req: func.HttpRequest) -> func.HttpResponse:
    try:
        from govy.api.ingest_doctrine import handle_ingest_doctrine
        return handle_ingest_doctrine(req)
    except Exception as e:
        import traceback
        return func.HttpResponse(
            json.dumps(
                {"error": "ingest_doctrine failed", "details": str(e), "traceback": traceback.format_exc()},
                ensure_ascii=False,
            ),
            status_code=500,
            mimetype="application/json",
        )
