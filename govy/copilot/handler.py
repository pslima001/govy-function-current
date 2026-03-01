# govy/copilot/handler.py
"""
Handler principal do Copiloto — orquestra todo o pipeline.

Fluxo:
  1. build_policy()
  2. detect_context() + detect_intent() + choose_tone()
  3. Se tentativa_defesa → bloquear imediatamente
  4. Se pergunta_bi e BI desabilitado → placeholder + coleta de parâmetros
  5. Retrieval (KB + BI + workspace) conforme intent
  6. Se require_evidence e sem evidência → resposta de incerteza
  7. Chamar LLM para gerar resposta
  8. Validar resposta contra policy
  9. Retornar CopilotOutput
"""
import logging
import uuid
import time
from datetime import datetime, timezone
from typing import Optional

from govy.copilot.contracts import (
    CopilotOutput, Evidence, BiRequestDraft,
    BiProductQuery, BiLocation, BiTimeRange,
    WorkspaceContext,
)
from govy.copilot.config import (
    LLM_ENABLED,
    LLM_DISABLED_MESSAGE,
    LLM_PROVIDER,
    validate_llm_config,
    get_active_model,
)
from govy.copilot.policy import build_policy, validate_response
from govy.copilot.router import (
    detect_intent, detect_context, choose_tone,
    build_workspace_context,
    detect_bi_metric_type, detect_bi_platform, detect_bi_time_preset,
)
from govy.copilot.retrieval import retrieve_from_kb, retrieve_from_bi, retrieve_workspace_docs
from govy.copilot.llm_answer import generate_answer
from govy.copilot.conversation import save_turn, build_history_context

logger = logging.getLogger(__name__)

# Validar config na importação — fail-fast
_config_ok, _config_error = validate_llm_config()


