# juris_constants.py - Constantes e Enums para KB Juridica GOVY
# Versao: 2.0 | Data: 29/01/2026
# ATUALIZADO: Mappings completos baseados em valores reais medidos nos FAILs

"""
Este modulo define os enums validos para classificacao de jurisprudencia
e funcoes de normalizacao/clamp para garantir valores consistentes.

REGRA DE OURO: Melhor NAO_CLARO do que valor inventado.
"""

# ==============================================================================
# ENUMS VALIDOS (SPEC 1.2 + UPSERT)
# ==============================================================================

# Doc types aceitos pelo upsert
VALID_DOC_TYPES = {"jurisprudencia", "lei", "doutrina", "edital"}

# Tribunais aceitos pelo upsert
VALID_TRIBUNALS = {"TCU", "TCE"}

# Secoes aceitas para chunks de jurisprudencia
VALID_CHUNK_SECOES = {"tese", "vital", "fundamento_legal", "limites", "contexto_minimo"}

VALID_PROCEDURAL_STAGE = {
    "EDITAL",
    "DISPUTA",
    "JULGAMENTO",
    "HABILITACAO",
    "CONTRATACAO",
    "EXECUCAO",
    "PAGAMENTO",
    "SANCIONAMENTO",
    "NAO_CLARO"
}

VALID_HOLDING_OUTCOME = {
    "MANTEVE",
    "AFASTOU",
    "DETERMINOU_AJUSTE",
    "ANULOU",
    "NAO_CLARO"
}

VALID_REMEDY_TYPE = {
    "IMPUGNACAO",
    "RECURSO",
    "CONTRARRAZOES",
    "REPRESENTACAO",
    "DENUNCIA",
    "ORIENTACAO_GERAL",
    "NAO_CLARO"
}

VALID_EFFECT = {
    "FLEXIBILIZA",
    "RIGORIZA",
    "CONDICIONAL"
}

VALID_SECAO = {
    "EMENTA",
    "RELATORIO",
    "FUNDAMENTACAO",
    "DISPOSITIVO",
    "VOTO",
    "NAO_CLARO"
}


# ==============================================================================
# ALIASES PARA COMPATIBILIDADE COM juris_pipeline.py
# ==============================================================================

# Aliases (nomes antigos -> novos)
PROCEDURAL_STAGES = VALID_PROCEDURAL_STAGE
HOLDING_OUTCOMES = VALID_HOLDING_OUTCOME
REMEDY_TYPES = VALID_REMEDY_TYPE
EFFECTS = VALID_EFFECT

# ==============================================================================
# PISTAS PARA CLASSIFICACAO (usado pelo juris_pipeline.py)
# ==============================================================================

PISTAS_PROCEDURAL_STAGE = {
    "EDITAL": ["edital", "publicacao", "aviso", "termo de referencia", "projeto basico"],
    "DISPUTA": ["sessao", "lance", "proposta", "pregao", "leilao", "disputa"],
    "JULGAMENTO": ["julgamento", "classificacao", "desclassificacao", "analise"],
    "HABILITACAO": ["habilitacao", "documentos", "certidao", "atestado", "qualificacao"],
    "CONTRATACAO": ["contrato", "assinatura", "homologacao", "adjudicacao"],
    "EXECUCAO": ["execucao", "fiscalizacao", "medicao", "aditivo", "reajuste"],
    "PAGAMENTO": ["pagamento", "liquidacao", "empenho", "nota fiscal"],
    "SANCIONAMENTO": ["sancao", "multa", "penalidade", "impedimento", "inidoneidade"],
}

PISTAS_HOLDING_OUTCOME = {
    "MANTEVE": ["manteve", "mantem", "confirmou", "regular", "procedente"],
    "AFASTOU": ["afastou", "improcedente", "rejeitou", "nao acolheu"],
    "DETERMINOU_AJUSTE": ["determinou", "recomendou", "orientou", "ressalva", "ajuste"],
    "ANULOU": ["anulou", "nulo", "nulidade", "revogou", "suspendeu", "cancelou"],
}

PISTAS_REMEDY_TYPE = {
    "IMPUGNACAO": ["impugnacao", "impugnou", "impugnar"],
    "RECURSO": ["recurso", "recorreu", "reexame", "reconsideracao", "embargos"],
    "CONTRARRAZOES": ["contrarrazoes", "contra-razoes"],
    "REPRESENTACAO": ["representacao", "representou"],
    "DENUNCIA": ["denuncia", "denunciou"],
    "ORIENTACAO_GERAL": ["consulta", "auditoria", "levantamento", "monitoramento"],
}

