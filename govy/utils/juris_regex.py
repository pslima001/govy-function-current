"""
GOVY - Regex Permissivo para Fundamento Legal
SPEC 1.2 - Knowledge Base Jurídica

REGRA CLARÍSSIMA:
- Regex NÃO seleciona jurisprudência
- Regex NÃO seleciona tese/vital
- Regex SÓ decide se vale extrair FUNDAMENTO LEGAL

Se não disparar:
- fundamento_legal = NONE
- não chama IA para este campo
- não inventa lei
"""

import re
from typing import Tuple, List

# Regex AMPLIADO e PERMISSIVO
# Disparar se encontrar qualquer:
# - art. / artigo
# - lei (com ou sem nº, com barra/ano)
# - decreto
# - § / parágrafo único
# - inciso / alínea

FUNDAMENTO_LEGAL_REGEX = re.compile(
    r"(?:"
    r"art(?:igo)?\.?\s*\d+(?:-[A-Z])?"  # art. 62, artigo 63, art. 37-A
    r"|lei\s+(?:n[°º.]?\s*)?[\d.]+(?:/\d+)?"  # Lei 14.133/2021, Lei nº 8.666/93
    r"|lei\s+(?:n[°º.]?\s*)?[\d.]+\s+de\s+\d{4}"  # Lei 14.133 de 2021
    r"|decreto\s+(?:n[°º.]?\s*)?[\d.]+(?:/\d+)?"  # Decreto 10.024/2019
    r"|§\s*\d+[°º]?"  # § 1º, § 2°, § 1
    r"|parágrafo\s+único"  # parágrafo único
    r"|inciso\s+[IVXLCDM]+"  # inciso IV
    r'|alínea\s+["\']?[a-z]["\']?'  # alínea "a", alínea b
    r"|lei\s+complementar"  # Lei Complementar
    r"|medida\s+provisória"  # Medida Provisória
    r"|instrução\s+normativa"  # Instrução Normativa
    r"|súmula\s+(?:n[°º.]?\s*)?\d+"  # Súmula 247
    r"|constituição\s+federal"  # Constituição Federal
    r"|CF/\d{2,4}"  # CF/88
    r"|CRFB/\d{2,4}"  # CRFB/88
    r")",
    re.IGNORECASE,
)


def has_fundamento_legal(text: str) -> Tuple[bool, List[str]]:
    """
    Verifica se o texto contém referências a fundamentos legais.

    Args:
        text: Texto completo da jurisprudência

    Returns:
        Tuple[bool, List[str]]: (disparou_regex, lista_de_matches)

    Exemplo:
        >>> has_fundamento_legal("Conforme art. 62 da Lei 14.133/2021...")
        (True, ['art. 62', 'Lei 14.133/2021'])

        >>> has_fundamento_legal("O licitante foi inabilitado por falta de documentos.")
        (False, [])
    """
    if not text:
        return False, []

    matches = FUNDAMENTO_LEGAL_REGEX.findall(text)

    # Remove duplicatas mantendo ordem
    unique_matches = []
    seen = set()
    for match in matches:
        match_lower = match.lower().strip()
        if match_lower not in seen:
            seen.add(match_lower)
            unique_matches.append(match.strip())

    return len(unique_matches) > 0, unique_matches


def extract_legal_references(text: str) -> dict:
    """
    Extrai e categoriza referências legais do texto.

    Returns:
        dict com categorias: artigos, leis, decretos, paragrafos, incisos, alineas, sumulas
    """
    if not text:
        return {"found": False, "references": {}}

    patterns = {
        "artigos": re.compile(r"art(?:igo)?\.?\s*\d+(?:-[A-Z])?", re.IGNORECASE),
        "leis": re.compile(
            r"lei\s+(?:n[°º.]?\s*)?[\d.]+(?:/\d+|\s+de\s+\d{4})?", re.IGNORECASE
        ),
        "decretos": re.compile(
            r"decreto\s+(?:n[°º.]?\s*)?[\d.]+(?:/\d+)?", re.IGNORECASE
        ),
        "paragrafos": re.compile(r"(?:§\s*\d+[°º]?|parágrafo\s+único)", re.IGNORECASE),
        "incisos": re.compile(r"inciso\s+[IVXLCDM]+", re.IGNORECASE),
        "alineas": re.compile(r'alínea\s+["\']?[a-z]["\']?', re.IGNORECASE),
        "sumulas": re.compile(r"súmula\s+(?:n[°º.]?\s*)?\d+", re.IGNORECASE),
        "constituicao": re.compile(
            r"(?:constituição\s+federal|CF/\d{2,4}|CRFB/\d{2,4})", re.IGNORECASE
        ),
    }

    references = {}
    total_found = 0

    for category, pattern in patterns.items():
        matches = pattern.findall(text)
        if matches:
            # Remove duplicatas
            unique = list(dict.fromkeys(m.strip() for m in matches))
            references[category] = unique
            total_found += len(unique)

    return {"found": total_found > 0, "total": total_found, "references": references}


# =============================================================================
# TESTES
# =============================================================================

if __name__ == "__main__":
    # Testes básicos
    test_cases = [
        ("Conforme art. 62 da Lei 14.133/2021, é vedado...", True),
        ("O § 1º do artigo 63 determina que...", True),
        ("Lei nº 8.666/93, inciso IV, alínea 'a'", True),
        ("Decreto 10.024/2019 regulamenta...", True),
        ("Súmula 247 do TCU estabelece...", True),
        ("parágrafo único do art. 75", True),
        ("O licitante foi inabilitado por falta de documentos.", False),
        ("A empresa não comprovou capacidade técnica.", False),
        ("Conforme entendimento consolidado do TCU...", False),
    ]

    print("=" * 60)
    print("TESTE DO REGEX PERMISSIVO - FUNDAMENTO LEGAL")
    print("=" * 60)

    for text, expected in test_cases:
        result, matches = has_fundamento_legal(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} Esperado: {expected}, Obtido: {result}")
        print(f"   Texto: {text[:50]}...")
        if matches:
            print(f"   Matches: {matches}")
        print()

    print("=" * 60)
    print("TESTE DE EXTRAÇÃO CATEGORIZADA")
    print("=" * 60)

    texto_completo = """
    Conforme art. 62, § 1º, inciso IV, alínea "a" da Lei 14.133/2021,
    combinado com o art. 37 da Constituição Federal e a Súmula 247 do TCU,
    bem como o Decreto 10.024/2019, é necessário observar o parágrafo único
    do artigo 75 da Lei nº 8.666/93.
    """

    refs = extract_legal_references(texto_completo)
    print(f"Encontrado: {refs['found']}")
    print(f"Total: {refs['total']}")
    for cat, items in refs["references"].items():
        print(f"  {cat}: {items}")