def handle_chat(user_text: str, context: Optional[dict] = None) -> CopilotOutput:
    """
    Ponto de entrada principal do copiloto.

    Args:
        user_text: texto do usuário
        context: dict com workspace_id, licitacao_id, uf, tribunal, etc.

    Returns:
        CopilotOutput com resposta, evidências, flags
    """
    request_id = str(uuid.uuid4())[:12]
    t_start = time.time()
    context = context or {}
    policy = build_policy()
    conversation_id = context.get("conversation_id", "")

    # ─── Fail-closed: LLM desligado ─────────────────────────────
    # Intent detection e bloqueio de defesa funcionam SEM LLM.
    # Só bloqueia chamadas ao LLM de fato.

    # ─── Histórico de conversa ───────────────────────────────────
    history_context = build_history_context(conversation_id) if conversation_id else None

    # ─── Router ──────────────────────────────────────────────────
    ws_ctx = build_workspace_context(context)
    ctx = ws_ctx.mode
    intent = detect_intent(user_text)
    tone = choose_tone(user_text)

    logger.info(
        f"[{request_id}] copilot: ctx={ctx} intent={intent} tone={tone} "
        f"llm_enabled={LLM_ENABLED} provider={LLM_PROVIDER} docs={ws_ctx.doc_names()}"
    )

    # ─── Bloqueio de defesa (não precisa de LLM) ─────────────────
    if intent == "tentativa_defesa":
        _log_audit(request_id, intent, ctx, t_start, llm_called=False, blocked_defense=True)
        return CopilotOutput(
            intent=intent,
            tone="simples",
            answer=(
                "Esse tipo de conteúdo (recurso/impugnação/defesa) é gerado no módulo "
                "de **Criação de Documentos**. Quer que eu te direcione para lá?"
            ),
            followup_questions=[
                "Você quer criar: recurso, impugnação ou contrarrazões?",
            ],
            flags={"blocked_defense": True, "request_id": request_id},
        )

    # ─── Operacional (não precisa de LLM) ────────────────────────
    if intent == "operacional_sistema":
        _log_audit(request_id, intent, ctx, t_start, llm_called=False)
        output = _handle_operacional(user_text, tone)
        output.flags["request_id"] = request_id
        return output

    # ─── BI Placeholder (não precisa de LLM) ─────────────────────
    if intent == "pergunta_bi" and not policy.bi_enabled:
        _log_audit(request_id, intent, ctx, t_start, llm_called=False)
        output = _handle_bi_placeholder(user_text, context, ws_ctx)
        output.flags["request_id"] = request_id
        return output

    # ─── Fail-closed: se LLM desabilitado, parar aqui ────────────
    if not LLM_ENABLED:
        _log_audit(request_id, intent, ctx, t_start, llm_called=False, fallback="llm_disabled")
        return CopilotOutput(
            intent=intent,
            tone=tone,
            answer=LLM_DISABLED_MESSAGE,
            flags={
                "request_id": request_id,
                "llm_enabled": False,
                "workspace_mode": ws_ctx.mode,
            },
        )

    # ─── Fail-closed: config inválida ────────────────────────────
    if not _config_ok:
        _log_audit(request_id, intent, ctx, t_start, llm_called=False, fallback="config_error")
        return CopilotOutput(
            intent=intent,
            tone=tone,
            answer=LLM_DISABLED_MESSAGE,
            flags={
                "request_id": request_id,
                "llm_enabled": True,
                "config_error": _config_error,
                "workspace_mode": ws_ctx.mode,
            },
        )

    # ─── Retrieval ───────────────────────────────────────────────
    evidence: list[Evidence] = []

    if intent == "pergunta_bi":
        evidence = retrieve_from_bi(user_text, policy)
    else:
        # Perguntas jurídicas e checklist usam KB
        uf = ws_ctx.uf or context.get("uf")
        tribunal = context.get("tribunal")
        procedural_stage = context.get("procedural_stage")
        if isinstance(procedural_stage, str):
            procedural_stage = [procedural_stage]

        evidence = retrieve_from_kb(
            query=user_text,
            policy=policy,
            uf=uf,
            tribunal=tribunal,
            procedural_stage=procedural_stage,
        )

        # Se estamos num workspace, buscar também docs do workspace
        workspace_id = ws_ctx.workspace_id or ws_ctx.licitacao_id
        if workspace_id:
            # Converter WorkspaceDoc para dicts para retrieve_workspace_docs
            available_docs_raw = [
                {"name": d.name, "doc_type": d.doc_type, "indexed": d.indexed}
                for d in ws_ctx.available_docs
            ]
            ws_evidence = retrieve_workspace_docs(
                user_text, workspace_id, policy,
                available_docs=available_docs_raw,
            )
            evidence.extend(ws_evidence)

    # ─── Sem evidência ───────────────────────────────────────────
    if policy.require_evidence and not evidence:
        _log_audit(request_id, intent, ctx, t_start, llm_called=False,
                   evidence_count=0, fallback="no_evidence")
        output = _build_no_evidence_response(intent, tone, ws_ctx)
        output.flags["request_id"] = request_id
        return output

    # ─── Gerar resposta via LLM ──────────────────────────────────
    llm_result = generate_answer(
        query=user_text,
        evidence=evidence,
        tone=tone,
        request_id=request_id,
        history_context=history_context,
    )

    answer = llm_result["answer"]

    # ─── Validação pós-resposta ──────────────────────────────────
    violations = validate_response(answer, policy)
    if violations:
        logger.warning(f"[{request_id}] copilot: policy violations detectadas: {violations}")
        answer = (
            "Não consigo responder dessa forma dentro das regras do copiloto. "
            "Posso reformular de outra maneira — tente ser mais específico sobre "
            "o que deseja saber."
        )

    # ─── Salvar turno na conversa ────────────────────────────────
    if conversation_id:
        try:
            save_turn(conversation_id, user_text, answer, intent=intent)
        except Exception as e:
            logger.warning(f"[{request_id}] Falha ao salvar turno: {e}")

    # ─── Log de auditoria ────────────────────────────────────────
    _log_audit(
        request_id, intent, ctx, t_start,
        llm_called=True,
        provider=llm_result.get("llm_provider"),
        model=llm_result.get("llm_model"),
        llm_time_ms=llm_result.get("llm_time_ms"),
        evidence_count=len(evidence),
        llm_error=llm_result.get("llm_error", False),
        policy_violations=violations or None,
        blocked_defense=False,
    )

    return CopilotOutput(
        intent=intent,
        tone=tone,
        answer=answer,
        uncertainty=llm_result.get("uncertainty"),
        followup_questions=llm_result.get("followup_questions", [])[:3],
        evidence=evidence[: policy.max_evidence],
        flags={
            "request_id": request_id,
            "llm_time_ms": llm_result.get("llm_time_ms"),
            "llm_model": llm_result.get("llm_model"),
            "llm_provider": llm_result.get("llm_provider"),
            "policy_violations": violations if violations else None,
            "workspace_mode": ws_ctx.mode,
        },
    )


