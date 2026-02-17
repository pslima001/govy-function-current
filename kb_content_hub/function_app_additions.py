# ============================================================================
# KB CONTENT HUB - ADICIONAR AO function_app.py
# ============================================================================
# Copiar este trecho para o final do function_app.py (antes do último import)
# ============================================================================

# -----------------------------------------------------------------------------
# KB Juris Paste - Colar texto de jurisprudência
# -----------------------------------------------------------------------------
@app.function_name(name="kb_juris_paste")
@app.route(route="kb/juris/paste", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def kb_juris_paste(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_juris_paste import handle_kb_juris_paste
    return handle_kb_juris_paste(req)


# -----------------------------------------------------------------------------
# KB Content List - Listar conteúdos
# -----------------------------------------------------------------------------
@app.function_name(name="kb_content_list")
@app.route(route="kb/content/list", methods=["GET"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_list(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_content_admin import handle_kb_content_list
    return handle_kb_content_list(req)


# -----------------------------------------------------------------------------
# KB Content Approve - Aprovar e indexar
# -----------------------------------------------------------------------------
@app.function_name(name="kb_content_approve")
@app.route(route="kb/content/{id}/approve", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_approve(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_content_admin import handle_kb_content_approve
    return handle_kb_content_approve(req)


# -----------------------------------------------------------------------------
# KB Content Reject - Rejeitar
# -----------------------------------------------------------------------------
@app.function_name(name="kb_content_reject")
@app.route(route="kb/content/{id}/reject", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_reject(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_content_admin import handle_kb_content_reject
    return handle_kb_content_reject(req)


# -----------------------------------------------------------------------------
# KB Content Update - Atualizar metadados
# -----------------------------------------------------------------------------
@app.function_name(name="kb_content_update")
@app.route(route="kb/content/{id}/update", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_update(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_content_admin import handle_kb_content_update
    return handle_kb_content_update(req)


# -----------------------------------------------------------------------------
# KB Content Delete - Soft/Hard delete
# -----------------------------------------------------------------------------
@app.function_name(name="kb_content_delete")
@app.route(route="kb/content/{id}/delete", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def kb_content_delete(req: func.HttpRequest) -> func.HttpResponse:
    from govy.api.kb_content_admin import handle_kb_content_delete
    return handle_kb_content_delete(req)
