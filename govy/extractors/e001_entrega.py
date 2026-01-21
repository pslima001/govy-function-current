# govy/extractors/e001_entrega.py
"""
E001 - Extrator de Prazo de Entrega
VERSAO 2.1 - Correcao: penalizar "inicio da execucao" vs "prazo de entrega/conclusao"
Ultima atualizacao: 21/01/2026
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional, List

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

def _normalizar_texto(s: str) -> str:
    if not s:
        return ""
    s = s.lower()
    return "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))

def _limpar_encoding(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()

TERMOS_POSITIVOS = [
    "entrega", "entregar", "fornecimento", "fornecer", "execucao", "prestacao",
    "servico", "produto", "material", "objeto", "contrato", "adjudicado",
    "prazo de entrega", "prazo de fornecimento", "condicoes de entrega",
    "concluido", "conclusao", "prazo de realizacao", "nota de empenho",
    "ordem de servico", "autorizacao de fornecimento", "deverao ser executados",
    "cronograma", "prazo para conclusao", "prazo de conclusao",
]

TERMOS_NEGATIVOS = [
    "pagamento", "pagar", "liquidacao", "nota fiscal", "fatura", "empenho",
    "atesto", "recurso", "impugna", "vigencia", "validade", "garantia",
    "proposta", "dotacao", "orcamentaria", "assinatura do contrato",
    "convocacao", "adjudicacao", "homologacao", "credenciamento",
    "inicio da execucao", "inicio do objeto", "inicio de execucao",
    "recebimento provisorio", "recebidos provisoriamente",
    "recebimento definitivo", "recebidos definitivamente",
]

REGEX_PRINCIPAL = r"(\d{1,3})\s*(?:\([^\)]{0,30}\))?\s*dias?\s*(?:uteis|corridos)?"
THRESHOLD_SCORE = 2
PESO_POSITIVO = 2
PESO_NEGATIVO = 3
BONUS_FRASE_TIPICA = 3

def _calcular_similaridade(texto1: str, texto2: str) -> float:
    norm1 = set(_normalizar_texto(texto1).split())
    norm2 = set(_normalizar_texto(texto2).split())
    if not norm1 or not norm2:
        return 0.0
    return len(norm1 & norm2) / len(norm1 | norm2)

def extract_e001_multi(text: str, max_candidatos: int = 3) -> List[CandidateResult]:
    if not text:
        return []
    text = _limpar_encoding(text)
    padrao = re.compile(REGEX_PRINCIPAL, re.IGNORECASE)
    positivos_norm = [_normalizar_texto(p) for p in TERMOS_POSITIVOS]
    negativos_norm = [_normalizar_texto(n) for n in TERMOS_NEGATIVOS]
    todos_candidatos = []
    for match in padrao.finditer(text):
        num = match.group(1)
        pos = match.start()
        ctx_inicio = max(0, pos - 250)
        ctx_fim = min(len(text), pos + 250)
        ctx = text[ctx_inicio:ctx_fim]
        ctx_norm = _normalizar_texto(ctx)
        ctx_lower = ctx.lower()
        score = 0
        for termo in positivos_norm:
            if termo and termo in ctx_norm:
                score += PESO_POSITIVO
        for termo in negativos_norm:
            if termo and termo in ctx_norm:
                score -= PESO_NEGATIVO
        if "prazo" in ctx_lower and ("entrega" in ctx_lower or "fornecimento" in ctx_lower):
            score += BONUS_FRASE_TIPICA
        if any(f in ctx_lower for f in ["prazo de execucao", "prazo de fornecimento", "prazo de entrega", "prazo de realizacao"]):
            score += 2
        if any(f in ctx_lower for f in ["devera ser concluido", "deverao ser executados"]):
            score += 3
        if "cronograma" in ctx_lower and ("realizacao" in ctx_lower or "servico" in ctx_lower):
            score += 5
        if "prazo de" in ctx_lower and "dias corridos" in ctx_lower:
            score += 2
        if "inicio" in ctx_lower and ("execucao" in ctx_lower or "objeto" in ctx_lower):
            score -= 5
        if score >= THRESHOLD_SCORE:
            match_text = match.group(0).lower()
            if "uteis" in match_text:
                valor = f"{num} dias uteis"
            elif "corridos" in match_text:
                valor = f"{num} dias corridos"
            else:
                valor = f"{num} dias"
            ev_inicio = max(0, pos - 60)
            ev_fim = min(len(text), pos + 60)
            evidence = re.sub(r"\s+", " ", text[ev_inicio:ev_fim]).strip()
            todos_candidatos.append(CandidateResult(value=valor, score=score, context=re.sub(r"\s+", " ", ctx).strip(), evidence=evidence))
    todos_candidatos.sort(key=lambda x: x.score, reverse=True)
    selecionados = []
    for c in todos_candidatos:
        eh_similar = any(_calcular_similaridade(c.context, s.context) >= 0.75 for s in selecionados)
        if not eh_similar:
            selecionados.append(c)
        if len(selecionados) >= max_candidatos:
            break
    return selecionados

def extract_e001(text: str) -> ExtractResult:
    candidatos = extract_e001_multi(text, max_candidatos=1)
    if candidatos:
        c = candidatos[0]
        return ExtractResult(value=c.value, evidence=c.evidence, score=c.score)
    return ExtractResult(value=None, evidence=None, score=0)