# ─── Log de auditoria ────────────────────────────────────────────────


def _log_audit(
    request_id: str,
    intent: str,
    ctx: str,
    t_start: float,
    *,
    llm_called: bool = False,
    provider: str = None,
    model: str = None,
    llm_time_ms: int = None,
    evidence_count: int = None,
    llm_error: bool = False,
    policy_violations: list = None,
    blocked_defense: bool = False,
    fallback: str = None,
):
    """Log estruturado de auditoria para cada request."""
    total_ms = int((time.time() - t_start) * 1000)
    logger.info(
        f"AUDIT [{request_id}] "
        f"intent={intent} ctx={ctx} "
        f"provider={provider or '-'} model={model or '-'} "
        f"llm_called={llm_called} llm_time_ms={llm_time_ms or 0} "
        f"total_ms={total_ms} "
        f"evidence_count={evidence_count if evidence_count is not None else '-'} "
        f"llm_error={llm_error} "
        f"blocked_defense={blocked_defense} "
        f"fallback={fallback or '-'} "
        f"violations={policy_violations or '-'}"
    )


# ─── Handlers especializados ────────────────────────────────────────


def _handle_operacional(user_text: str, tone: str) -> CopilotOutput:
    """Perguntas operacionais sobre o sistema — sem KB, resposta direta."""
    return CopilotOutput(
        intent="operacional_sistema",
        tone=tone,
        answer=(
            "Para dúvidas sobre o funcionamento da plataforma GOVY, "
            "consulte a seção de **Ajuda** no menu principal ou entre em contato "
            "com o suporte. Posso ajudar com questões jurídicas sobre licitações!"
        ),
        followup_questions=[
            "Você tem alguma dúvida jurídica sobre uma licitação?",
        ],
        flags={"operacional": True},
    )


def _build_no_evidence_response(
    intent: str,
    tone: str,
    ws_ctx: WorkspaceContext,
) -> CopilotOutput:
    """
    Resposta quando require_evidence=True mas nenhuma evidência foi encontrada.
    Context-aware: não pede documentos se já estão no workspace.
    """
    if ws_ctx.mode == "licitacao_workspace":
        if ws_ctx.has_indexed_text:
            # Tem docs indexados mas a busca não encontrou nada relevante
            doc_list = ", ".join(ws_ctx.doc_names()) or "os documentos anexados"
            answer = (
                f"Pesquisei em {doc_list} mas não encontrei um trecho que responda "
                "sua pergunta com segurança. Tente reformular ou indicar a seção/cláusula "
                "específica do documento."
            )
            followup = [
                "Pode indicar a seção ou cláusula específica?",
                "Quer que eu busque na base jurídica geral (leis, jurisprudência)?",
            ]
        elif ws_ctx.available_docs:
            # Tem docs mas não estão indexados ainda
            doc_list = ", ".join(ws_ctx.doc_names())
            answer = (
                f"Os documentos ({doc_list}) ainda não foram indexados para busca. "
                "Enquanto isso, cole o trecho relevante aqui que eu analiso."
            )
            followup = [
                "Cole o trecho do documento que deseja analisar.",
                "Quer que eu busque na base jurídica geral enquanto isso?",
            ]
        else:
            # Workspace sem docs
            answer = (
                "Este workspace ainda não tem documentos anexados. "
                "Anexe o edital, TR ou ETP para que eu possa consultar, "
                "ou cole o trecho relevante."
            )
            followup = [
                "Você pode anexar o edital ou TR neste workspace.",
                "Cole o trecho relevante do documento aqui.",
            ]
    else:
        # site_geral — fora do workspace
        answer = (
            "Não encontrei evidência suficiente **na base interna** para responder "
            "com segurança. Se você estiver analisando uma licitação específica, "
            "acesse o workspace dela para uma resposta mais precisa."
        )
        followup = [
            "Você está analisando uma licitação específica? Acesse o workspace dela.",
            "Pode colar o trecho relevante do documento?",
        ]

    return CopilotOutput(
        intent=intent,
        tone=tone,
        answer=answer,
        uncertainty="Evidência interna insuficiente para afirmar.",
        followup_questions=followup,
        flags={
            "needs_more_context": True,
            "workspace_mode": ws_ctx.mode,
            "has_indexed_text": ws_ctx.has_indexed_text,
        },
    )


