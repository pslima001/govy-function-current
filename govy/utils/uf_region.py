# govy/utils/uf_region.py
"""
Mapeamento UF -> REGION para Knowledge Base Juridica GOVY
Versao: 1.0
"""

UF_TO_REGION = {
    # SUDESTE
    "SP": "SUDESTE", "RJ": "SUDESTE", "MG": "SUDESTE", "ES": "SUDESTE",
    # SUL
    "PR": "SUL", "SC": "SUL", "RS": "SUL",
    # NORDESTE
    "AL": "NORDESTE", "BA": "NORDESTE", "CE": "NORDESTE", "MA": "NORDESTE",
    "PB": "NORDESTE", "PE": "NORDESTE", "PI": "NORDESTE", "RN": "NORDESTE", "SE": "NORDESTE",
    # CENTRO-OESTE
    "DF": "CENTRO_OESTE", "GO": "CENTRO_OESTE", "MT": "CENTRO_OESTE", "MS": "CENTRO_OESTE",
    # NORTE
    "AC": "NORTE", "AM": "NORTE", "AP": "NORTE", "PA": "NORTE", 
    "RO": "NORTE", "RR": "NORTE", "TO": "NORTE"
}

VALID_REGIONS = {"SUDESTE", "SUL", "NORDESTE", "CENTRO_OESTE", "NORTE"}
VALID_EFFECTS = {"FLEXIBILIZA", "RIGORIZA", "CONDICIONAL"}
VALID_TRIBUNALS = {"TCU", "TCE"}

# Mapeamento scenario -> desired_effect
SCENARIO_TO_EFFECT = {
    1: "FLEXIBILIZA",
    2: "RIGORIZA",
    3: "FLEXIBILIZA",
    4: "RIGORIZA",
}


def get_region(uf):
    """Retorna a regiao para uma UF."""
    if not uf:
        return None
    return UF_TO_REGION.get(uf.upper())


def get_desired_effect(scenario):
    """Retorna o efeito desejado para um cenario."""
    return SCENARIO_TO_EFFECT.get(scenario)


def validate_jurisprudencia(chunk):
    """
    Valida um chunk de jurisprudencia.
    
    Regras:
    - effect obrigatorio
    - tribunal obrigatorio
    - Se tribunal = TCE: uf e region obrigatorios
    - Se tribunal = TCU: uf e region devem ser null
    
    Returns:
        Lista de erros (vazia se valido)
    """
    errors = []
    
    effect = chunk.get("effect")
    if not effect:
        errors.append("Campo 'effect' obrigatorio para jurisprudencia")
    elif effect not in VALID_EFFECTS:
        errors.append(f"Campo 'effect' invalido: {effect}. Valores aceitos: {list(VALID_EFFECTS)}")
    
    tribunal = chunk.get("tribunal")
    if not tribunal:
        errors.append("Campo 'tribunal' obrigatorio para jurisprudencia")
    elif tribunal not in VALID_TRIBUNALS:
        errors.append(f"Campo 'tribunal' invalido: {tribunal}. Valores aceitos: {list(VALID_TRIBUNALS)}")
    else:
        uf = chunk.get("uf")
        region = chunk.get("region")
        
        if tribunal == "TCE":
            if not uf:
                errors.append("Campo 'uf' obrigatorio para tribunal=TCE")
            elif uf.upper() not in UF_TO_REGION:
                errors.append(f"Campo 'uf' invalido: {uf}")
            
            if not region:
                errors.append("Campo 'region' obrigatorio para tribunal=TCE")
            elif region not in VALID_REGIONS:
                errors.append(f"Campo 'region' invalido: {region}. Valores aceitos: {list(VALID_REGIONS)}")
            
            if uf and region:
                expected_region = get_region(uf)
                if expected_region and expected_region != region:
                    errors.append(f"UF {uf} deveria ter region={expected_region}, nao {region}")
        
        elif tribunal == "TCU":
            if uf:
                errors.append("Campo 'uf' deve ser null para tribunal=TCU")
            if region:
                errors.append("Campo 'region' deve ser null para tribunal=TCU")
    
    return errors