PISTAS_EFFECT = {
    "FLEXIBILIZA": ["pode", "admite", "permite", "faculta", "possivel"],
    "RIGORIZA": ["deve", "obrigatorio", "veda", "proibe", "impede", "nao pode"],
    "CONDICIONAL": ["desde que", "caso", "se", "mediante", "exceto"],
}

# ==============================================================================
# OUTRAS CONSTANTES
# ==============================================================================

CONFIDENCE_THRESHOLD = 0.90
REVIEW_QUEUE_DIR = "review_queue"

# ==============================================================================
# MAPEAMENTOS DE NORMALIZACAO - VERSAO COMPLETA
# Baseado em valores reais medidos nos FAILs do batch TCU 29/01/2026
# ==============================================================================

HOLDING_OUTCOME_MAPPINGS = {
    # ===== VALORES JA VALIDOS (passam direto) =====
    "MANTEVE": "MANTEVE",
    "AFASTOU": "AFASTOU",
    "DETERMINOU_AJUSTE": "DETERMINOU_AJUSTE",
    "ANULOU": "ANULOU",
    "NAO_CLARO": "NAO_CLARO",
    
    # ===== ANULATIVOS/SUSPENSIVOS -> ANULOU =====
    "ANULOU_DETERMINACAO": "ANULOU",
    "ANULOU_SANCAO": "ANULOU",
    "ANULOU_SANCIONOU": "ANULOU",
    "REVOGOU": "ANULOU",
    "REVOGOU_DETERMINACAO": "ANULOU",
    "SUSPENDEU": "ANULOU",
    "SUSPENDEU_CERTAME": "ANULOU",
    "SUSPENSAO_CAUTELAR": "ANULOU",
    "NULIDADE": "ANULOU",
    "DECLAROU_NULIDADE": "ANULOU",
    "ANULACAO": "ANULOU",
    "CANCELOU": "ANULOU",
    
    # ===== ACOLHEDORES/PROCEDENTES -> AFASTOU =====
    "ACOLHEU": "AFASTOU",
    "ACOLHEU_JUSTIFICATIVAS": "AFASTOU",
    "ACOLHEU_PARCIALMENTE": "DETERMINOU_AJUSTE",
    "ACOLHEU_REPRESENTACAO": "AFASTOU",
    "PROCEDENTE": "AFASTOU",
    "PROCEDENTE_PARCIAL": "DETERMINOU_AJUSTE",
    "PROVIDO": "AFASTOU",
    "PROVIMENTO_PARCIAL": "DETERMINOU_AJUSTE",
    "PARCIALMENTE_PROCEDENTE": "DETERMINOU_AJUSTE",
    "PARCIALMENTE_PROVIDO": "DETERMINOU_AJUSTE",
    "PARCIAL": "DETERMINOU_AJUSTE",
    "REFORMOU": "AFASTOU",
    
    # ===== REJEITATORIOS/IMPROCEDENTES -> MANTEVE =====
    "REJEITOU": "MANTEVE",
    "REJEITADO": "MANTEVE",
    "REJEITOU_ALEGACAO": "MANTEVE",
    "REJEITOU_ALEGACOES": "MANTEVE",
    "REJEITOU_JUSTIFICATIVAS": "MANTEVE",
    "NAO_ACOLHEU_ALEGACAO": "MANTEVE",
    "JULGOU_IMPROCEDENTE": "MANTEVE",
    "IMPROVIDO": "MANTEVE",
    "JULGOU_IRREGULARES": "MANTEVE",
    "JULGOU_IRREGULAR": "MANTEVE",
    "JULGOU_REGULARES": "MANTEVE",
    "JULGOU_REGULARES_COM_RESSALVA": "DETERMINOU_AJUSTE",
    
    # ===== SANCIONATORIOS/CONDENATORIOS -> DETERMINOU_AJUSTE =====
    "APLICOU_SANCAO": "DETERMINOU_AJUSTE",
    "APLICOU_SANCAO_BRANDA": "DETERMINOU_AJUSTE",
    "APLICOU_MULTA": "DETERMINOU_AJUSTE",
    "CONDENOU": "DETERMINOU_AJUSTE",
    "CONDENOU_DEBITO": "DETERMINOU_AJUSTE",
    "CONDENOU_RESPONSAVEIS": "DETERMINOU_AJUSTE",
    "CONDENOU_RESSARCIMENTO": "DETERMINOU_AJUSTE",
    "IMPUTOU_DEBITO": "DETERMINOU_AJUSTE",
    "DECLAROU_IRREGULARIDADE": "DETERMINOU_AJUSTE",
    "COMUNICOU_IRREGULARIDADE": "DETERMINOU_AJUSTE",
    
    # ===== ORIENTATIVOS/INFORMATIVOS -> DETERMINOU_AJUSTE =====
    "DETERMINOU": "DETERMINOU_AJUSTE",
    "RECOMENDOU": "DETERMINOU_AJUSTE",
    "ORIENTOU": "DETERMINOU_AJUSTE",
    "ORIENTOU_CORRIGIU": "DETERMINOU_AJUSTE",
    "ORIENTOU_PROCEDIMENTO": "DETERMINOU_AJUSTE",
    "DEU_CIENCIA": "DETERMINOU_AJUSTE",
    "CIENTIFICOU": "DETERMINOU_AJUSTE",
    "ESCLARECEU": "DETERMINOU_AJUSTE",
    "ESCLARECEU_ORIENTACAO": "DETERMINOU_AJUSTE",
    "FIRMOU_ENTENDIMENTO": "DETERMINOU_AJUSTE",
    "INTERPRETOU_NORMA": "DETERMINOU_AJUSTE",
    "RESPONDEU": "DETERMINOU_AJUSTE",
    "RESPONDEU_CONSULTA": "DETERMINOU_AJUSTE",
    
    # ===== PERMISSIVOS -> AFASTOU =====
    "AUTORIZOU": "AFASTOU",
    "PERMITIU": "AFASTOU",
    
    # ===== MANUTENCAO EXPLICITA -> MANTEVE =====
    "MANTEVE_DECISAO": "MANTEVE",
    "MANTEVE_JULGAMENTO_IRREGULARIDADE": "MANTEVE",
    "MANTEVE_POSICAO": "MANTEVE",
    "MANTEVE_SITUACAO": "MANTEVE",
    
    # ===== OUTROS/AMBIGUOS -> NAO_CLARO =====
    "NAO_APLICAVEL": "NAO_CLARO",
    "NAO_DETERMINOU": "NAO_CLARO",
    "CONHECIDO": "NAO_CLARO",
    "NAO_CONHECIDO": "NAO_CLARO",
    "PREJUDICADO": "NAO_CLARO",
    "EXTINTO": "NAO_CLARO",
    "REPRESENTACAO_PREJUDICADA": "NAO_CLARO",
    "VALIDACAO_COM_RESSALVA": "DETERMINOU_AJUSTE",
    "JULGAMENTO": "NAO_CLARO",
    "RIGORIZA": "NAO_CLARO",
}

