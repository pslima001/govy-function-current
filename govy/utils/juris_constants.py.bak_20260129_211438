# juris_constants.py - Constantes e Enums para KB Juridica GOVY
# Versao: 1.0 | Data: 29/01/2026

"""
Este modulo define os enums validos para classificacao de jurisprudencia
e funcoes de normalizacao/clamp para garantir valores consistentes.

REGRA DE OURO: Melhor NAO_CLARO do que valor inventado.
"""

# ==============================================================================
# ENUMS VALIDOS (SPEC 1.2)
# ==============================================================================

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
# MAPEAMENTOS DE NORMALIZACAO
# Termos comuns fora do enum -> valor valido
# ==============================================================================

PROCEDURAL_STAGE_MAPPINGS = {
    # Variacoes de escrita
    "LICITACAO": "EDITAL",
    "PRE_LICITATORIO": "EDITAL",
    "PRE-LICITATORIO": "EDITAL",
    "POS_LICITATORIO": "EXECUCAO",
    "POS-LICITATORIO": "EXECUCAO",
    "HABILITAÇÃO": "HABILITACAO",
    "CONTRATAÇÃO": "CONTRATACAO",
    "EXECUÇÃO": "EXECUCAO",
    "SANCIONAMENTO": "SANCIONAMENTO",
    
    # Termos relacionados
    "PUBLICACAO_EDITAL": "EDITAL",
    "ELABORACAO_EDITAL": "EDITAL",
    "SESSAO_PUBLICA": "DISPUTA",
    "ABERTURA_PROPOSTAS": "DISPUTA",
    "LANCES": "DISPUTA",
    "ANALISE_PROPOSTAS": "JULGAMENTO",
    "CLASSIFICACAO": "JULGAMENTO",
    "DESCLASSIFICACAO": "JULGAMENTO",
    "ANALISE_DOCUMENTOS": "HABILITACAO",
    "INABILITACAO": "HABILITACAO",
    "ASSINATURA_CONTRATO": "CONTRATACAO",
    "GESTAO_CONTRATO": "EXECUCAO",
    "FISCALIZACAO": "EXECUCAO",
    "LIQUIDACAO": "PAGAMENTO",
    "MULTA": "SANCIONAMENTO",
    "PENALIDADE": "SANCIONAMENTO",
    "SUSPENSAO": "SANCIONAMENTO",
    "IMPEDIMENTO": "SANCIONAMENTO",
}

HOLDING_OUTCOME_MAPPINGS = {
    # Termos do TCU
    "JULGOU_IRREGULARES": "MANTEVE",
    "JULGOU_REGULARES": "MANTEVE",
    "JULGOU_REGULARES_COM_RESSALVA": "DETERMINOU_AJUSTE",
    "APLICOU_MULTA": "MANTEVE",
    "DETERMINOU": "DETERMINOU_AJUSTE",
    "RECOMENDOU": "DETERMINOU_AJUSTE",
    "NULIDADE": "ANULOU",
    "DECLAROU_NULIDADE": "ANULOU",
    "ANULACAO": "ANULOU",
    "CANCELOU": "ANULOU",
    "REVOGOU": "ANULOU",
    "SUSPENDEU": "DETERMINOU_AJUSTE",
    
    # Termos genericos
    "PROCEDENTE": "MANTEVE",
    "IMPROCEDENTE": "AFASTOU",
    "PARCIALMENTE_PROCEDENTE": "DETERMINOU_AJUSTE",
    "PARCIAL": "DETERMINOU_AJUSTE",
    "PROVIDO": "MANTEVE",
    "IMPROVIDO": "AFASTOU",
    "PARCIALMENTE_PROVIDO": "DETERMINOU_AJUSTE",
    "CONHECIDO": "NAO_CLARO",  # Conhecer nao e decidir merito
    "NAO_CONHECIDO": "NAO_CLARO",
    "PREJUDICADO": "NAO_CLARO",
    "EXTINTO": "NAO_CLARO",
}

