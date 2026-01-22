# govy/extractors/o001_objeto.py
"""
O001 - Extrator de Objeto da Licitacao
VERSAO 2.4 - Correcao de extracao de frase generica + fallback ITENS
Ultima atualizacao: 20/01/2026

CORRECOES v2.4:
- Extrai objeto REAL de frases genericas tipo "contratacao por dispensa de licitacao de [OBJETO]"
- Fallback para ITENS/LOTE quando nao encontra secao OBJETO
- Filtros para rejeitar cabecalhos de orgaos, prazos, documentacao
- Novos STOP_MARKERS
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional, List, Tuple

@dataclass(frozen=True)
class ExtractResult:
    value: Optional[str]
    evidence: Optional[str]
    score: int

@dataclass
class CandidateResult:
    value: str
    score: int
    context: str
    evidence: str

def _limpar_encoding(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\uFFFD", "")
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

def _normalizar_texto(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))

def _is_sumario(text: str) -> bool:
    """Detecta se o texto parece ser um sumario/indice."""
    if not text:
        return False
    matches = re.findall(r'\d+\s*\.\s*[A-Z]', text)
    if len(matches) >= 2:
        return True
    numeros_secao = re.findall(r'(\d+)\s*\.?\s*(?:DA|DO|DAS|DOS|DE)\s+[A-Z]', text)
    if len(numeros_secao) >= 3:
        return True
    return False


# =============================================================================
# NOVO v2.4: FILTROS DE LIXO
# =============================================================================

def _is_lixo(text: str) -> bool:
    """
    Detecta se o texto e lixo (cabecalho, prazo, documentacao, etc.)
    
    Returns:
        True se o texto deve ser rejeitado
    """
    if not text:
        return True
    
    text_lower = text.lower()
    text_norm = _normalizar_texto(text)
    
    # Rejeitar cabecalhos de orgaos
    cabecalhos = [
        "ministerio da defesa",
        "exercito brasileiro",
        "instituto de biologia",
        "camara nacional de modelos",
        "consultoria-geral da uniao",
    ]
    for cab in cabecalhos:
        if cab in text_norm:
            return True
    
    # Rejeitar textos que comecam com padroes de lixo
    lixo_inicio = [
        r'^da\s+contrata',  # "da Contratacao Direta"
        r'^licitado,?\s+contados',  # prazo
        r'^\d+\s*\.\s*\d+',  # "1.1", "2.3" - numeracao solta
        r'^sem\s*motivo\s+justificado',  # documentacao
        r'^apresentar\s+declara',  # documentacao
        r'^aos\s+dias\s+de',  # termo de recebimento
    ]
    for pattern in lixo_inicio:
        if re.match(pattern, text_lower):
            return True
    
    # Rejeitar textos que falam de prazo/dias sem mencionar produto/servico
    if re.search(r'\b\d+\s*(?:dias?|horas?)\b', text_lower):
        # So rejeita se NAO tiver palavras de objeto
        palavras_objeto = ["aquisicao", "contratacao", "servico", "fornecimento", "obra", "compra"]
        tem_objeto = any(p in text_norm for p in palavras_objeto)
        if not tem_objeto:
            return True
    
    return False


# =============================================================================
# NOVO v2.4: EXTRACAO DE OBJETO DE FRASE GENERICA
# =============================================================================

def _extrair_objeto_frase_generica(text: str) -> Optional[str]:
    """
    Extrai o objeto REAL de frases genericas tipo:
    "O objeto da presente dispensa e a escolha da proposta mais vantajosa 
     para a contratacao, por dispensa de licitacao, de [OBJETO REAL], conforme..."
    
    Returns:
        Texto do objeto real ou None
    """
    if not text:
        return None
    
    # Padrao: "contratacao[,] por dispensa de licitacao[,] de [OBJETO]"
    # Captura o que vem depois do ultimo "de" ate "conforme" ou ponto final
    patterns = [
        # Padrao principal com "por dispensa de licitacao"
        r'contrata[cç][aã]o,?\s*por\s+dispensa\s+de\s+licita[cç][aã]o,?\s+de\s+(.+?)(?:,\s*conforme|,\s*nas\s+condi[cç][oõ]es|\.\s*$|\.\s*\d)',
        # Padrao alternativo com "por inexigibilidade"  
        r'contrata[cç][aã]o,?\s*por\s+inexigibilidade,?\s+de\s+(.+?)(?:,\s*conforme|,\s*nas\s*condi[cç][oõ]es|\.\s*$|\.\s*\d)',
        # Padrao mais simples
        r'dispensa\s+de\s+licita[cç][aã]o\s+de\s+(.+?)(?:,\s*conforme|\.\s*$|\.\s*\d)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            objeto = match.group(1).strip()
            # Limpar espacos extras
            objeto = re.sub(r'\s+', ' ', objeto)
            # Remover pontuacao final
            objeto = re.sub(r'[,;:\s]+$', '', objeto)
            if len(objeto) >= 20:
                return objeto
    
    return None


def _extrair_objeto_folha_dados(texto: str) -> Optional[str]:
    """
    Extrai o objeto da secao CGDL 1.1 (Folha de Dados).
    """
    if not texto:
        return None

    pattern = r'CGDL\s*1\.1\s*(?![)\]])\n([A-Z][^\n]*(?:\n(?![A-Z]*CGDL)[^\n]*)*)'

    match = re.search(pattern, texto, re.MULTILINE)
    if match:
        objeto = match.group(1).strip()
        objeto = re.sub(r'\s+', ' ', objeto)
        if len(objeto) > 700:
            objeto = objeto[:700].rstrip() + "..."
        return objeto

    return None


# =============================================================================
# NOVO v2.4: FALLBACK PARA ITENS/LOTE
# =============================================================================

def _extrair_objeto_itens(text: str) -> Optional[str]:
    """
    Fallback: extrai objeto da descricao de ITENS quando nao encontra secao OBJETO.
    
    Busca padroes como:
    - "ITEM 1: descricao do produto"
    - "LOTE 1 - descricao"
    - Tabela com "Descricao" e texto do produto
    
    Returns:
        Texto do objeto ou None
    """
    if not text:
        return None
    
    # Padrao 1: ITEM N: descricao ou ITEM N - descricao
    pattern_item = r'(?:ITEM|LOTE)\s*(?:\d+|[IVX]+)[:\-\s]+([A-Z][^\.]{20,200})'
    match = re.search(pattern_item, text, re.IGNORECASE)
    if match:
        obj = match.group(1).strip()
        obj = re.sub(r'\s+', ' ', obj)
        return obj
    
    # Padrao 2: Servico de / Aquisicao de / Fornecimento de (inicio de frase)
    pattern_servico = r'(?:Servi[cç]o\s+de|Aquisi[cç][aã]o\s+de|Fornecimento\s+de)\s+([^\.]{20,200})'
    match = re.search(pattern_servico, text)
    if match:
        obj = "Servico de " + match.group(1).strip() if "servic" in match.group(0).lower() else match.group(1).strip()
        obj = re.sub(r'\s+', ' ', obj)
        return obj
    
    return None


# =============================================================================
# NOVO v2.4: DETECCAO DE TEXTO GENERICO
# =============================================================================

def _is_texto_generico_objeto(text: str) -> bool:
    """
    Detecta se o texto do objeto e generico.
    """
    if not text:
        return False

    patterns = [
        r'conforme\s+(?:descri[cç][aã]o|especifica[cç][oõ]es?).*(?:ANEXO|FOLHA\s+DE\s+DADOS|CGDL)',
        r'especificad[ao]s?\s+n[oa]\s+ANEXO',
        r'ANEXO\s+IV.*FOLHA\s+DE\s+DADOS',
        r'(?:descri[cç][aã]o|condi[cç][oõ]es)\s+especificadas?\s+no\s+ANEXO',
        # NOVO v2.4: Detectar frase generica "escolha da proposta mais vantajosa"
        r'escolha\s+da\s+proposta\s+mais\s+vantajosa',
        r'objeto\s+d[ao]\s+presente\s+(?:dispensa|procedimento|licita)',
    ]

    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


# =============================================================================
# CONFIGURACOES
# =============================================================================

STOP_MARKERS = [
    "DA JUSTIFICATIVA", "DO VALOR", "DA VIGENCIA", "DAS CONDICOES",
    "DA HABILITACAO", "DO PAGAMENTO", "DA ENTREGA", "DOS PRAZOS",
    "DISPOSICOES GERAIS", "CONFORME TERMO DE REFERENCIA", "ANEXO I",
    "TERMO DE REFERENCIA", "CONDICAO DA PARTICIPACAO", "CONDICOES DE PARTICIPACAO",
    "EXCLUSIVA PARA EPP", "EXCLUSIVA PARA ME", "PARTICIPACAO EXCLUSIVA",
    "CRITERIO DE JULGAMENTO", "MENOR PRECO", "MAIOR DESCONTO",
    "FUNDAMENTACAO LEGAL", "ART. 75", "LEI FEDERAL",
    "INTERVALO MINIMO", "ENVIO DAS PROPOSTAS", "PERIODO DE ENVIO",
    "DATA DA SESSAO", "FASE DE LANCES", "PROCESSO ADMINISTRATIVO",
    "DOTACAO ORCAMENTARIA", "VALOR TOTAL ESTIMADO", "VALOR ESTIMADO",
    "AVISO DE CONTRATACAO DIRETA", "AVISO DE LICITACAO",
    "ESTUDO TECNICO PRELIMINAR", "PRAZO DE VIGENCIA",
    # NOVOS v2.4
    "AOS DIAS DE", "RECEBEMOS EM CARATER", "TERMO DE RECEBIMENTO",
    "CONFORME CONDICOES", "QUANTIDADES E EXIGENCIAS",
    "HAVENDO MAIS DE UM ITEM", "O CRITERIO DE JULGAMENTO",
    "PARTICIPACAO NA DISPENSA", "REGISTRO DE PRECOS",
]

BONUS_TERMS = [
    "contratacao", "aquisicao", "registro de precos", "fornecimento",
    "prestacao de servicos", "servicos", "compra", "obras",
    "manutencao", "instalacao", "confeccao", "reforma",
]

MIN_CONTENT_BEFORE_STOP = 20
MAX_LENGTH = 700


# =============================================================================
# FUNCOES AUXILIARES
# =============================================================================

def _clean_spaces(s: str) -> str:
    s = (s or "").replace("\uFFFD", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def _marker_to_regex(marker: str) -> str:
    marker = marker.strip()
    if not marker:
        return ""
    parts = [re.escape(p) for p in marker.split()]
    return r"\b" + r"\s+".join(parts) + r"\b"

def _stop_at_markers(s: str, min_content_length: int = MIN_CONTENT_BEFORE_STOP) -> str:
    best_cut = len(s)
    for marker in STOP_MARKERS:
        pattern = _marker_to_regex(marker)
        if pattern:
            match = re.search(pattern, s, flags=re.IGNORECASE)
            if match and match.start() >= min_content_length:
                if match.start() < best_cut:
                    best_cut = match.start()
    result = s[:best_cut].strip()
    result = re.sub(r'[,;:\s]+$', '', result)
    return result

def _normalize_object_text(s: str, max_len: int = MAX_LENGTH) -> str:
    s = _clean_spaces(s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > max_len:
        s = s[:max_len].rstrip() + "..."
    return s

def _calcular_similaridade(texto1: str, texto2: str) -> float:
    norm1 = set(_normalizar_texto(texto1).split())
    norm2 = set(_normalizar_texto(texto2).split())
    if not norm1 or not norm2:
        return 0.0
    return len(norm1 & norm2) / len(norm1 | norm2)


# =============================================================================
# EXTRACAO DE CANDIDATOS
# =============================================================================

def _extract_candidates(text: str) -> List[Tuple[str, str, int]]:
    if not text:
        return []
    text = _limpar_encoding(text)
    
    candidates = []
    
    # NOVO v2.4: Primeiro tentar extrair de frase generica
    objeto_frase = _extrair_objeto_frase_generica(text)
    if objeto_frase:
        obj = _normalize_object_text(objeto_frase, max_len=MAX_LENGTH)
        obj = _stop_at_markers(obj)
        if len(obj) >= 30 and not _is_lixo(obj):
            # Score alto porque extraiu o objeto REAL da frase
            candidates.append((obj, obj[:500], 18))
    
    # Padroes tradicionais
    patterns = [
        r'OBJETO\s*[:\-]?\s*([A-Z][^\n]{30,}?)(?=VALOR\s+TOTAL|DATA\s+DA\s+SESS|CRITERIO|PREFERENC|\n{2,}|\Z)',
        r'\bDO\s+OBJETO\b\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)',
        r'OBJETO\s+DA\s+LICITA.{1,2}O\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)',
        r'OBJETO\s+DO\s+CERTAME\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)',
        r'OBJETO\s+DA\s+CONTRATA.{1,3}O\s+DIRETA\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)',
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE | re.DOTALL):
            full_match = match.group(0) or ""
            raw = match.group(1)
            raw = _clean_spaces(raw)
            raw = _stop_at_markers(raw)
            evidence = raw[:500]
            obj = _normalize_object_text(raw, max_len=MAX_LENGTH)

            # FILTRO: Rejeitar sumario
            if _is_sumario(obj):
                continue
            
            # FILTRO v2.4: Rejeitar lixo
            if _is_lixo(obj):
                continue

            # Se o texto e generico, buscar alternativas
            if _is_texto_generico_objeto(obj):
                # Tentar FOLHA DE DADOS
                objeto_real = _extrair_objeto_folha_dados(text)
                if objeto_real:
                    obj = _normalize_object_text(objeto_real, max_len=MAX_LENGTH)
                    evidence = objeto_real[:500]
                    base_score = 15
                else:
                    # Tentar extrair da frase generica
                    objeto_frase = _extrair_objeto_frase_generica(obj)
                    if objeto_frase:
                        obj = _normalize_object_text(objeto_frase, max_len=MAX_LENGTH)
                        evidence = objeto_frase[:500]
                        base_score = 14
                    else:
                        # Nao encontrou alternativa, score baixo
                        base_score = 3
            else:
                base_score = 10

            bonus = 0
            if re.search(r"\b(?:DO\s+)?OBJETO\b", full_match, flags=re.IGNORECASE):
                bonus += 3
            obj_lower = obj.lower()
            for term in BONUS_TERMS:
                if term.lower() in obj_lower:
                    bonus += 2
                    break
            score = base_score + bonus
            if len(obj) >= 40:
                candidates.append((obj, evidence, score))
    
    # FALLBACK v2.4: Se nao encontrou candidatos, tentar ITENS
    if len(candidates) == 0:
        objeto_item = _extrair_objeto_itens(text)
        if objeto_item:
            obj = _normalize_object_text(objeto_item, max_len=MAX_LENGTH)
            if not _is_lixo(obj):
                candidates.append((obj, obj[:500], 8))
    
    return candidates


# =============================================================================
# FUNCOES PUBLICAS
# =============================================================================

def extract_o001_multi(text: str, max_candidatos: int = 3) -> List[CandidateResult]:
    candidates = _extract_candidates(text)
    if not candidates:
        return []
    candidates.sort(key=lambda x: x[2], reverse=True)
    selecionados = []
    for obj, evidence, score in candidates:
        eh_similar = any(_calcular_similaridade(obj, s.value) >= 0.75 for s in selecionados)
        if not eh_similar:
            selecionados.append(CandidateResult(value=obj, score=score, context=evidence, evidence=evidence[:200]))
        if len(selecionados) >= max_candidatos:
            break
    return selecionados

def extract_o001(text: str) -> ExtractResult:
    candidates = _extract_candidates(text)
    if not candidates:
        return ExtractResult(value=None, evidence=None, score=0)
    candidates.sort(key=lambda x: x[2], reverse=True)
    best_obj, best_ev, best_score = candidates[0]
    return ExtractResult(value=best_obj, evidence=best_ev, score=int(best_score))
