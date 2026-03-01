import azure.functions as func

bp = func.Blueprint()


@bp.function_name(name="kb_index_upsert")
@bp.route(route="kb/index/upsert", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_index_upsert(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_index_upsert import main
    return main(req)


@bp.function_name(name="kb_search")
@bp.route(route="kb/search", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_search(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_search import main
    return main(req)


@bp.function_name(name="kb_effect_classify")
@bp.route(route="kb/effect/classify", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_effect_classify(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_effect_classify import main
    return main(req)


@bp.function_name(name="kb_juris_extract_all")
@bp.route(route="kb/juris/extract_all", methods=["POST", "OPTIONS"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_extract_all(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import main
    return main(req)


@bp.function_name(name="kb_juris_review_list")
@bp.route(route="kb/juris/review_queue", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_review_list(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import list_review_queue
    return list_review_queue(req)


@bp.function_name(name="kb_juris_review_get")
@bp.route(route="kb/juris/review_queue/{item_id}", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_review_get(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import get_review_item
    return get_review_item(req)


@bp.function_name(name="kb_juris_review_approve")
@bp.route(route="kb/juris/review_queue/{item_id}/approve", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_review_approve(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import approve_review_item
    return approve_review_item(req)


@bp.function_name(name="kb_juris_review_reject")
@bp.route(route="kb/juris/review_queue/{item_id}/reject", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_review_reject(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import reject_review_item
    return reject_review_item(req)


@bp.function_name(name="kb_juris_approved_list")
@bp.route(route="kb/juris/approved", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_approved_list(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import list_approved_items
    return list_approved_items(req)


@bp.function_name(name="kb_juris_blocked_list")
@bp.route(route="kb/juris/blocked", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_blocked_list(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import list_blocked_items
    return list_blocked_items(req)


@bp.function_name(name="kb_juris_rejected_list")
@bp.route(route="kb/juris/rejected", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_rejected_list(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import list_rejected_items
    return list_rejected_items(req)


@bp.function_name(name="kb_juris_stats")
@bp.route(route="kb/juris/stats", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_stats(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_extract import get_queue_stats
    return get_queue_stats(req)
