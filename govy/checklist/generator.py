"""
GOVY Checklist — Gerador determinístico de checklist para análise de edital
============================================================================
Lê texto de edital/TR, aplica audit_questions (keyword match) e busca
referências no guia_tcu para produzir um ChecklistResult JSON.

Sem LLM. Toda lógica é determinística: keyword search + retriever.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import List, Optional

from govy.checklist.audit_questions import AUDIT_QUESTIONS, AuditQuestion
from govy.checklist.models import (
    CheckItem,
    ChecklistResult,
    GuiaTcuRef,
    SINALIZACAO_OK,
    SINALIZACAO_ATENCAO,
    SINALIZACAO_NAO_CONFORME,
    SINALIZACAO_NAO_IDENTIFICADO,
)

logger = logging.getLogger(__name__)

# Context window around keyword match (chars before/after)
_SNIPPET_CONTEXT = 200
_MIN_TEXT_LENGTH = 50  # Edital texts shorter than this are rejected


def _normalize_text(text: str) -> str:
    """Lowercase + collapse whitespace for keyword matching."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _find_keyword_snippet(
    text_lower: str, text_original: str, keywords: List[str]
) -> Optional[str]:
    """Find first keyword match in text and return surrounding snippet."""
    for kw in keywords:
        kw_lower = kw.lower()
        pos = text_lower.find(kw_lower)
        if pos >= 0:
            start = max(0, pos - _SNIPPET_CONTEXT)
            end = min(len(text_original), pos + len(kw) + _SNIPPET_CONTEXT)
            snippet = text_original[start:end].strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(text_original):
                snippet = snippet + "..."
            return snippet
    return None


def _classify_sinalizacao(
    keyword_found: bool,
    keywords_ausencia: List[str],
    text_lower: str,
) -> str:
    """
    Deterministic classification:
    - keyword found → OK
    - keyword NOT found but keywords_ausencia present → depends on ausencia match
    - keyword NOT found, no ausencia keywords → Não identificado
    """
    if keyword_found:
        return SINALIZACAO_OK

    if keywords_ausencia:
        for kw in keywords_ausencia:
            if kw.lower() in text_lower:
                return SINALIZACAO_NAO_CONFORME
        return SINALIZACAO_NAO_IDENTIFICADO

    return SINALIZACAO_NAO_IDENTIFICADO


def _retrieve_guia_ref(
    query: str, stage_tag: str, use_retriever: bool = True
) -> GuiaTcuRef:
    """Call the guia_tcu retriever and return the best match as GuiaTcuRef."""
    if not use_retriever:
        return GuiaTcuRef(
            section_id="",
            section_title="(retriever desabilitado)",
            source_url="",
            score=0.0,
        )
    try:
        from govy.utils.retrieve_guia_tcu import retrieve_guia_tcu

        results = retrieve_guia_tcu(query, stage_tag=stage_tag, top_k=3)
        if results:
            best = results[0]
            return GuiaTcuRef(
                section_id=best.section_id,
                section_title=best.section_title,
                source_url=best.source_url,
                score=best.score,
            )
    except Exception as e:
        logger.warning(f"Retriever failed for query '{query[:50]}': {e}")

    return GuiaTcuRef(
        section_id="",
        section_title="(sem referência encontrada)",
        source_url="",
        score=0.0,
    )


def generate_checklist(
    edital_text: str,
    arquivo_nome: str = "edital.pdf",
    use_retriever: bool = True,
    questions: Optional[List[AuditQuestion]] = None,
) -> ChecklistResult:
    """
    Generate a deterministic checklist from edital text.

    Args:
        edital_text: Full text of the edital/TR.
        arquivo_nome: Name of the analyzed file (for the report).
        use_retriever: If True, calls retrieve_guia_tcu for each check.
        questions: Override questions list (default: AUDIT_QUESTIONS).

    Returns:
        ChecklistResult with all checks populated.
    """
    if len(edital_text.strip()) < _MIN_TEXT_LENGTH:
        raise ValueError(
            f"Texto do edital muito curto ({len(edital_text)} chars). "
            f"Mínimo: {_MIN_TEXT_LENGTH} chars."
        )

    text_lower = _normalize_text(edital_text)
    qs = questions or AUDIT_QUESTIONS
    run_id = str(uuid.uuid4())[:8]

    checks: List[CheckItem] = []
    stage_dist: dict = {}
    sinal_dist: dict = {}

    for q in qs:
        # 1. Keyword search in edital
        snippet = _find_keyword_snippet(text_lower, edital_text, q.keywords_edital)
        keyword_found = snippet is not None

        # 2. Classification
        sinalizacao = _classify_sinalizacao(
            keyword_found, q.keywords_ausencia, text_lower
        )

        # 3. Observação
        if sinalizacao == SINALIZACAO_OK:
            obs = "Keyword encontrada no edital."
        elif sinalizacao == SINALIZACAO_NAO_IDENTIFICADO:
            obs = "Nenhuma keyword encontrada no texto do edital."
        elif sinalizacao == SINALIZACAO_NAO_CONFORME:
            obs = "Ausência de elemento obrigatório detectada."
        else:
            obs = ""

        # 4. Retrieve guia_tcu reference
        ref = _retrieve_guia_ref(q.query_guia_tcu, q.stage_tag, use_retriever)

        check = CheckItem(
            check_id=q.id,
            stage_tag=q.stage_tag,
            pergunta_de_auditoria=q.pergunta,
            sinalizacao=sinalizacao,
            trecho_do_edital=snippet or "",
            referencia_guia_tcu=ref,
            observacao=obs,
        )
        checks.append(check)

        # Update distributions
        stage_dist[q.stage_tag] = stage_dist.get(q.stage_tag, 0) + 1
        sinal_dist[sinalizacao] = sinal_dist.get(sinalizacao, 0) + 1

    result = ChecklistResult(
        run_id=run_id,
        arquivo_analisado=arquivo_nome,
        total_checks=len(checks),
        checks=checks,
        stage_tag_distribution=stage_dist,
        sinalizacao_distribution=sinal_dist,
    )

    logger.info(
        f"Checklist generated: {result.total_checks} checks, "
        f"sinalizacao={dict(sinal_dist)}"
    )
    return result


def generate_checklist_from_pdf(
    pdf_path: str,
    use_retriever: bool = True,
) -> ChecklistResult:
    """
    Convenience: extract text from PDF then generate checklist.

    Uses PyMuPDF + pdfplumber fallback (same as matching module).
    """
    from govy.matching.pdf_utils import extract_text_from_pdf

    text = extract_text_from_pdf(pdf_path)
    if not text or len(text.strip()) < _MIN_TEXT_LENGTH:
        raise ValueError(
            f"Não foi possível extrair texto suficiente do PDF: {pdf_path}"
        )

    import os

    nome = os.path.basename(pdf_path)
    return generate_checklist(text, arquivo_nome=nome, use_retriever=use_retriever)