PROCEDURAL_STAGE_MAPPINGS = {
    # ===== VALORES JA VALIDOS =====
    "EDITAL": "EDITAL",
    "DISPUTA": "DISPUTA",
    "JULGAMENTO": "JULGAMENTO",
    "HABILITACAO": "HABILITACAO",
    "CONTRATACAO": "CONTRATACAO",
    "EXECUCAO": "EXECUCAO",
    "PAGAMENTO": "PAGAMENTO",
    "SANCIONAMENTO": "SANCIONAMENTO",
    "NAO_CLARO": "NAO_CLARO",
    
    # ===== PRE-LICITATORIOS -> EDITAL =====
    "LICITACAO": "EDITAL",
    "PRE_LICITACAO": "EDITAL",
    "PRE_LICITATORIO": "EDITAL",
    "PRE-LICITATORIO": "EDITAL",
    "REGULAMENTO": "EDITAL",
    "PUBLICACAO_EDITAL": "EDITAL",
    "ELABORACAO_EDITAL": "EDITAL",
    
    # ===== DISPUTA =====
    "SESSAO_PUBLICA": "DISPUTA",
    "ABERTURA_PROPOSTAS": "DISPUTA",
    "LANCES": "DISPUTA",
    
    # ===== JULGAMENTO =====
    "ANALISE_PROPOSTAS": "JULGAMENTO",
    "CLASSIFICACAO": "JULGAMENTO",
    "DESCLASSIFICACAO": "JULGAMENTO",
    "CERTAME_CONCLUIDO": "JULGAMENTO",
    "RECURSO": "JULGAMENTO",
    "CONSULTA": "JULGAMENTO",
    "DENUNCIA": "JULGAMENTO",
    
    # ===== HABILITACAO =====
    "ANALISE_DOCUMENTOS": "HABILITACAO",
    "INABILITACAO": "HABILITACAO",
    
    # ===== CONTRATACAO =====
    "ASSINATURA_CONTRATO": "CONTRATACAO",
    
    # ===== EXECUCAO =====
    "GESTAO_CONTRATO": "EXECUCAO",
    "FISCALIZACAO": "EXECUCAO",
    "CONTROLE_EXTERNO": "EXECUCAO",
    "EXECUCAO_CONTRATO": "EXECUCAO",
    "EXECUCAO_CONTRATUAL": "EXECUCAO",
    "POS_LICITATORIO": "EXECUCAO",
    "POS-LICITATORIO": "EXECUCAO",
    
    # ===== PAGAMENTO =====
    "LIQUIDACAO": "PAGAMENTO",
    
    # ===== SANCIONAMENTO =====
    "MULTA": "SANCIONAMENTO",
    "PENALIDADE": "SANCIONAMENTO",
    "SUSPENSAO": "SANCIONAMENTO",
    "IMPEDIMENTO": "SANCIONAMENTO",
    
    # ===== OUTROS -> NAO_CLARO =====
    "NAO_APLICAVEL": "NAO_CLARO",
}