def _handle_bi_placeholder(
    user_text: str,
    context: dict,
    ws_ctx: WorkspaceContext,
) -> CopilotOutput:
    """
    Fluxo BI quando BI_ENABLED=false.
    Não retorna números. Coleta parâmetros. Gera draft. Persiste.
    """
    # ─── Extrair o que for possível do texto e contexto ──────────
    metric_type = detect_bi_metric_type(user_text)
    platform = detect_bi_platform(user_text)
    time_preset = detect_bi_time_preset(user_text)

    workspace_id = ws_ctx.workspace_id or context.get("workspace_id")
    licitacao_id = ws_ctx.licitacao_id or context.get("licitacao_id")
    uf = ws_ctx.uf or context.get("uf")
    orgao = ws_ctx.orgao or context.get("orgao")

    # ─── Determinar o que ainda precisa do usuário ───────────────
    needs_user_input = []

    # Produto: sempre precisa (não extraímos NLP de produto ainda)
    needs_user_input.append("product_query")

    # Localidade
    if not uf and not context.get("city"):
        needs_user_input.append("city_or_uf")

    # Plataforma
    if platform == "unknown":
        needs_user_input.append("platform")

    # Período
    if not time_preset:
        needs_user_input.append("time_range")

    # ─── Montar draft ────────────────────────────────────────────
    request_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    draft = BiRequestDraft(
        request_id=request_id,
        created_at_utc=now_utc,
        user_question_raw=user_text,
        metric_type=metric_type,
        product_query=BiProductQuery(raw="", confidence=0.0),
        location=BiLocation(
            city=context.get("city"),
            uf=uf,
            orgao=orgao,
        ),
        platform=platform,
        time_range=BiTimeRange(preset=time_preset),
        workspace_id=workspace_id,
        licitacao_id=licitacao_id,
        needs_user_input=needs_user_input,
        assumptions=[],
    )

    # ─── Persistir draft ─────────────────────────────────────────
    blob_path = None
    bi_draft_persisted = False
    bi_draft_error = None
    try:
        from govy.copilot.bi_request_store import store_bi_request_draft
        blob_path = store_bi_request_draft(draft)
        bi_draft_persisted = blob_path is not None
    except Exception as e:
        logger.error(f"Falha ao persistir bi_request_draft: {e}")
        bi_draft_error = str(e)

    # ─── Montar follow-ups (sempre 3) ────────────────────────────
    followup_questions = _build_bi_followups(needs_user_input, ws_ctx.mode)

    # ─── Resposta ────────────────────────────────────────────────
    return CopilotOutput(
        intent="pergunta_bi",
        tone="simples",
        answer=(
            "Ainda não tenho acesso ao módulo de **Business Intelligence** para "
            "fornecer números com segurança. Para preparar sua consulta, preciso "
            "de algumas informações:"
        ),
        uncertainty="Módulo BI indisponível — nenhum número pode ser fornecido.",
        followup_questions=followup_questions,
        evidence=[],
        flags={
            "bi_placeholder": True,
            "bi_draft_persisted": bi_draft_persisted,
            "bi_draft_blob_path": blob_path,
            "bi_draft_error": bi_draft_error,
        },
        bi_pending=True,
        bi_request_draft=draft,
    )


def _build_bi_followups(needs: list[str], ctx: str) -> list[str]:
    """
    Retorna exatamente 3 follow-ups para coleta de parâmetros BI.
    Ordem fixa: produto → local → plataforma.
    Período fica para o próximo turno se faltar.
    """
    questions = []

    # 1. Produto (sempre primeiro)
    if "product_query" in needs:
        questions.append(
            "Qual é o item ou produto que você quer consultar? "
            "(ex.: dipirona 500mg, notebook, serviço de limpeza)"
        )
    else:
        questions.append("Pode detalhar melhor o item/produto?")

    # 2. Local
    if "city_or_uf" in needs:
        questions.append(
            "Qual local? (cidade, UF ou órgão)" if ctx != "licitacao_workspace"
            else "Deseja usar a localidade desta licitação ou outra?"
        )
    else:
        questions.append("Deseja filtrar por alguma cidade, UF ou órgão específico?")

    # 3. Plataforma
    if "platform" in needs:
        questions.append(
            "Em qual plataforma? (PNCP, Comprasnet, BEC ou todas)"
        )
    else:
        questions.append("Deseja restringir a alguma plataforma específica?")

    return questions[:3]