REMEDY_TYPE_MAPPINGS = {
    # Termos do TCU
    "TOMADA_DE_CONTAS": "ORIENTACAO_GERAL",
    "TOMADA_DE_CONTAS_ESPECIAL": "ORIENTACAO_GERAL",
    "TCE": "ORIENTACAO_GERAL",
    "CONSULTA": "ORIENTACAO_GERAL",
    "AUDITORIA": "ORIENTACAO_GERAL",
    "LEVANTAMENTO": "ORIENTACAO_GERAL",
    "MONITORAMENTO": "ORIENTACAO_GERAL",
    "ACOMPANHAMENTO": "ORIENTACAO_GERAL",
    "TCU_REPRESENTACAO": "REPRESENTACAO",
    "REPRESENTAÇÃO": "REPRESENTACAO",
    "DENÚNCIA": "DENUNCIA",
    "IMPUGNAÇÃO": "IMPUGNACAO",
    "CONTRARRAZÕES": "CONTRARRAZOES",
    
    # Recursos
    "PEDIDO_REEXAME": "RECURSO",
    "PEDIDO_DE_REEXAME": "RECURSO",
    "RECONSIDERACAO": "RECURSO",
    "PEDIDO_RECONSIDERACAO": "RECURSO",
    "EMBARGOS": "RECURSO",
    "EMBARGOS_DECLARACAO": "RECURSO",
    "AGRAVO": "RECURSO",
    "REVISAO": "RECURSO",
}

EFFECT_MAPPINGS = {
    "FLEXIBILIZACAO": "FLEXIBILIZA",
    "FLEXÍVEL": "FLEXIBILIZA",
    "PERMITIU": "FLEXIBILIZA",
    "ADMITIU": "FLEXIBILIZA",
    "AUTORIZOU": "FLEXIBILIZA",
    "RIGOR": "RIGORIZA",
    "RIGIDO": "RIGORIZA",
    "EXIGIU": "RIGORIZA",
    "OBRIGOU": "RIGORIZA",
    "VEDOU": "RIGORIZA",
    "PROIBIU": "RIGORIZA",
    "CONDICAO": "CONDICIONAL",
    "DEPENDE": "CONDICIONAL",
    "DESDE_QUE": "CONDICIONAL",
    "SE": "CONDICIONAL",
}