EFFECT_MAPPINGS = {
    # ===== VALORES JA VALIDOS =====
    "FLEXIBILIZA": "FLEXIBILIZA",
    "RIGORIZA": "RIGORIZA",
    "CONDICIONAL": "CONDICIONAL",
    
    # ===== MAPEAMENTOS =====
    "FLEXIBILIZACAO": "FLEXIBILIZA",
    "FLEXIVEL": "FLEXIBILIZA",
    "PERMITIU": "FLEXIBILIZA",
    "ADMITIU": "FLEXIBILIZA",
    "AUTORIZOU": "FLEXIBILIZA",
    
    "RIGOR": "RIGORIZA",
    "RIGIDO": "RIGORIZA",
    "EXIGIU": "RIGORIZA",
    "OBRIGOU": "RIGORIZA",
    "VEDOU": "RIGORIZA",
    "PROIBIU": "RIGORIZA",
    "MANDATORIO": "RIGORIZA",
    
    "CONDICAO": "CONDICIONAL",
    "DEPENDE": "CONDICIONAL",
    "DESDE_QUE": "CONDICIONAL",
    "SE": "CONDICIONAL",
    "DIRETO": "CONDICIONAL",
    "NAO_APLICAVEL": "CONDICIONAL",
    "NAO_CLARO": "CONDICIONAL",
}

REMEDY_TYPE_MAPPINGS = {
    # ===== VALORES JA VALIDOS =====
    "IMPUGNACAO": "IMPUGNACAO",
    "RECURSO": "RECURSO",
    "CONTRARRAZOES": "CONTRARRAZOES",
    "REPRESENTACAO": "REPRESENTACAO",
    "DENUNCIA": "DENUNCIA",
    "ORIENTACAO_GERAL": "ORIENTACAO_GERAL",
    "NAO_CLARO": "NAO_CLARO",
    
    # ===== RECURSOS =====
    "PEDIDO_REEXAME": "RECURSO",
    "PEDIDO_DE_REEXAME": "RECURSO",
    "REEXAME": "RECURSO",
    "RECONSIDERACAO": "RECURSO",
    "PEDIDO_RECONSIDERACAO": "RECURSO",
    "EMBARGOS": "RECURSO",
    "EMBARGOS_DECLARACAO": "RECURSO",
    "EMBARGOS_DE_DECLARACAO": "RECURSO",
    "AGRAVO": "RECURSO",
    "REVISAO": "RECURSO",
    
    # ===== ORIENTACAO GERAL =====
    "TOMADA_DE_CONTAS": "ORIENTACAO_GERAL",
    "TOMADA_DE_CONTAS_ESPECIAL": "ORIENTACAO_GERAL",
    "TOMADA_CONTAS_ESPECIAL": "ORIENTACAO_GERAL",
    "TCE": "ORIENTACAO_GERAL",
    "CONSULTA": "ORIENTACAO_GERAL",
    "AUDITORIA": "ORIENTACAO_GERAL",
    "LEVANTAMENTO": "ORIENTACAO_GERAL",
    "MONITORAMENTO": "ORIENTACAO_GERAL",
    "ACOMPANHAMENTO": "ORIENTACAO_GERAL",
    "FISCALIZACAO": "ORIENTACAO_GERAL",
    "DETERMINACAO": "ORIENTACAO_GERAL",
    "DETERMINACAO_ESPECIFICA": "ORIENTACAO_GERAL",
    "ACAO_CORRETIVA": "ORIENTACAO_GERAL",
    "DEBITO": "ORIENTACAO_GERAL",
    "RESSARCIMENTO": "ORIENTACAO_GERAL",
    "RESSARCIMENTO_E_SANCAO": "ORIENTACAO_GERAL",
    "SANCAO": "ORIENTACAO_GERAL",
    "SANCAO_INDIVIDUAL": "ORIENTACAO_GERAL",
    "SANCIONAMENTO": "ORIENTACAO_GERAL",
    
    # ===== REPRESENTACAO =====
    "TCU_REPRESENTACAO": "REPRESENTACAO",
    "MEDIDA_CAUTELAR": "REPRESENTACAO",
    
    # ===== OUTROS =====
    "NAO_APLICAVEL": "NAO_CLARO",
}

