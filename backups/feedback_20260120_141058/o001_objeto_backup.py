# govy/extractors/o001_objeto.py
"""
O001 - Extrator de Objeto da Licitação

Este arquivo contém TODAS as regras para extração do objeto da licitação.
Para editar regras, modifique as listas abaixo.

Última atualização: 16/01/2026
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass(frozen=True)
class ExtractResult:
    """Resultado da extração de um parâmetro."""
    value: Optional[str]
    evidence: Optional[str]
    score: int


# =============================================================================
# CONFIGURAÇÃO DE REGRAS - EDITE AQUI
# =============================================================================

# Marcadores que indicam FIM da seção de objeto (seções seguintes)
STOP_MARKERS = [
    # Seções típicas de edital
    "DA JUSTIFICATIVA",
    "DO VALOR",
    "DA VIGÊNCIA",
    "DA VIGENCIA",
    "DAS CONDIÇÕES",
    "DAS CONDICOES",
    "DA HABILITAÇÃO",
    "DA HABILITACAO",
    "DO PAGAMENTO",
    "DA ENTREGA",
    "DOS PRAZOS",
    "DISPOSIÇÕES GERAIS",
    "DISPOSICOES GERAIS",
    # Referências a anexos
    "CONFORME TERMO DE REFERÊNCIA",
    "CONFORME TERMO DE REFERENCIA",
    "ANEXO I",
    "TERMO DE REFERÊNCIA",
    "TERMO DE REFERENCIA",
    # Condições de participação
    "CONDIÇÃO DA PARTICIPAÇÃO",
    "CONDICAO DA PARTICIPACAO",
    "CONDIÇÕES DE PARTICIPAÇÃO",
    "CONDICOES DE PARTICIPACAO",
    "EXCLUSIVA PARA EPP",
    "EXCLUSIVA PARA ME",
    "PARTICIPAÇÃO EXCLUSIVA",
    "PARTICIPACAO EXCLUSIVA",
    # Critérios de julgamento
    "CRITÉRIO DE JULGAMENTO",
    "CRITERIO DE JULGAMENTO",
    "MENOR PREÇO",
    "MENOR PRECO",
    "MAIOR DESCONTO",
    # Fundamentação legal
    "FUNDAMENTAÇÃO LEGAL",
    "FUNDAMENTACAO LEGAL",
    "ART. 75",
    "LEI FEDERAL",
    "LEI Nº 14.133",
    "LEI N 14.133",
    # Prazos e datas
    "INTERVALO MÍNIMO",
    "INTERVALO MINIMO",
    "ENVIO DAS PROPOSTAS",
    "PERÍODO DE ENVIO",
    "PERIODO DE ENVIO",
    "PERÍODO DE LANCES",
    "PERIODO DE LANCES",
    "PERÍODO DE PROPOSTAS",
    "PERIODO DE PROPOSTAS",
    "DATA DA SESSÃO",
    "DATA DA SESSAO",
    "HORÁRIO DA FASE",
    "HORARIO DA FASE",
    "FASE DE LANCES",
    # Informações administrativas
    "PROCESSO ADMINISTRATIVO",
    "DOTAÇÃO ORÇAMENTÁRIA",
    "DOTACAO ORCAMENTARIA",
    "RECURSO ORÇAMENTÁRIO",
    "RECURSO ORCAMENTARIO",
    # Divisão do objeto
    "A AQUISIÇÃO SERÁ",
    "A AQUISICAO SERA",
    "A AQUISIÇÃO SERÁ DIVIDIDA",
    "A AQUISICAO SERA DIVIDIDA",
    "SERÁ DIVIDIDA EM",
    "SERA DIVIDIDA EM",
    # Valores estimados
    "VALOR TOTAL ESTIMADO",
    "VALOR ESTIMADO",
    "VALOR MÁXIMO",
    "VALOR MAXIMO",
    # Cabeçalhos institucionais (quando aparecem após o título)
    "MINISTÉRIO DA DEFESA",
    "MINISTERIO DA DEFESA",
    "EXÉRCITO BRASILEIRO",
    "EXERCITO BRASILEIRO",
    "AVISO DE CONTRATAÇÃO DIRETA",
    "AVISO DE CONTRATACAO DIRETA",
    "AVISO DE LICITAÇÃO",
    "AVISO DE LICITACAO",
    # Estudo técnico e vigência
    "ESTUDO TÉCNICO PRELIMINAR",
    "ESTUDO TECNICO PRELIMINAR",
    "PRAZO DE VIGÊNCIA",
    "PRAZO DE VIGENCIA",
    # Declarações e termos técnicos (ruído)
    "DECLARAÇÃO FORMAL",
    "DECLARACAO FORMAL",
    "RESPONSÁVEL TÉCNICO",
    "RESPONSAVEL TECNICO",
    "CONHECIMENTO PLENO",
    "LICITANTE ACERCA",
    "PODERÁ SER SUBSTITUÍDA",
    "PODERA SER SUBSTITUIDA",
]

# Termos que dão BÔNUS na pontuação
BONUS_TERMS = [
    "contratação",
    "contratacao",
    "aquisição",
    "aquisicao",
    "registro de preços",
    "registro de precos",
    "fornecimento",
    "prestação de serviços",
    "prestacao de servicos",
    "serviços",
    "servicos",
]

# Comprimento mínimo de conteúdo antes de aceitar um STOP_MARKER
MIN_CONTENT_BEFORE_STOP = 20

# Comprimento máximo do objeto extraído
MAX_LENGTH = 700

# =============================================================================
# FUNÇÕES DE EXTRAÇÃO - NÃO EDITE ABAIXO DESTA LINHA
# =============================================================================

def _clean_spaces(s: str) -> str:
    """Remove espaços excessivos e caracteres inválidos."""
    s = (s or "").replace("\uFFFD", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _marker_to_regex(marker: str) -> str:
    """Converte um marcador de texto em padrão regex."""
    marker = marker.strip()
    if not marker:
        return ""
    parts = [re.escape(p) for p in marker.split()]
    return r"\b" + r"\s+".join(parts) + r"\b"


def _stop_at_markers(s: str, min_content_length: int = MIN_CONTENT_BEFORE_STOP) -> str:
    """
    Corta o texto do objeto quando encontra marcadores de seções seguintes.
    
    Proteção: Só corta se já tiver capturado conteúdo mínimo antes do marcador,
    evitando cortes incorretos quando o marcador aparece antes do objeto.
    
    Args:
        s: Texto a ser processado
        min_content_length: Mínimo de caracteres antes de aceitar um corte
        
    Returns:
        Texto truncado no primeiro marcador válido encontrado
    """
    best_cut = len(s)  # Por padrão, não corta
    
    for marker in STOP_MARKERS:
        pattern = _marker_to_regex(marker)
        if pattern:
            match = re.search(pattern, s, flags=re.IGNORECASE)
            if match and match.start() >= min_content_length:
                # Só considera se tiver pelo menos min_content_length chars antes
                if match.start() < best_cut:
                    best_cut = match.start()
    
    result = s[:best_cut].strip()
    
    # Remove pontuação final indesejada (vírgula, ponto-e-vírgula)
    result = re.sub(r'[,;:\s]+$', '', result)
    
    return result


def _normalize_object_text(s: str, max_len: int = MAX_LENGTH) -> str:
    """Normaliza e trunca o texto do objeto."""
    s = _clean_spaces(s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[:max_len].rstrip() + "..."
    return s


def _extract_candidates(text: str) -> List[Tuple[str, str, int]]:
    """
    Extrai candidatos de objeto do texto.

    Returns:
        Lista de tuplas (objeto_normalizado, evidencia_curta, score)
    """
    if not text:
        return []

    # Padrões para encontrar o objeto
    patterns = [
        r"\b(?:DO\s+)?OBJETO\b\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)",
        r"\bOBJETO\s+DA\s+LICITA[ÇC][ÃA]O\b\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)",
        r"\bOBJETO\s+DO\s+CERTAME\b\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)",
    ]

    candidates: List[Tuple[str, str, int]] = []

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            full_match = match.group(0) or ""
            raw = match.group(1)
            raw = _clean_spaces(raw)
            raw = _stop_at_markers(raw)

            # Evidência curta (até 500 chars)
            evidence = raw[:500]
            obj = _normalize_object_text(raw, max_len=MAX_LENGTH)

            # Calcular pontuação
            base_score = 10
            bonus = 0

            # Bônus se contém "OBJETO" explícito
            if re.search(r"\b(?:DO\s+)?OBJETO\b", full_match, flags=re.IGNORECASE):
                bonus += 3
            if re.search(r"\b(?:DO\s+)?OBJETO\b", raw, flags=re.IGNORECASE):
                bonus += 3

            # Bônus por termos típicos
            obj_lower = obj.lower()
            for term in BONUS_TERMS:
                if term.lower() in obj_lower:
                    bonus += 2
                    break  # Só um bônus por termo

            score = base_score + bonus

            # Só aceita se tiver tamanho mínimo
            if len(obj) >= 40:
                candidates.append((obj, evidence, score))

    return candidates


def extract_o001(text: str) -> ExtractResult:
    """
    Extrai o objeto da licitação do texto.

    Estratégia:
    1. Procura padrões como "OBJETO:", "DO OBJETO", etc.
    2. Corta quando encontra seções seguintes (JUSTIFICATIVA, VALOR, etc.)
    3. Pontua baseado em termos típicos de objeto
    4. Retorna o candidato com maior pontuação

    Args:
        text: Texto completo do documento

    Returns:
        ExtractResult com valor, evidência e score
    """
    if not text:
        return ExtractResult(value=None, evidence=None, score=0)

    candidates = _extract_candidates(text)

    if not candidates:
        return ExtractResult(value=None, evidence=None, score=0)

    # Ordenar por score (maior primeiro)
    candidates.sort(key=lambda x: x[2], reverse=True)

    best_obj, best_ev, best_score = candidates[0]

    return ExtractResult(
        value=best_obj,
        evidence=best_ev,
        score=int(best_score)
    )