"""
GOVY Checklist — Perguntas de auditoria determinísticas (v1)
==============================================================
Tabela de checks baseados nas seções do Manual TCU.
Cada check tem keywords para buscar no texto do edital e uma
pergunta para o retriever do guia_tcu.

REGRA: Esta tabela é o source-of-truth. Sem LLM, sem inferência.
Para adicionar checks: editar esta tabela e rodar testes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class AuditQuestion:
    """Uma pergunta de auditoria pré-definida."""
    id: str                         # Identificador único (ex: "PL-001")
    stage_tag: str                  # Fase do processo
    pergunta: str                   # Pergunta ao licitante
    keywords_edital: List[str]      # Keywords para buscar no edital (OR)
    keywords_ausencia: List[str]    # Keywords cuja ausência indica problema
    query_guia_tcu: str             # Query para o retriever do guia_tcu
    severidade: str                 # "alta" | "media" | "baixa"


# ─── Tabela de Perguntas v1 ──────────────────────────────────────────────────
# Organizado por stage_tag. IDs: PL=planejamento, ED=edital, SE=seleção,
# CO=contrato, GE=gestão, GO=governança.

AUDIT_QUESTIONS: List[AuditQuestion] = [
    # ═══════════════════════════════════════════════════════════════════════════
    # PLANEJAMENTO
    # ═══════════════════════════════════════════════════════════════════════════
    AuditQuestion(
        id="PL-001",
        stage_tag="planejamento",
        pergunta="O edital menciona o Estudo Técnico Preliminar (ETP)?",
        keywords_edital=["estudo técnico preliminar", "etp"],
        keywords_ausencia=[],
        query_guia_tcu="estudo técnico preliminar ETP obrigatório",
        severidade="alta",
    ),
    AuditQuestion(
        id="PL-002",
        stage_tag="planejamento",
        pergunta="O Termo de Referência (TR) está presente ou referenciado?",
        keywords_edital=["termo de referência", "termo de referencia"],
        keywords_ausencia=[],
        query_guia_tcu="termo de referência TR conteúdo obrigatório",
        severidade="alta",
    ),
    AuditQuestion(
        id="PL-003",
        stage_tag="planejamento",
        pergunta="A estimativa de preços está fundamentada com pesquisa de mercado?",
        keywords_edital=["pesquisa de preço", "pesquisa de mercado", "estimativa de valor",
                         "valor estimado", "preço de referência", "orçamento estimado"],
        keywords_ausencia=[],
        query_guia_tcu="estimativa valor contratação pesquisa preços fontes",
        severidade="alta",
    ),
    AuditQuestion(
        id="PL-004",
        stage_tag="planejamento",
        pergunta="O edital define o objeto de forma precisa e suficiente?",
        keywords_edital=["objeto", "definição do objeto", "descrição do objeto"],
        keywords_ausencia=[],
        query_guia_tcu="definição do objeto licitação requisitos",
        severidade="alta",
    ),
    AuditQuestion(
        id="PL-005",
        stage_tag="planejamento",
        pergunta="A análise de riscos da contratação foi realizada?",
        keywords_edital=["análise de risco", "gestão de risco", "mapa de risco",
                         "matriz de risco"],
        keywords_ausencia=[],
        query_guia_tcu="análise riscos contratação planejamento",
        severidade="media",
    ),
    AuditQuestion(
        id="PL-006",
        stage_tag="planejamento",
        pergunta="O parcelamento do objeto foi justificado?",
        keywords_edital=["parcelamento", "parcela", "lote", "grupo", "item"],
        keywords_ausencia=[],
        query_guia_tcu="parcelamento contratação justificativa viabilidade",
        severidade="media",
    ),
    AuditQuestion(
        id="PL-007",
        stage_tag="planejamento",
        pergunta="Há previsão orçamentária adequada?",
        keywords_edital=["dotação orçamentária", "adequação orçamentária",
                         "previsão orçamentária", "crédito orçamentário"],
        keywords_ausencia=[],
        query_guia_tcu="adequação orçamentária contratação",
        severidade="alta",
    ),

    # ═══════════════════════════════════════════════════════════════════════════
    # EDITAL
    # ═══════════════════════════════════════════════════════════════════════════
    AuditQuestion(
        id="ED-001",
        stage_tag="edital",
        pergunta="O edital prevê prazo para impugnação?",
        keywords_edital=["impugnação", "impugnar"],
        keywords_ausencia=[],
        query_guia_tcu="prazo impugnação edital licitação",
        severidade="alta",
    ),
    AuditQuestion(
        id="ED-002",
        stage_tag="edital",
        pergunta="Há previsão de pedidos de esclarecimento?",
        keywords_edital=["esclarecimento", "pedido de esclarecimento"],
        keywords_ausencia=[],
        query_guia_tcu="pedido esclarecimento edital prazo",
        severidade="media",
    ),
    AuditQuestion(
        id="ED-003",
        stage_tag="edital",
        pergunta="O edital define critério de julgamento (menor preço, técnica e preço, etc.)?",
        keywords_edital=["critério de julgamento", "menor preço", "técnica e preço",
                         "maior desconto", "melhor técnica"],
        keywords_ausencia=[],
        query_guia_tcu="critério julgamento licitação menor preço técnica",
        severidade="alta",
    ),
    AuditQuestion(
        id="ED-004",
        stage_tag="edital",
        pergunta="A modalidade de licitação está correta para o valor e tipo de objeto?",
        keywords_edital=["pregão", "concorrência", "concurso", "leilão",
                         "diálogo competitivo", "modalidade"],
        keywords_ausencia=[],
        query_guia_tcu="modalidade licitação pregão concorrência quando usar",
        severidade="alta",
    ),
    AuditQuestion(
        id="ED-005",
        stage_tag="edital",
        pergunta="O modo de disputa está definido (aberto, fechado, combinado)?",
        keywords_edital=["modo de disputa", "aberto", "fechado", "aberto e fechado",
                         "lance"],
        keywords_ausencia=[],
        query_guia_tcu="modo disputa aberto fechado licitação",
        severidade="media",
    ),

    # ═══════════════════════════════════════════════════════════════════════════
    # SELEÇÃO
    # ═══════════════════════════════════════════════════════════════════════════
    AuditQuestion(
        id="SE-001",
        stage_tag="seleção",
        pergunta="Os requisitos de habilitação jurídica estão definidos?",
        keywords_edital=["habilitação jurídica", "habilitação juridica",
                         "ato constitutivo", "estatuto", "contrato social"],
        keywords_ausencia=[],
        query_guia_tcu="habilitação jurídica documentos exigidos",
        severidade="alta",
    ),
    AuditQuestion(
        id="SE-002",
        stage_tag="seleção",
        pergunta="Os requisitos de habilitação técnica estão definidos?",
        keywords_edital=["habilitação técnica", "qualificação técnica",
                         "atestado de capacidade", "certidão de acervo"],
        keywords_ausencia=[],
        query_guia_tcu="habilitação técnica qualificação atestado capacidade",
        severidade="alta",
    ),
    AuditQuestion(
        id="SE-003",
        stage_tag="seleção",
        pergunta="Os requisitos de habilitação econômico-financeira estão proporcionais?",
        keywords_edital=["habilitação econômico", "qualificação econômico",
                         "balanço patrimonial", "certidão negativa", "capital social"],
        keywords_ausencia=[],
        query_guia_tcu="habilitação econômico-financeira proporcionalidade exigências",
        severidade="alta",
    ),
    AuditQuestion(
        id="SE-004",
        stage_tag="seleção",
        pergunta="Há previsão de recursos administrativos?",
        keywords_edital=["recurso", "contrarrazão", "contrarrazões",
                         "prazo recursal"],
        keywords_ausencia=[],
        query_guia_tcu="recurso administrativo licitação prazo procedimento",
        severidade="media",
    ),
    AuditQuestion(
        id="SE-005",
        stage_tag="seleção",
        pergunta="As sanções para infrações de licitantes estão previstas?",
        keywords_edital=["sanção", "sanções", "penalidade", "penalidades",
                         "advertência", "multa", "impedimento", "inidoneidade"],
        keywords_ausencia=[],
        query_guia_tcu="infrações sanções administrativas licitantes penalidade",
        severidade="media",
    ),
    AuditQuestion(
        id="SE-006",
        stage_tag="seleção",
        pergunta="Há tratamento diferenciado para ME/EPP (microempresas)?",
        keywords_edital=["microempresa", "empresa de pequeno porte", "me/epp",
                         "me e epp", "tratamento diferenciado", "lc 123",
                         "lei complementar 123"],
        keywords_ausencia=[],
        query_guia_tcu="microempresa pequeno porte tratamento diferenciado ME EPP",
        severidade="media",
    ),

    # ═══════════════════════════════════════════════════════════════════════════
    # CONTRATO
    # ═══════════════════════════════════════════════════════════════════════════
    AuditQuestion(
        id="CO-001",
        stage_tag="contrato",
        pergunta="As cláusulas contratuais essenciais estão presentes?",
        keywords_edital=["cláusula", "minuta do contrato", "minuta contratual",
                         "condições contratuais"],
        keywords_ausencia=[],
        query_guia_tcu="cláusulas essenciais contrato administrativo",
        severidade="alta",
    ),
    AuditQuestion(
        id="CO-002",
        stage_tag="contrato",
        pergunta="A garantia contratual está prevista e dentro dos limites legais?",
        keywords_edital=["garantia contratual", "garantia de execução",
                         "caução", "seguro-garantia", "fiança bancária"],
        keywords_ausencia=[],
        query_guia_tcu="garantia contratual limites caução seguro fiança",
        severidade="media",
    ),
    AuditQuestion(
        id="CO-003",
        stage_tag="contrato",
        pergunta="A duração do contrato está definida e é compatível com o objeto?",
        keywords_edital=["vigência", "duração", "prazo do contrato",
                         "prazo contratual", "prorrogação"],
        keywords_ausencia=[],
        query_guia_tcu="duração contrato vigência prazo prorrogação limites",
        severidade="alta",
    ),
    AuditQuestion(
        id="CO-004",
        stage_tag="contrato",
        pergunta="A matriz de riscos está presente (quando obrigatória)?",
        keywords_edital=["matriz de risco", "alocação de risco"],
        keywords_ausencia=[],
        query_guia_tcu="matriz riscos contrato alocação obrigatória",
        severidade="media",
    ),

    # ═══════════════════════════════════════════════════════════════════════════
    # GESTÃO
    # ═══════════════════════════════════════════════════════════════════════════
    AuditQuestion(
        id="GE-001",
        stage_tag="gestão",
        pergunta="O modelo de gestão/fiscalização do contrato está definido?",
        keywords_edital=["fiscal do contrato", "gestor do contrato",
                         "fiscalização", "modelo de gestão"],
        keywords_ausencia=[],
        query_guia_tcu="fiscalização contrato gestor fiscal designação",
        severidade="alta",
    ),
    AuditQuestion(
        id="GE-002",
        stage_tag="gestão",
        pergunta="Os critérios de medição e pagamento estão definidos?",
        keywords_edital=["medição", "pagamento", "nota fiscal",
                         "critério de pagamento", "atesto"],
        keywords_ausencia=[],
        query_guia_tcu="critérios medição pagamento contrato prazo",
        severidade="alta",
    ),
    AuditQuestion(
        id="GE-003",
        stage_tag="gestão",
        pergunta="Há previsão de reajuste/reequilíbrio contratual?",
        keywords_edital=["reajuste", "reequilíbrio", "repactuação",
                         "índice de reajuste", "equilíbrio econômico"],
        keywords_ausencia=[],
        query_guia_tcu="reajuste reequilíbrio econômico-financeiro contrato",
        severidade="media",
    ),
    AuditQuestion(
        id="GE-004",
        stage_tag="gestão",
        pergunta="As condições de recebimento do objeto estão definidas?",
        keywords_edital=["recebimento provisório", "recebimento definitivo",
                         "termo de recebimento"],
        keywords_ausencia=[],
        query_guia_tcu="recebimento provisório definitivo objeto contrato",
        severidade="media",
    ),
    AuditQuestion(
        id="GE-005",
        stage_tag="gestão",
        pergunta="A subcontratação está regulamentada (se permitida)?",
        keywords_edital=["subcontratação", "subcontratar", "subcontratado",
                         "cessão", "transferência"],
        keywords_ausencia=[],
        query_guia_tcu="subcontratação limites autorização contrato",
        severidade="baixa",
    ),

    # ═══════════════════════════════════════════════════════════════════════════
    # GOVERNANÇA
    # ═══════════════════════════════════════════════════════════════════════════
    AuditQuestion(
        id="GO-001",
        stage_tag="governança",
        pergunta="O processo menciona conformidade com a Lei 14.133/2021?",
        keywords_edital=["14.133", "lei 14133", "lei de licitações",
                         "nova lei de licitações"],
        keywords_ausencia=[],
        query_guia_tcu="lei 14.133 2021 aplicação normas gerais",
        severidade="alta",
    ),
    AuditQuestion(
        id="GO-002",
        stage_tag="governança",
        pergunta="O edital prevê publicidade e transparência adequadas?",
        keywords_edital=["publicação", "diário oficial", "pncp",
                         "portal nacional de contratações",
                         "comprasnet", "transparência"],
        keywords_ausencia=[],
        query_guia_tcu="publicidade transparência licitação PNCP divulgação",
        severidade="media",
    ),
]


def get_questions_by_stage(stage_tag: str) -> List[AuditQuestion]:
    """Retorna perguntas filtradas por stage_tag."""
    return [q for q in AUDIT_QUESTIONS if q.stage_tag == stage_tag]


def get_all_stage_tags() -> List[str]:
    """Retorna lista de stage_tags únicos com perguntas."""
    return sorted(set(q.stage_tag for q in AUDIT_QUESTIONS))
