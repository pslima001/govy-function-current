# govy/copilot/_checklist_lookup.py
"""
Lookup de audit questions do checklist por check_id.
Ponte entre o copilot e o módulo govy.checklist.audit_questions.
"""
from typing import Optional


def get_audit_question_by_id(check_id: str) -> Optional[dict]:
    """
    Busca uma AuditQuestion pelo ID (ex.: 'PL-001', 'ED-003').

    Retorna dict com keys: id, stage_tag, pergunta, keywords_edital,
    keywords_ausencia, query_guia_tcu, severidade.
    Retorna None se não encontrar.
    """
    try:
        from govy.checklist.audit_questions import AUDIT_QUESTIONS
    except ImportError:
        return None

    for q in AUDIT_QUESTIONS:
        if q.id == check_id:
            return {
                "id": q.id,
                "stage_tag": q.stage_tag,
                "pergunta": q.pergunta,
                "keywords_edital": q.keywords_edital,
                "keywords_ausencia": q.keywords_ausencia,
                "query_guia_tcu": q.query_guia_tcu,
                "severidade": q.severidade,
            }

    return None