SECAO_MAPPINGS = {
    "EMENTARIO": "EMENTA",
    "SUMULA": "EMENTA",
    "FUNDAMENTOS": "FUNDAMENTACAO",
    "MERITO": "FUNDAMENTACAO",
    "ANALISE": "FUNDAMENTACAO",
    "DECISAO": "DISPOSITIVO",
    "ACORDAO": "DISPOSITIVO",
}

# ==============================================================================
# MAPEAMENTO UF -> REGIAO
# ==============================================================================

UF_TO_REGION = {
    # SUDESTE
    "SP": "SUDESTE", "RJ": "SUDESTE", "MG": "SUDESTE", "ES": "SUDESTE",
    # SUL
    "PR": "SUL", "SC": "SUL", "RS": "SUL",
    # NORDESTE
    "BA": "NORDESTE", "PE": "NORDESTE", "CE": "NORDESTE", "MA": "NORDESTE",
    "PB": "NORDESTE", "RN": "NORDESTE", "AL": "NORDESTE", "SE": "NORDESTE", "PI": "NORDESTE",
    # CENTRO-OESTE
    "GO": "CENTRO_OESTE", "MT": "CENTRO_OESTE", "MS": "CENTRO_OESTE", "DF": "CENTRO_OESTE",
    # NORTE
    "AM": "NORTE", "PA": "NORTE", "AC": "NORTE", "RO": "NORTE",
    "RR": "NORTE", "AP": "NORTE", "TO": "NORTE"
}

# ==============================================================================
# AUTHORITY SCORES
# ==============================================================================

AUTHORITY_SCORES = {
    "TCU": 0.90,
    "TCE": 0.80,
}

# ==============================================================================
# FUNCOES DE NORMALIZACAO
# ==============================================================================

def normalize_string(value: str) -> str:
    """Normaliza string para comparacao."""
    if not value:
        return ""
    v = value.strip().upper()
    v = v.replace(" ", "_").replace("-", "_")
    while "__" in v:
        v = v.replace("__", "_")
    return v


def clamp_enum(value: str, valid_set: set, mappings: dict, fallback: str) -> str:
    """Normaliza e clamp um valor para um enum valido."""
    if not value:
        return fallback
    v = normalize_string(value)
    if v in valid_set:
        return v
    if v in mappings:
        return mappings[v]
    return fallback


def clamp_procedural_stage(value: str) -> str:
    return clamp_enum(value, VALID_PROCEDURAL_STAGE, PROCEDURAL_STAGE_MAPPINGS, "NAO_CLARO")


def clamp_holding_outcome(value: str) -> str:
    return clamp_enum(value, VALID_HOLDING_OUTCOME, HOLDING_OUTCOME_MAPPINGS, "NAO_CLARO")


def clamp_remedy_type(value: str) -> str:
    return clamp_enum(value, VALID_REMEDY_TYPE, REMEDY_TYPE_MAPPINGS, "ORIENTACAO_GERAL")


def clamp_effect(value: str) -> str:
    return clamp_enum(value, VALID_EFFECT, EFFECT_MAPPINGS, "CONDICIONAL")


def clamp_secao(value: str) -> str:
    return clamp_enum(value, VALID_SECAO, SECAO_MAPPINGS, "NAO_CLARO")


