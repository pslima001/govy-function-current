# govy/extractors/l001_locais.py
"""
L001 - Extrator de Locais de Entrega via Texto

Este arquivo contém a lógica para extrair locais de entrega do TEXTO
do documento (quando não há tabelas ou como fallback).

Última atualização: 15/01/2026
Responsável pela edição de regras: ChatGPT 5.2
Responsável pelo deploy: Claude
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class ExtractResultList:
    """Resultado da extração de lista de valores."""
    values: List[str]
    evidence: Optional[str]
    score: int


# =============================================================================
# CONFIGURAÇÃO DE REGRAS - EDITE AQUI
# =============================================================================

# Gatilhos de contexto (indicam seção de local de entrega)
GATILHOS = [
    "local de entrega",
    "locais de entrega",
    "endereço de entrega",
    "endereços de entrega",
    "endereco de entrega",
    "enderecos de entrega",
    "local de recebimento",
    "locais de recebimento",
    "recebimento",
    "entrega",
    "entregar",
    "fornecimento",
    "ponto de entrega",
    "ponto a ponto",
]

# Termos negativos (evitar cabeçalho/rodapé/contato institucional)
TERMOS_NEGATIVOS = [
    "prefeitura",
    "câmara",
    "camara",
    "cnpj",
    "telefone",
    "tel.",
    "fax",
    "e-mail",
    "email",
    "www",
    ".gov",
    "ouvidoria",
    "secretaria",
    "gabinete",
]

# =============================================================================
# FUNÇÕES DE EXTRAÇÃO - NÃO EDITE ABAIXO DESTA LINHA
# =============================================================================

def _normalizar_texto(s: str) -> str:
    """Normaliza texto para comparação."""
    s = s.lower()
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", s) 
        if not unicodedata.combining(ch)
    )


def _norm_spaces(s: str) -> str:
    """Remove espaços e caracteres inválidos."""
    s = (s or "").replace("\uFFFD", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# Pré-normalizar listas
_GATILHOS_NORM = [_normalizar_texto(g) for g in GATILHOS]
_NEGATIVOS_NORM = [_normalizar_texto(n) for n in TERMOS_NEGATIVOS]

# Padrão de início de logradouro
LOGRADOURO_RE = re.compile(
    r"\b(rua|r\.|avenida|av\.?|rodovia|rod\.?|estrada|travessa|alameda|largo|praça|praca|br)\b",
    re.IGNORECASE
)

# Captura um candidato relativamente longo após o logradouro
CANDIDATO_RE = re.compile(
    r"\b(?:Rua|R\.|Avenida|Av\.?|Rodovia|Rod\.?|Estrada|Travessa|Alameda|Largo|Praça|Praca|BR)"
    r"\s+[^\n;]{10,220}",
    re.IGNORECASE
)


def _has_context(window: str) -> bool:
    """Verifica se a janela tem contexto de entrega."""
    w = _normalizar_texto(window)
    return any(g and g in w for g in _GATILHOS_NORM)


def _is_negative(window: str) -> bool:
    """Verifica se a janela tem termos negativos."""
    w = _normalizar_texto(window)
    return any(n and n in w for n in _NEGATIVOS_NORM)


def _validate_candidate(cand: str) -> bool:
    """Valida se um candidato é um endereço válido."""
    c = _norm_spaces(cand)
    low = c.lower()

    # Precisa começar com logradouro
    if not re.search(
        r"^(rua|r\.|avenida|av\.?|rodovia|rod\.?|estrada|travessa|alameda|largo|praça|praca|br)\b", 
        low
    ):
        return False

    # Precisa ter número, km ou s/n
    if not re.search(r"(\b\d{1,6}\b|\bkm\b|\bs\/n\b|\bsn\b)", low):
        return False

    # Tamanho mínimo
    if len(c) < 15:
        return False

    return True


def extract_l001(text: str) -> ExtractResultList:
    """
    Extrai locais de entrega/recebimento do texto.
    
    Estratégia:
    1. Procura "janelas" de contexto com gatilhos (entrega/recebimento)
    2. Dentro dessas janelas, extrai candidatos de endereço por regex
    3. Valida estrutura mínima (logradouro + número/s/n/km)
    4. Deduplica
    
    Args:
        text: Texto completo do documento
        
    Returns:
        ExtractResultList com valores encontrados
    """
    if not text:
        return ExtractResultList(values=[], evidence=None, score=0)

    lines = text.splitlines()
    hits: List[str] = []
    evidences: List[str] = []

    # Varre linhas e cria janelas de 8 linhas antes/depois quando achar gatilho
    for i, line in enumerate(lines):
        # Verifica se a linha contém algum gatilho
        if any(g and g in _normalizar_texto(line) for g in _GATILHOS_NORM):
            ini = max(0, i - 8)
            fim = min(len(lines), i + 12)
            window = "\n".join(lines[ini:fim])

            # Evita janelas claramente de cabeçalho
            if _is_negative(window) and not _has_context(window):
                continue

            # Busca endereços na janela
            for match in CANDIDATO_RE.finditer(window):
                cand = _norm_spaces(match.group(0))
                if _validate_candidate(cand):
                    hits.append(cand)

            # Guarda evidência (primeira janela já ajuda)
            if window and not evidences:
                evidences.append(window[:800])

    # Dedup preservando ordem
    seen = set()
    unique: List[str] = []
    
    for h in hits:
        key = _normalizar_texto(h)
        if key not in seen:
            seen.add(key)
            unique.append(h)

    if not unique:
        return ExtractResultList(values=[], evidence=None, score=0)

    score = 5 + min(10, len(unique) * 2)
    evidence = evidences[0] if evidences else None
    
    return ExtractResultList(
        values=unique,
        evidence=evidence,
        score=int(score)
    )
