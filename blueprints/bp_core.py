import json
import sys
import typing
from pathlib import Path

import azure.functions as func

bp = func.Blueprint()


@bp.function_name(name="ping")
@bp.route(route="ping", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def ping(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("pong", status_code=200)


@bp.function_name(name="diag")
@bp.route(route="diag", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def diag(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.diag import handle_diag
    return handle_diag(req)


@bp.function_name(name="dicionario")
@bp.route(route="dicionario", methods=["GET", "POST", "DELETE"], auth_level=func.AuthLevel.FUNCTION)
def dicionario(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.dicionario_api import handle_dicionario
    return handle_dicionario(req)


@bp.function_name(name="diagnostic_full")
@bp.route(route="diagnostic_full", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def diagnostic_full(req: func.HttpRequest) -> func.HttpResponse:
    """Endpoint de diagnostico completo para troubleshooting"""
    import os

    d: typing.Dict[str, typing.Any] = {}

    d["python_version"] = sys.version
    d["sys_path"] = sys.path
    d["cwd"] = os.getcwd()

    wwwroot = "/home/site/wwwroot"
    d["wwwroot_exists"] = os.path.exists(wwwroot)
    if os.path.exists(wwwroot):
        try:
            d["wwwroot_contents"] = os.listdir(wwwroot)
        except Exception as e:
            d["wwwroot_contents"] = f"ERROR: {str(e)}"

    govy_path = os.path.join(wwwroot, "govy")
    d["govy_exists"] = os.path.exists(govy_path)

    if os.path.exists(govy_path):
        try:
            d["govy_contents"] = os.listdir(govy_path)

            govy_api = os.path.join(govy_path, "api")
            govy_doctrine = os.path.join(govy_path, "doctrine")

            d["govy_api_exists"] = os.path.exists(govy_api)
            if os.path.exists(govy_api):
                d["govy_api_files"] = os.listdir(govy_api)[:50]

            d["govy_doctrine_exists"] = os.path.exists(govy_doctrine)
            if os.path.exists(govy_doctrine):
                d["govy_doctrine_files"] = os.listdir(govy_doctrine)[:50]
        except Exception as e:
            d["govy_error"] = str(e)

    init_files = []
    for init_path in [
        os.path.join(wwwroot, "govy", "__init__.py"),
        os.path.join(wwwroot, "govy", "api", "__init__.py"),
        os.path.join(wwwroot, "govy", "doctrine", "__init__.py"),
    ]:
        init_files.append({"path": init_path.replace(wwwroot, ""), "exists": os.path.exists(init_path)})
    d["init_files"] = init_files

    import_tests = {}
    try:
        import govy as govy_module  # noqa: F401
        import_tests["import_govy"] = "OK"
    except Exception as e:
        import_tests["import_govy"] = f"FAILED: {str(e)}"

    try:
        from govy.api.ingest_doctrine import handle_ingest_doctrine  # noqa: F401
        import_tests["import_ingest_doctrine"] = "OK"
    except Exception as e:
        import_tests["import_ingest_doctrine"] = f"FAILED: {str(e)}"

    try:
        from govy.doctrine import pipeline  # noqa: F401
        import_tests["import_pipeline"] = "OK"
    except Exception as e:
        import_tests["import_pipeline"] = f"FAILED: {str(e)}"

    d["import_tests"] = import_tests

    return func.HttpResponse(
        body=json.dumps(d, indent=2, ensure_ascii=False),
        mimetype="application/json",
        status_code=200,
    )
