"""
govy/juris/metadata_extract.py

Módulo de extração de metadados de jurisprudência.
Detecta automaticamente: tribunal, UF, número do caso, ano.

Versão: 1.0
Data: 05/02/2026
"""

import re
import unicodedata
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict


# =============================================================================
# CONSTANTES - MAPEAMENTO DE ESTADOS
# =============================================================================

UF_LIST = [
    'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
    'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN',
    'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO'
]

UF_PATTERN = '|'.join(UF_LIST)

# Mapeamento nome do estado -> UF
ESTADO_TO_UF = {
    'ACRE': 'AC', 'ALAGOAS': 'AL', 'AMAZONAS': 'AM', 'AMAPA': 'AP',
    'BAHIA': 'BA', 'CEARA': 'CE', 'DISTRITO FEDERAL': 'DF', 'ESPIRITO SANTO': 'ES',
    'GOIAS': 'GO', 'MARANHAO': 'MA', 'MINAS GERAIS': 'MG', 'MATO GROSSO DO SUL': 'MS',
    'MATO GROSSO': 'MT', 'PARA': 'PA', 'PARAIBA': 'PB', 'PERNAMBUCO': 'PE',
    'PIAUI': 'PI', 'PARANA': 'PR', 'RIO DE JANEIRO': 'RJ', 'RIO GRANDE DO NORTE': 'RN',
    'RONDONIA': 'RO', 'RORAIMA': 'RR', 'RIO GRANDE DO SUL': 'RS', 'SANTA CATARINA': 'SC',
    'SERGIPE': 'SE', 'SAO PAULO': 'SP', 'TOCANTINS': 'TO'
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class DetectionResult:
    """Resultado da detecção de tribunal."""
    tribunal_family: Optional[str] = None
    tribunal: Optional[str] = None
    uf: Optional[str] = None
    confidence: float = 0.0
    signals: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CaseNumberResult:
    """Resultado da extração de números do caso."""
    case_number_primary: Optional[str] = None
    case_numbers_secondary: List[str] = field(default_factory=list)
    year: int = 0
    number_type: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class MetadataResult:
    """Resultado completo da extração de metadados."""
    tribunal_family: Optional[str] = None
    tribunal: Optional[str] = None
    uf: Optional[str] = None
    case_number_primary: Optional[str] = None
    case_numbers_secondary: List[str] = field(default_factory=list)
    year: int = 0
    confidence: float = 0.0
    signals: List[str] = field(default_factory=list)
    citation: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def normalize_text(text: str) -> str:
    """Normaliza texto para detecção (upper, sem acentos)."""
    text_normalized = unicodedata.normalize('NFD', text)
    text_normalized = ''.join(
        c for c in text_normalized 
        if unicodedata.category(c) != 'Mn'
    )
    text_normalized = text_normalized.upper()
    text_normalized = re.sub(r'\s+', ' ', text_normalized)
    return text_normalized


def extract_uf_from_state_name(text_norm: str) -> Optional[str]:
    """Extrai UF a partir do nome do estado no texto."""
    for estado, uf in ESTADO_TO_UF.items():
        if estado in text_norm:
            return uf
    return None


# =============================================================================
# DETECÇÃO DE TRIBUNAL
# =============================================================================

def detect_tribunal(text: str) -> DetectionResult:
    """Detecta tribunal a partir do texto."""
    text_norm = normalize_text(text)
    result = DetectionResult()
    
    # ----- TCU -----
    tcu_patterns = [
        (r'\bTCU\b', 'TCU'),
        (r'TRIBUNAL\s+DE\s+CONTAS\s+DA\s+UNIAO', 'TCU_NOME'),
        (r'ACORDAO\s*(N[O.]?\s*)?\d{1,6}\s*/\s*\d{4}.*TCU', 'ACORDAO_TCU'),
        (r'PLENARIO\s+DO\s+TCU', 'PLENARIO_TCU'),
        (r'RELATOR[A]?:\s*MINISTRO', 'MINISTRO_TCU'),
    ]
    
    tcu_signals = []
    for pattern, signal in tcu_patterns:
        if re.search(pattern, text_norm):
            tcu_signals.append(signal)
    
    if tcu_signals:
        if 'TCU' in tcu_signals or 'TCU_NOME' in tcu_signals or 'ACORDAO_TCU' in tcu_signals:
            result.tribunal_family = 'TCU'
            result.tribunal = 'TCU'
            result.signals = tcu_signals
            result.confidence = min(0.5 + len(tcu_signals) * 0.15, 0.98)
            return result
    
    # ----- TCE (com UF) -----
    tce_pattern = rf'\bTCE[\-/\s]?({UF_PATTERN})\b'
    tce_match = re.search(tce_pattern, text_norm)
    if tce_match:
        uf = tce_match.group(1)
        result.tribunal_family = 'TCE'
        result.tribunal = f'TCE-{uf}'
        result.uf = uf
        result.signals = [f'TCE-{uf}']
        result.confidence = 0.92
        return result
    
    tce_nome_pattern = r'TRIBUNAL\s+DE\s+CONTAS\s+DO\s+ESTADO\s+D[OE]\s+'
    if re.search(tce_nome_pattern, text_norm):
        uf = extract_uf_from_state_name(text_norm)
        if uf:
            result.tribunal_family = 'TCE'
            result.tribunal = f'TCE-{uf}'
            result.uf = uf
            result.signals = ['TCE_NOME', f'UF_{uf}']
            result.confidence = 0.90
            return result
    
    # ----- STF -----
    stf_patterns = [
        (r'\bSTF\b', 'STF'),
        (r'SUPREMO\s+TRIBUNAL\s+FEDERAL', 'STF_NOME'),
        (r'\bARE\b\s*\d', 'ARE'),
        (r'\bRE\b\s*\d', 'RE'),
        (r'\bADI\b\s*\d', 'ADI'),
        (r'\bADPF\b\s*\d', 'ADPF'),
        (r'\bRCL\b\s*\d', 'RCL'),
        (r'TEMA\s*N[O.]?\s*\d{1,4}', 'TEMA'),
    ]
    
    stf_signals = []
    for pattern, signal in stf_patterns:
        if re.search(pattern, text_norm):
            stf_signals.append(signal)
    
    if 'STF' in stf_signals or 'STF_NOME' in stf_signals:
        result.tribunal_family = 'STF'
        result.tribunal = 'STF'
        result.signals = stf_signals
        result.confidence = min(0.5 + len(stf_signals) * 0.15, 0.98)
        return result
    
    if any(s in stf_signals for s in ['ARE', 'RE', 'ADI', 'ADPF', 'RCL']):
        result.tribunal_family = 'STF'
        result.tribunal = 'STF'
        result.signals = stf_signals
        result.confidence = 0.75
        return result
    
    # ----- STJ -----
    stj_patterns = [
        (r'\bSTJ\b', 'STJ'),
        (r'SUPERIOR\s+TRIBUNAL\s+DE\s+JUSTICA', 'STJ_NOME'),
        (r'\bRESP\b', 'RESP'),
        (r'\bARESP\b', 'ARESP'),
        (r'\bAGINT\b', 'AGINT'),
        (r'\bEDCL\b', 'EDCL'),
        (r'\bRMS\b\s*\d', 'RMS'),
    ]
    
    stj_signals = []
    for pattern, signal in stj_patterns:
        if re.search(pattern, text_norm):
            stj_signals.append(signal)
    
    if 'STJ' in stj_signals or 'STJ_NOME' in stj_signals:
        result.tribunal_family = 'STJ'
        result.tribunal = 'STJ'
        result.signals = stj_signals
        result.confidence = min(0.5 + len(stj_signals) * 0.15, 0.98)
        return result
    
    if any(s in stj_signals for s in ['RESP', 'ARESP', 'AGINT']):
        result.tribunal_family = 'STJ'
        result.tribunal = 'STJ'
        result.signals = stj_signals
        result.confidence = 0.75
        return result
    
    # ----- TRF (regiões) -----
    trf_pattern = r'\bTRF\s*-?\s*([1-6])\b|\bTRF([1-6])\b'
    trf_match = re.search(trf_pattern, text_norm)
    if trf_match:
        regiao = trf_match.group(1) or trf_match.group(2)
        result.tribunal_family = 'TRF'
        result.tribunal = f'TRF{regiao}'
        result.signals = [f'TRF{regiao}']
        result.confidence = 0.90
        return result
    
    # ----- TJ (com UF) -----
    tj_pattern = rf'\bTJ({UF_PATTERN})\b'
    tj_match = re.search(tj_pattern, text_norm)
    if tj_match:
        uf = tj_match.group(1)
        result.tribunal_family = 'TJ'
        result.tribunal = f'TJ{uf}'
        result.uf = uf
        result.signals = [f'TJ{uf}']
        result.confidence = 0.92
        return result
    
    tj_nome_pattern = r'TRIBUNAL\s+DE\s+JUSTICA\s+DO\s+ESTADO\s+D[OE]\s+'
    if re.search(tj_nome_pattern, text_norm):
        uf = extract_uf_from_state_name(text_norm)
        if uf:
            result.tribunal_family = 'TJ'
            result.tribunal = f'TJ{uf}'
            result.uf = uf
            result.signals = ['TJ_NOME', f'UF_{uf}']
            result.confidence = 0.88
            return result
    
    # ----- TST/TRT (Trabalho) -----
    if re.search(r'\bTST\b|TRIBUNAL\s+SUPERIOR\s+DO\s+TRABALHO', text_norm):
        result.tribunal_family = 'TST'
        result.tribunal = 'TST'
        result.signals = ['TST']
        result.confidence = 0.90
        return result
    
    trt_pattern = r'\bTRT\s*-?\s*(\d{1,2})\b|\bTRT(\d{1,2})\b'
    trt_match = re.search(trt_pattern, text_norm)
    if trt_match:
        regiao = trt_match.group(1) or trt_match.group(2)
        result.tribunal_family = 'TRT'
        result.tribunal = f'TRT{regiao}'
        result.signals = [f'TRT{regiao}']
        result.confidence = 0.90
        return result
    
    # ----- Não identificado -----
    uf = extract_uf_from_state_name(text_norm)
    if uf:
        result.uf = uf
        result.signals = [f'UF_{uf}_INFERIDA']
        result.confidence = 0.30
    
    return result


# =============================================================================
# EXTRAÇÃO DE NÚMERO DO CASO
# =============================================================================

def extract_case_numbers(text: str) -> CaseNumberResult:
    """Extrai números do caso do texto."""
    text_norm = normalize_text(text)
    result = CaseNumberResult()
    found_numbers = []
    
    # CNJ
    cnj_pattern = r'\b(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})\b'
    cnj_matches = re.findall(cnj_pattern, text_norm)
    for match in cnj_matches:
        year = int(match[11:15])
        found_numbers.append({'number': match, 'type': 'CNJ', 'year': year, 'priority': 1})
    
    # Acórdão
    acordao_pattern = r'ACORDAO\s*(?:N[O.]?\s*)?(\d{1,6}\s*/\s*\d{4})'
    acordao_matches = re.findall(acordao_pattern, text_norm)
    for match in acordao_matches:
        clean = re.sub(r'\s+', '', match)
        year_match = re.search(r'/(\d{4})$', clean)
        year = int(year_match.group(1)) if year_match else 0
        found_numbers.append({'number': f'Acordao {clean}', 'type': 'ACORDAO', 'year': year, 'priority': 2})
    
    # REsp
    resp_pattern = r'\bRESP\s*(?:N[O.]?\s*)?([\d\.\-\/]+)'
    resp_matches = re.findall(resp_pattern, text_norm)
    for match in resp_matches:
        found_numbers.append({'number': f'REsp {match}', 'type': 'RESP', 'year': 0, 'priority': 3})
    
    # AREsp
    aresp_pattern = r'\bARESP\s*(?:N[O.]?\s*)?([\d\.\-\/]+)'
    aresp_matches = re.findall(aresp_pattern, text_norm)
    for match in aresp_matches:
        found_numbers.append({'number': f'AREsp {match}', 'type': 'ARESP', 'year': 0, 'priority': 3})
    
    # RE
    re_pattern = r'\bRE\s*(?:N[O.]?\s*)?(\d{5,})'
    re_matches = re.findall(re_pattern, text_norm)
    for match in re_matches:
        found_numbers.append({'number': f'RE {match}', 'type': 'RE', 'year': 0, 'priority': 3})
    
    # ARE
    are_pattern = r'\bARE\s*(?:N[O.]?\s*)?(\d{5,})'
    are_matches = re.findall(are_pattern, text_norm)
    for match in are_matches:
        found_numbers.append({'number': f'ARE {match}', 'type': 'ARE', 'year': 0, 'priority': 3})
    
    # Processo
    processo_pattern = r'PROCESSO\s*(?:N[O.]?\s*)?([\d\.\-\/]+)'
    processo_matches = re.findall(processo_pattern, text_norm)
    for match in processo_matches:
        if len(match) >= 5:
            found_numbers.append({'number': f'Processo {match}', 'type': 'PROCESSO', 'year': 0, 'priority': 4})
    
    # Autos
    autos_pattern = r'AUTOS?\s*(?:N[O.]?\s*)?([\d\.\-\/]+)'
    autos_matches = re.findall(autos_pattern, text_norm)
    for match in autos_matches:
        if len(match) >= 5:
            found_numbers.append({'number': f'Autos {match}', 'type': 'AUTOS', 'year': 0, 'priority': 5})
    
    # Ordenar e deduplicar
    found_numbers.sort(key=lambda x: x['priority'])
    seen = set()
    unique_numbers = []
    for item in found_numbers:
        if item['number'] not in seen:
            seen.add(item['number'])
            unique_numbers.append(item)
    
    if unique_numbers:
        primary = unique_numbers[0]
        result.case_number_primary = primary['number']
        result.number_type = primary['type']
        result.year = primary['year']
        
        if len(unique_numbers) > 1:
            result.case_numbers_secondary = [n['number'] for n in unique_numbers[1:]]
        
        if result.year == 0:
            for item in unique_numbers:
                if item['year'] > 0:
                    result.year = item['year']
                    break
    
    return result


# =============================================================================
# CONSTRUÇÃO DE CITAÇÃO
# =============================================================================

def build_citation(detection: DetectionResult, case_numbers: CaseNumberResult) -> str:
    """Constrói string de citação padronizada."""
    parts = []
    
    if detection.tribunal:
        parts.append(detection.tribunal)
    else:
        parts.append("Tribunal nao identificado")
    
    if case_numbers.case_number_primary:
        parts.append(case_numbers.case_number_primary)
    
    if case_numbers.year > 0:
        parts.append(str(case_numbers.year))
    
    return ", ".join(parts)


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def extract_metadata(text: str) -> MetadataResult:
    """Extrai todos os metadados de um texto de jurisprudência."""
    detection = detect_tribunal(text)
    case_numbers = extract_case_numbers(text)
    citation = build_citation(detection, case_numbers)
    
    return MetadataResult(
        tribunal_family=detection.tribunal_family,
        tribunal=detection.tribunal,
        uf=detection.uf,
        case_number_primary=case_numbers.case_number_primary,
        case_numbers_secondary=case_numbers.case_numbers_secondary,
        year=case_numbers.year,
        confidence=detection.confidence,
        signals=detection.signals,
        citation=citation
    )


# =============================================================================
# CRITÉRIOS DE AUTO-APPROVE
# =============================================================================

def should_auto_approve(
    metadata: MetadataResult, 
    text_length: int,
    sha_duplicate: bool = False,
    semantic_duplicate: bool = False
) -> Tuple[bool, str]:
    """Determina se deve auto-aprovar a jurisprudência."""
    strong_families = ['TCU', 'TCE', 'STF', 'STJ', 'TJ', 'TRF']
    if metadata.tribunal_family not in strong_families:
        return False, "tribunal_not_detected"
    
    if metadata.confidence < 0.70:
        return False, "low_confidence"
    
    if not metadata.case_number_primary:
        return False, "no_case_number"
    
    if sha_duplicate:
        return False, "sha_duplicate"
    
    if semantic_duplicate:
        return False, "semantic_duplicate"
    
    if text_length < 1000:
        return False, "text_too_short"
    
    return True, "approved"