# ─── Explain Checklist ─────────────────────────────────────────────────

def explain_check(check_id: str, edital_id: str, context: Optional[dict] = None) -> CopilotOutput:
    """
    Explica um item do checklist de conformidade usando LLM + evidência da KB.

    Args:
        check_id: ID do item do checklist (ex.: "PL-001", "ED-003")
        edital_id: ID do edital/workspace para buscar contexto
        context: dict opcional com workspace_id, uf, etc.

    Returns:
        CopilotOutput com explicação detalhada do item
    """
    request_id = str(uuid.uuid4())[:12]
    context = context or {}
    policy = build_policy()

    # Buscar a audit question correspondente ao check_id
    from govy.copilot._checklist_lookup import get_audit_question_by_id
    audit_q = get_audit_question_by_id(check_id)

    if not audit_q:
        return CopilotOutput(
            intent="checklist_conformidade",
            tone="tecnico",
            answer=f"Item de checklist **{check_id}** não encontrado na base de auditoria.",
            flags={"explain_check": True, "check_id": check_id, "found": False,
                   "request_id": request_id},
        )

    # ─── Fail-closed: se LLM desabilitado, resposta sem LLM ─────
    if not LLM_ENABLED or not _config_ok:
        return CopilotOutput(
            intent="checklist_conformidade",
            tone="tecnico",
            answer=(
                f"O item **{check_id}** ({audit_q['stage_tag']}) verifica: "
                f"\"{audit_q['pergunta']}\". "
                f"Severidade: **{audit_q['severidade']}**. "
                f"{LLM_DISABLED_MESSAGE}"
            ),
            flags={
                "explain_check": True,
                "check_id": check_id,
                "found": True,
                "llm_enabled": False,
                "request_id": request_id,
            },
        )

    # Buscar evidência na KB sobre o tema do item
    uf = context.get("uf")
    tribunal = context.get("tribunal")
    evidence = retrieve_from_kb(
        query=audit_q["pergunta"],
        policy=policy,
        uf=uf,
        tribunal=tribunal,
    )

    # Montar query para o LLM
    query = (
        f"Explique o item de checklist [{check_id}]: \"{audit_q['pergunta']}\"\n"
        f"Estágio: {audit_q['stage_tag']}\n"
        f"Severidade: {audit_q['severidade']}\n"
        f"O que verificar: {', '.join(audit_q['keywords_edital'])}\n"
        f"Sinais de ausência: {', '.join(audit_q['keywords_ausencia'])}"
    )

    llm_result = generate_answer(
        query=query,
        evidence=evidence,
        tone="tecnico",
        request_id=request_id,
    )

    answer = llm_result["answer"]

    # Validação pós-resposta
    violations = validate_response(answer, policy)
    if violations:
        logger.warning(f"[{request_id}] explain_check: policy violations: {violations}")
        answer = (
            f"O item **{check_id}** ({audit_q['stage_tag']}) verifica: "
            f"\"{audit_q['pergunta']}\". "
            f"Severidade: **{audit_q['severidade']}**. "
            f"Consulte o Guia de Auditoria do TCU para mais detalhes."
        )

    return CopilotOutput(
        intent="checklist_conformidade",
        tone="tecnico",
        answer=answer,
        uncertainty=llm_result.get("uncertainty"),
        followup_questions=llm_result.get("followup_questions", [])[:3],
        evidence=evidence[: policy.max_evidence],
        flags={
            "explain_check": True,
            "check_id": check_id,
            "edital_id": edital_id,
            "stage_tag": audit_q["stage_tag"],
            "severidade": audit_q["severidade"],
            "found": True,
            "llm_time_ms": llm_result.get("llm_time_ms"),
            "llm_provider": llm_result.get("llm_provider"),
            "request_id": request_id,
        },
    )
