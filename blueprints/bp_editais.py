import azure.functions as func

bp = func.Blueprint()


@bp.function_name(name="upload_edital")
@bp.route(route="upload_edital", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def upload_edital(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.upload_edital import handle_upload_edital
    return handle_upload_edital(req)


@bp.function_name(name="parse_layout")
@bp.route(route="parse_layout", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.parse_layout import handle_parse_layout
    return handle_parse_layout(req)


@bp.function_name(name="extract_params")
@bp.route(route="extract_params", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_params(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.extract_params import handle_extract_params
    return handle_extract_params(req)


@bp.function_name(name="extract_params_amplos")
@bp.route(route="extract_params_amplos", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_params_amplos(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.extract_params_amplos import handle_extract_params_amplos
    return handle_extract_params_amplos(req)


@bp.function_name(name="extract_items")
@bp.route(route="extract_items", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_items(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.extract_items import handle_extract_items
    return handle_extract_items(req)


@bp.function_name(name="get_blob_url")
@bp.route(route="get_blob_url", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def get_blob_url(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.get_blob_url import handle_get_blob_url
    return handle_get_blob_url(req)


@bp.function_name(name="consult_llms")
@bp.route(route="consult_llms", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def consult_llms(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.consult_llms import handle_consult_llms
    return handle_consult_llms(req)
