import azure.functions as func

bp = func.Blueprint()


@bp.function_name(name="api_juris_upload")
@bp.route(route="juris/upload", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def api_juris_upload(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.juris_upload import main
    return main(req)


@bp.function_name(name="api_juris_fichas")
@bp.route(route="juris/fichas", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def api_juris_fichas(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.juris_fichas import main
    return main(req)


@bp.function_name(name="api_juris_validar")
@bp.route(route="juris/validar", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def api_juris_validar(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.juris_validar import main
    return main(req)


@bp.function_name(name="api_juris_buscar")
@bp.route(route="juris/buscar", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def api_juris_buscar(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.juris_buscar import main
    return main(req)
