# govy/extractors/o001_objeto.py
"""
O001 - Extrator de Objeto da Licitacao
VERSAO 2.0 - Retorna TOP 3 candidatos distintos para avaliacao por LLMs
Ultima atualizacao: 19/01/2026
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
]

BONUS_TERMS = [
    "contratacao", "aquisicao", "registro de precos", "fornecimento",
    "prestacao de servicos", "servicos", "compra", "obras",
]

MIN_CONTENT_BEFORE_STOP = 20
MAX_LENGTH = 700

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

def _extract_candidates(text: str) -> List[Tuple[str, str, int]]:
    if not text:
        return []
    text = _limpar_encoding(text)
    patterns = [
        r'OBJETO\s*[:\-]?\s*([A-Z][^\n]{30,}?)(?=VALOR\s+TOTAL|DATA\s+DA\s+SESS|CRITERIO|PREFERENC|\n{2,}|\Z)',
        r'\bDO\s+OBJETO\b\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)',
        r'OBJETO\s+DA\s+LICITA.{1,2}O\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)',
        r'OBJETO\s+DO\s+CERTAME\s*[:\-]?\s*(.+?)(?=\n{2,}|\Z)',
    ]
    candidates = []
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
    return candidates

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