def normalize_chunk_for_upsert(chunk: dict, tribunal: str = None) -> dict:
    """Normaliza todos os campos enum de um chunk antes do upsert."""
    tribunal = tribunal or chunk.get("tribunal", "").upper()
    normalized = dict(chunk)
    
    if "procedural_stage" in normalized:
        normalized["procedural_stage"] = clamp_procedural_stage(normalized.get("procedural_stage"))
    if "holding_outcome" in normalized:
        normalized["holding_outcome"] = clamp_holding_outcome(normalized.get("holding_outcome"))
    if "remedy_type" in normalized:
        normalized["remedy_type"] = clamp_remedy_type(normalized.get("remedy_type"))
    if "effect" in normalized:
        normalized["effect"] = clamp_effect(normalized.get("effect"))
    # NAO clampar secao - secao de chunk (tese/vital/etc) != secao de acordao (EMENTA/RELATORIO/etc)
    # if "secao" in normalized:
    #     normalized["secao"] = clamp_secao(normalized.get("secao"))
    
    if tribunal == "TCU":
        normalized["uf"] = None
        normalized["region"] = None
    elif tribunal == "TCE":
        uf = normalized.get("uf", "").upper() if normalized.get("uf") else None
        if uf and uf in UF_TO_REGION:
            normalized["region"] = UF_TO_REGION[uf]
    
    if "authority_score" not in normalized or normalized.get("authority_score") is None:
        normalized["authority_score"] = AUTHORITY_SCORES.get(tribunal, 0.80)
    
    return normalized


def validate_chunk_for_upsert(chunk: dict) -> tuple:
    """Valida se chunk pode ser indexado."""
    errors = []
    required = ["chunk_id", "tribunal", "content"]
    for field in required:
        if not chunk.get(field):
            errors.append(f"Campo obrigatorio ausente: {field}")
    
    tribunal = chunk.get("tribunal", "").upper()
    if tribunal == "TCE" and not chunk.get("uf"):
        errors.append("TCE requer uf")
    
    if chunk.get("effect") and chunk["effect"] not in VALID_EFFECT:
        errors.append(f"effect invalido: {chunk['effect']}")
    if chunk.get("procedural_stage") and chunk["procedural_stage"] not in VALID_PROCEDURAL_STAGE:
        errors.append(f"procedural_stage invalido: {chunk['procedural_stage']}")
    if chunk.get("holding_outcome") and chunk["holding_outcome"] not in VALID_HOLDING_OUTCOME:
        errors.append(f"holding_outcome invalido: {chunk['holding_outcome']}")
    if chunk.get("remedy_type") and chunk["remedy_type"] not in VALID_REMEDY_TYPE:
        errors.append(f"remedy_type invalido: {chunk['remedy_type']}")
    
    return (len(errors) == 0, errors)


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    # Sets de enums
    "VALID_DOC_TYPES",
    "VALID_TRIBUNALS",
    "VALID_CHUNK_SECOES",
    "VALID_PROCEDURAL_STAGE",
    "VALID_HOLDING_OUTCOME",
    "VALID_REMEDY_TYPE",
    "VALID_EFFECT",
    "VALID_SECAO",
    # Aliases para compatibilidade
    "PROCEDURAL_STAGES",
    "HOLDING_OUTCOMES",
    "REMEDY_TYPES",
    "EFFECTS",
    # Pistas
    "PISTAS_PROCEDURAL_STAGE",
    "PISTAS_HOLDING_OUTCOME",
    "PISTAS_REMEDY_TYPE",
    "PISTAS_EFFECT",
    # Outras constantes
    "CONFIDENCE_THRESHOLD",
    "REVIEW_QUEUE_DIR",
    # Mapeamentos
    "PROCEDURAL_STAGE_MAPPINGS",
    "HOLDING_OUTCOME_MAPPINGS",
    "REMEDY_TYPE_MAPPINGS",
    "EFFECT_MAPPINGS",
    "SECAO_MAPPINGS",
    "UF_TO_REGION",
    "AUTHORITY_SCORES",
    # Funcoes
    "normalize_string",
    "clamp_enum",
    "clamp_procedural_stage",
    "clamp_holding_outcome",
    "clamp_remedy_type",
    "clamp_effect",
    "clamp_secao",
    "normalize_chunk_for_upsert",
    "validate_chunk_for_upsert",
]