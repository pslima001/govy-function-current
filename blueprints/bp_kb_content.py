import azure.functions as func
from govy.api.cors import cors_preflight, cors_headers

bp = func.Blueprint()


@bp.function_name(name="kb_juris_paste")
@bp.route(route="kb/juris/paste", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_paste(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_juris_paste import handle_kb_juris_paste
    resp = handle_kb_juris_paste(req)
    resp.headers.update(cors_headers(req))
    return resp


@bp.function_name(name="kb_content_list")
@bp.route(route="kb/content/list", methods=["GET", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_list(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_list
    resp = handle_kb_content_list(req)
    resp.headers.update(cors_headers(req))
    return resp


@bp.function_name(name="kb_content_paste")
@bp.route(route="kb/content/paste", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_paste(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_paste
    resp = handle_kb_content_paste(req)
    resp.headers.update(cors_headers(req))
    return resp


@bp.function_name(name="kb_content_approve")
@bp.route(route="kb/content/{id}/approve", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_approve(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_approve
    resp = handle_kb_content_approve(req)
    resp.headers.update(cors_headers(req))
    return resp


@bp.function_name(name="kb_content_reject")
@bp.route(route="kb/content/{id}/reject", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_reject(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_reject
    resp = handle_kb_content_reject(req)
    resp.headers.update(cors_headers(req))
    return resp


@bp.function_name(name="kb_content_update")
@bp.route(route="kb/content/{id}/update", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_update(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_update
    resp = handle_kb_content_update(req)
    resp.headers.update(cors_headers(req))
    return resp


@bp.function_name(name="kb_content_delete")
@bp.route(route="kb/content/{id}/delete", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_delete(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_delete
    resp = handle_kb_content_delete(req)
    resp.headers.update(cors_headers(req))
    return resp


@bp.function_name(name="kb_content_restore")
@bp.route(route="kb/content/{id}/restore", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_restore(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return cors_preflight(req)
    from govy.api.kb_content_admin import handle_kb_content_restore
    resp = handle_kb_content_restore(req)
    resp.headers.update(cors_headers(req))
    return resp