SECAO_MAPPINGS = {
    "EMENTARIO": "EMENTA",
    "SÚMULA": "EMENTA",
    "SUMULA": "EMENTA",
    "RELATÓRIO": "RELATORIO",
    "FUNDAMENTAÇÃO": "FUNDAMENTACAO",
    "FUNDAMENTOS": "FUNDAMENTACAO",
    "MERITO": "FUNDAMENTACAO",
    "ANALISE": "FUNDAMENTACAO",
    "DECISÃO": "DISPOSITIVO",
    "DECISAO": "DISPOSITIVO",
    "ACORDAO": "DISPOSITIVO",
    "ACÓRDÃO": "DISPOSITIVO",
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
    """
    Normaliza string para comparacao:
    - Remove espacos extras
    - Uppercase
    - Substitui espacos e hifens por underscore
    - Remove acentos (basico)
    """
    if not value:
        return ""
    
    # Uppercase e strip
    v = value.strip().upper()
    
    # Substituir espacos e hifens por underscore
    v = v.replace(" ", "_").replace("-", "_")
    
    # Remover underscores duplicados
    while "__" in v:
        v = v.replace("__", "_")
    
    # Remover acentos comuns (basico)
    acentos = {
        "Á": "A", "À": "A", "Ã": "A", "Â": "A",
        "É": "E", "È": "E", "Ê": "E",
        "Í": "I", "Ì": "I", "Î": "I",
        "Ó": "O", "Ò": "O", "Õ": "O", "Ô": "O",
        "Ú": "U", "Ù": "U", "Û": "U",
        "Ç": "C",
    }
    for acentuado, sem_acento in acentos.items():
        v = v.replace(acentuado, sem_acento)
    
    return v


def clamp_enum(value: str, valid_set: set, mappings: dict, fallback: str) -> str:
    """
    Normaliza e clamp um valor para um enum valido.
    
    Ordem de decisao:
    1. Se valor vazio -> fallback
    2. Se valor normalizado esta no valid_set -> usa direto
    3. Se valor normalizado esta nos mappings -> usa mapeamento
    4. Se nada funcionou -> fallback
    
    Args:
        value: Valor a normalizar
        valid_set: Set de valores validos
        mappings: Dict de mapeamentos conhecidos
        fallback: Valor padrao se nao encontrar
    
    Returns:
        Valor normalizado e valido
    """
    if not value:
        return fallback
    
    v = normalize_string(value)
    
    # Ja e valido?
    if v in valid_set:
        return v
    
    # Tem mapeamento?
    if v in mappings:
        return mappings[v]
    
    # Fallback
    return fallback


def clamp_procedural_stage(value: str) -> str:
    """Normaliza procedural_stage para enum valido."""
    return clamp_enum(
        value,
        VALID_PROCEDURAL_STAGE,
        PROCEDURAL_STAGE_MAPPINGS,
        "NAO_CLARO"
    )


def clamp_holding_outcome(value: str) -> str:
    """Normaliza holding_outcome para enum valido."""
    return clamp_enum(
        value,
        VALID_HOLDING_OUTCOME,
        HOLDING_OUTCOME_MAPPINGS,
        "NAO_CLARO"
    )


def clamp_remedy_type(value: str) -> str:
    """Normaliza remedy_type para enum valido."""
    return clamp_enum(
        value,
        VALID_REMEDY_TYPE,
        REMEDY_TYPE_MAPPINGS,
        "ORIENTACAO_GERAL"
    )


def clamp_effect(value: str) -> str:
    """Normaliza effect para enum valido."""
    return clamp_enum(
        value,
        VALID_EFFECT,
        EFFECT_MAPPINGS,
        "CONDICIONAL"
    )


def clamp_secao(value: str) -> str:
    """Normaliza secao para enum valido."""
    return clamp_enum(
        value,
        VALID_SECAO,
        SECAO_MAPPINGS,
        "NAO_CLARO"
    )


def normalize_chunk_for_upsert(chunk: dict, tribunal: str = None) -> dict:
    """
    Normaliza todos os campos enum de um chunk antes do upsert.
    
    Tambem garante:
    - TCU: uf=None, region=None
    - TCE: region derivada de uf
    
    Args:
        chunk: Dicionario com dados do chunk
        tribunal: "TCU" ou "TCE" (se nao informado, usa chunk["tribunal"])
    
    Returns:
        Chunk normalizado
    """
    tribunal = tribunal or chunk.get("tribunal", "").upper()
    
    # Clonar para nao modificar original
    normalized = dict(chunk)
    
    # Normalizar enums
    if "procedural_stage" in normalized:
        normalized["procedural_stage"] = clamp_procedural_stage(normalized.get("procedural_stage"))
    
    if "holding_outcome" in normalized:
        normalized["holding_outcome"] = clamp_holding_outcome(normalized.get("holding_outcome"))
    
    if "remedy_type" in normalized:
        normalized["remedy_type"] = clamp_remedy_type(normalized.get("remedy_type"))
    
    if "effect" in normalized:
        normalized["effect"] = clamp_effect(normalized.get("effect"))
    
    if "secao" in normalized:
        normalized["secao"] = clamp_secao(normalized.get("secao"))
    
    # Garantir uf/region corretos por tribunal
    if tribunal == "TCU":
        normalized["uf"] = None
        normalized["region"] = None
    elif tribunal == "TCE":
        uf = normalized.get("uf", "").upper() if normalized.get("uf") else None
        if uf and uf in UF_TO_REGION:
            normalized["region"] = UF_TO_REGION[uf]
        else:
            # Se TCE sem UF valida, marcar como erro
            normalized["_validation_error"] = f"TCE sem UF valida: {uf}"
    
    # Authority score
    if "authority_score" not in normalized or normalized.get("authority_score") is None:
        normalized["authority_score"] = AUTHORITY_SCORES.get(tribunal, 0.80)
    
    return normalized


def validate_chunk_for_upsert(chunk: dict) -> tuple:
    """
    Valida se chunk pode ser indexado.
    
    Returns:
        (is_valid: bool, errors: list[str])
    """
    errors = []
    
    # Campos obrigatorios
    required = ["chunk_id", "tribunal", "content"]
    for field in required:
        if not chunk.get(field):
            errors.append(f"Campo obrigatorio ausente: {field}")
    
    tribunal = chunk.get("tribunal", "").upper()
    
    # Validacao por tribunal
    if tribunal == "TCE":
        if not chunk.get("uf"):
            errors.append("TCE requer uf")
    
    # Validar enums
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
    "VALID_PROCEDURAL_STAGE",
    "VALID_HOLDING_OUTCOME",
    "VALID_REMEDY_TYPE",
    "VALID_EFFECT",
    "VALID_SECAO",
    
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
