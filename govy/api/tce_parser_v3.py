# tce_parser_v3.py
# Python único, determinístico (sem IA externa), pronto para batch.
# Dep: PyMuPDF (fitz), pdfplumber (fallback)
from __future__ import annotations

import re
import io
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

MISSING = "__MISSING__"

# ----------------------------
# Normalização de texto
# ----------------------------
def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\r\n|\r", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def to_single_line(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def safe_upper(text: str) -> str:
    return _strip_accents(text).upper()

# ----------------------------
# Extração de texto do PDF
# ----------------------------
def extract_text_pymupdf(pdf_bytes: bytes) -> str:
    import fitz
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    parts = []
    for i in range(len(doc)):
        page = doc[i]
        parts.append(page.get_text("text") or "")
    return normalize_text("\n".join(parts))

def extract_text_pdfplumber(pdf_bytes: bytes) -> str:
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        parts = []
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return normalize_text("\n".join(parts))

def parse_bytes(pdf_bytes: bytes) -> Dict[str, str]:
    text = ""
    extractor = "pymupdf"
    needs_fallback = False
    try:
        text = extract_text_pymupdf(pdf_bytes)
    except Exception:
        needs_fallback = True
    if (not text or len(text) < 200) or needs_fallback:
        try:
            text = extract_text_pdfplumber(pdf_bytes)
            extractor = "pdfplumber"
        except Exception:
            text = ""
    text = normalize_text(text)
    return {
        "text": text,
        "text_1": to_single_line(text),
        "needs_fallback": str(needs_fallback or (extractor == "pdfplumber")),
        "extractor": extractor,
    }

# ----------------------------
# Tribunal / UF / Região
# ----------------------------
UF_MAP = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM",
    "BAHIA": "BA", "CEARA": "CE", "DISTRITO FEDERAL": "DF", "ESPIRITO SANTO": "ES",
    "GOIAS": "GO", "MARANHAO": "MA", "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG", "PARA": "PA", "PARAIBA": "PB", "PARANA": "PR",
    "PERNAMBUCO": "PE", "PIAUI": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN",
    "RIO GRANDE DO SUL": "RS", "RONDONIA": "RO", "RORAIMA": "RR", "SANTA CATARINA": "SC",
    "SAO PAULO": "SP", "SERGIPE": "SE", "TOCANTINS": "TO",
}

REGION_MAP = {
    "AC": "NORTE", "AP": "NORTE", "AM": "NORTE", "PA": "NORTE", "RO": "NORTE", "RR": "NORTE", "TO": "NORTE",
    "AL": "NORDESTE", "BA": "NORDESTE", "CE": "NORDESTE", "MA": "NORDESTE", "PB": "NORDESTE",
    "PE": "NORDESTE", "PI": "NORDESTE", "RN": "NORDESTE", "SE": "NORDESTE",
    "DF": "CENTRO-OESTE", "GO": "CENTRO-OESTE", "MT": "CENTRO-OESTE", "MS": "CENTRO-OESTE",
    "ES": "SUDESTE", "MG": "SUDESTE", "RJ": "SUDESTE", "SP": "SUDESTE",
    "PR": "SUL", "RS": "SUL", "SC": "SUL",
}

def detect_uf(text: str) -> str:
    t = safe_upper(text)
    m = re.search(r"\bESTADO\s+DE\s+([A-Z\s]{3,30})\b", t)
    if m:
        state = re.sub(r"\s{2,}", " ", m.group(1).strip())
        if state in UF_MAP:
            return UF_MAP[state]
    for state, uf in sorted(UF_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(state)}\b", t):
            return uf
    return MISSING

def detect_region(uf: str) -> str:
    return REGION_MAP.get(uf, MISSING)

def detect_tribunal_type(text: str) -> str:
    t = safe_upper(text)
    if re.search(r"\bSUPREMO\s+TRIBUNAL\s+FEDERAL\b|\bSTF\b", t): return "STF"
    if re.search(r"\bSUPERIOR\s+TRIBUNAL\s+DE\s+JUSTICA\b|\bSTJ\b", t): return "STJ"
    if re.search(r"\bTRIBUNAL\s+DE\s+CONTAS\s+DA\s+UNIAO\b|\bTCU\b", t): return "TCU"
    if re.search(r"\bTRIBUNAL\s+DE\s+CONTAS\b", t) and re.search(r"\bESTADO\b|\bESTADUAL\b", t): return "TCE"
    if re.search(r"\bTRIBUNAL\s+DE\s+CONTAS\s+DO\s+ESTADO\b", t): return "TCE"
    if re.search(r"\bTRIBUNAL\s+DE\s+JUSTICA\b|\bTJ[A-Z]{1,2}\b", t): return "TJ"
    return "OUTRO"

def detect_tribunal_name(text: str, tribunal_type: str, uf: str) -> str:
    t = safe_upper(text)
    if tribunal_type == "TCU": return "TRIBUNAL DE CONTAS DA UNIAO"
    if tribunal_type == "STF": return "SUPREMO TRIBUNAL FEDERAL"
    if tribunal_type == "STJ": return "SUPERIOR TRIBUNAL DE JUSTICA"
    m = re.search(r"(TRIBUNAL\s+DE\s+CONTAS\s+DO\s+ESTADO\s+DE\s+[A-Z\s]+)", t)
    if m: return re.sub(r"\s{2,}", " ", m.group(1)).strip()
    m = re.search(r"(TRIBUNAL\s+DE\s+JUSTICA\s+DO\s+ESTADO\s+DE\s+[A-Z\s]+)", t)
    if m: return re.sub(r"\s{2,}", " ", m.group(1)).strip()
    if tribunal_type == "TCE" and uf != MISSING: return f"TCE-{uf}"
    if tribunal_type == "TJ" and uf != MISSING: return f"TJ-{uf}"
    return MISSING

# ----------------------------
# Extrações nucleares
# ----------------------------
def extract_processo(text: str) -> str:
    t1 = to_single_line(text)
    candidates = [
        r"\b(TC-\d{3,6}\.\d{3}\.\d{2}-\d)\b",
        r"\b(TC\/\d{1,6}\/\d{4})\b",
        r"\bTC\/MS\s*[:\-]?\s*(TC\/\d{1,6}\/\d{4})\b",
        r"\bPROCESSO(?:\s+DIGITAL)?\s*(?:N[.º°]?\s*)?(TCE-[A-Z]{2}\s*N[º°]?\s*\d{4,10}-\d)\b",
        r"\bPROCESSO\s*(?:N[.º°]?\s*)?(TCE-[A-Z]{2}\s*N[º°]?\s*\d{4,10})\b",
        r"\bPROCESSO\s*(?:N[.º°]?\s*)?(TCE-[A-Z]{2}\s*N[º°]?\s*\d{4,10}-\d)\b",
        r"\bPROCESSO\s*(?:N[.º°]?\s*)?(\d{6,12}-\d)\b",
        r"\bPROCESSO\s*(?:N[.º°]?\s*)?(TCE\/\d{3,9}\/\d{4})\b",
        r"\b(TCE\/\d{3,9}\/\d{4})\b",
    ]
    for pat in candidates:
        m = re.search(pat, t1, flags=re.IGNORECASE)
        if m:
            # Use last capturing group if exists, else group(0)
            try:
                return m.group(1).strip()
            except (IndexError, AttributeError):
                return m.group(0).strip()
    m = re.search(r"\bPROCESSO\b[^A-Z0-9]{0,10}([A-Z0-9\/\.\-]{6,30})", t1, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return MISSING

def extract_acordao_numero(text: str) -> str:
    t1 = to_single_line(text)
    pats = [
        r"\bAC[ÓO]RD[ÃA]O\s*(?:T\.?C\.?)?\s*N[.º°]?\s*([\w\-/\.]+)\b",
        r"\bAC[ÓO]RD[ÃA]O\s*-\s*([A-Z0-9]{2,6}\s*-\s*\d{1,5}\/\d{4})\b",
        r"\bAC[ÓO]RD[ÃA]O\s*T\.?C\.?\s*N[.º°]?\s*(\d+\s*\/\s*\d{4})\b",
    ]
    for pat in pats:
        m = re.search(pat, t1, flags=re.IGNORECASE)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    return MISSING

def extract_relator(text: str) -> str:
    # Use multi-line text (NOT single-line) to respect line breaks
    t = normalize_text(text)
    pats = [
        r"\bRELATOR(?:A)?\s*[:\-]\s*(?:CONS(?:ELHEIRO)?\.?\s+)?([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ\s\.]{2,80}?)(?:\s*\n|\s*$|\s*(?:ÓRGÃO|ORGAO|EMENTA|ACORDAM|PROCESSO|SEGUNDA|PRIMEIRA|TERCEIRA|TRIBUNAL|PLENÁRIO|PLENARIO))",
        r"\bCONSELHEIRO\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ\s]{2,60}?)\s*[-–]\s*RELATOR\b",
    ]
    for pat in pats:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            rel = re.sub(r"\s{2,}", " ", m.group(1)).strip(" .-")
            rel = re.sub(r"\bCONS(?:ELHEIRO)?\.?\s*\b", "", rel, flags=re.IGNORECASE).strip()
            if len(rel) >= 3:
                return rel
    # fallback: simpler pattern on single line
    t1 = to_single_line(text)
    m = re.search(r"\bRELATOR(?:A)?\s*[:\-]\s*(?:CONS(?:ELHEIRO)?\.?\s+)?([A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ\.\s]{2,50})\b", t1, flags=re.I)
    if m:
        rel = m.group(1).strip(" .-")
        for stop in ["ÓRGÃO", "ORGAO", "EMENTA", "ACORDAM", "PROCESSO", "TRIBUNAL", "PLENÁRIO"]:
            idx = rel.upper().find(stop)
            if idx > 0:
                rel = rel[:idx].strip()
        if len(rel) >= 3:
            return re.sub(r"\bCONS(?:ELHEIRO)?\.?\s*\b", "", rel, flags=re.IGNORECASE).strip()
    return MISSING

def extract_ementa(text: str) -> str:
    t = normalize_text(text)
    m = re.search(
        r"\bEMENTA\b\s*[:\-]?\s*(.{10,4000}?)(?=\n\s*(?:AC[ÓO]RD[ÃA]O\b|ACORDAM\b|RELAT[ÓO]RIO\b|VOTO\b|DECIS[ÃA]O\b|DISPOSITIVO\b)\b)",
        t, flags=re.IGNORECASE | re.DOTALL,
    )
    if m:
        e = re.sub(r"\s{2,}", " ", normalize_text(m.group(1)))
        return e if len(e) >= 10 else MISSING
    m = re.search(r"\bEMENTA\b\s*[:\-]?\s*(.{10,800}?)(?=\n\n|\bAC[ÓO]RD[ÃA]O\b)", t, flags=re.I | re.S)
    if m:
        e = normalize_text(m.group(1))
        return e if len(e) >= 10 else MISSING
    return MISSING

def extract_dispositivo(text: str) -> str:
    t = normalize_text(text)

    # Ancoras de inicio (tupla: regex, allow_early)
    anchors = [
        (r"\bACORDA\s+(?:a|o|os|as)\s+(?:E(?:gr[e\xe9]gi[ao])?\.?\s+)?(?:Primeira|Segunda|Terceira|1[a\xaa]|2[a\xaa]|3[a\xaa])?\s*C[\xe2a]mara\b", True),
        (r"\bACORDA\s+(?:a|o|os|as)\s+(?:E(?:gr[e\xe9]gi[ao])?\.?\s+)?Plen[\xe1a]rio\b", True),
        (r"\bACORDAM\b", True),
        (r"\bACORDA\b", True),
        (r"\bA\s+E(?:gr[e\xe9]gi[ao])?\.?\s+(?:Primeira|Segunda|Terceira|1[a\xaa]|2[a\xaa]|3[a\xaa])?\s*C[\xe2a]mara\b", True),
        (r"\b[OA]\s+E(?:gr[e\xe9]gi[ao])?\.?\s+Plen[\xe1a]rio\b", True),
        (r"\bCONSIDERANDO\s+O\s+QUE\s+CONSTA\s+D[OA]\s+RELAT[\xf3o]RIO\b", True),
        (r"\bVISTOS,?\s*RELATADOS\s+E\s+DISCUTIDOS\b", True),
        (r"\bANTE\s+O\s+EXPOSTO\b", False),
        (r"\bDIANTE\s+DO\s+EXPOSTO\b", False),
        (r"\bPELO\s+EXPOSTO\b", False),
        (r"\bPELO\s+(?:MEU\s+)?VOTO\b", False),
        (r"\bDECIDIU-SE\b", False),
        (r"\bDISPOSITIVO\b\s*[:\-]?", False),
        (r"\bJULGAR\s+(?:REGULAR|IRREGULAR|PROCEDENTE|IMPROCEDENTE)\b", False),
        (r"\bDETERMINAR\s+(?:O\s+)?(?:ARQUIVAMENTO|RECOLHIMENTO)\b", False),
        (r"\bCONHECER\s+D[OA]\s+RECURSO\b", False),
    ]

    end_pattern = (
        r"(?:"
        r"\bPUBLIQUE-?SE\b"
        r"|\bREGISTRE-?SE\b"
        r"|\bARQUIVE-?SE\b"
        r"|\bINTIME-?SE\b"
        r"|\bNOTIFIQUE-?SE\b"
        r"|\bCUMPRA-?SE\b"
        r"|\bTR[\xc2A]NSIT(?:O|AD[OA])\s+EM\s+JULGADO\b"
        r"|\bSALA\s+DAS\s+SESS[\xd5O]ES\b"
        r"|\bS[\xc3A]O\s+PAULO\s*,\s*\d{1,2}\s+DE\s+\w+\s+DE\s+\d{4}\b"
        r"|\bASSINAD[OA]\s+DIGITALMENTE\b"
        r"|\bPRESIDENTE\b\s*(?:EM\s+EXERC[\xcdI]CIO\b)?(?:\s*[\-:])"
        r"|\bRELATOR\b\s*[\-:]"
        r"|\bCONSELHEIR[OA]\b\s*[\-:]"
        r")"
    )

    doc_len = len(t)
    doc_half = doc_len // 2
    best_match = None
    best_start = doc_len

    for anchor_re, allow_early in anchors:
        for m in re.finditer(anchor_re, t, flags=re.IGNORECASE | re.DOTALL):
            pos = m.start()
            if allow_early or pos >= doc_half:
                if pos < best_start:
                    best_match = m
                    best_start = pos
                break

    if not best_match:
        return MISSING

    start = best_match.start()
    window = t[start:start + 8000]

    # Buscar terminador so apos 500 chars (intro do acordao tem Relator:/Conselheiro:)
    m_end = re.search(end_pattern, window[500:], flags=re.IGNORECASE | re.DOTALL)
    if m_end:
        # Ajustar offset
        class _M:
            def __init__(self, s): self._s = s
            def start(self): return self._s
        m_end = _M(m_end.start() + 500)
    if m_end:
        bloco = window[:m_end.start()]
    else:
        bloco = window[:6000]

    bloco = re.sub(r"\s+", " ", bloco).strip()
    if len(bloco) < 80:
        return MISSING
    return bloco

def extract_publicacao(text: str) -> Tuple[str, str]:
    t1 = to_single_line(text)
    pub_no = MISSING
    pub_dt = MISSING
    m = re.search(r"\bDI[ÁA]RIO\s+OFICIAL\b.*?\bn[.\sº°]?\s*(\d{3,6})\b", t1, flags=re.I)
    if m: pub_no = m.group(1)
    m = re.search(r"\bDI[ÁA]RIO\s+OFICIAL\b.*?\bDE\s*(\d{2}\/\d{2}\/\d{4})\b", t1, flags=re.I)
    if m: pub_dt = m.group(1)
    if pub_dt == MISSING:
        m = re.search(r"\bDATA\s+DE\s+PUBLICA[ÇC][ÃA]O\s*[:\-]?\s*(?:[A-ZÁÉÍÓÚÂÊÔÃÕÇ]+\s+)?(\d{2}\/\d{2}\/\d{4})\b", t1, flags=re.I)
        if m: pub_dt = m.group(1)
    return pub_no, pub_dt

def extract_data_julgamento(text: str) -> str:
    t1 = to_single_line(text)
    m = re.search(r"\bDATA\s+DE\s+JULGAMENTO\s*[:\-]?\s*(\d{2}\/\d{2}\/\d{4})\b", t1, flags=re.I)
    if m: return m.group(1)
    m = re.search(r"\bREALIZAD[AO]\s+EM\s+(\d{2}\/\d{2}\/\d{4})\b", t1, flags=re.I)
    if m: return m.group(1)
    m = re.search(r"\b(\d{1,2})\s+DE\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ]+)\s+DE\s+(\d{4})\b", safe_upper(t1))
    if m: return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    return MISSING

# ----------------------------
# Referências a outros processos
# ----------------------------
def extract_references(text: str) -> List[str]:
    t1 = to_single_line(text)
    refs = set()
    for m in re.finditer(r"\bTC\/\d{1,6}\/\d{4}\b", t1, flags=re.I): refs.add(m.group(0))
    for m in re.finditer(r"\b\d{6,10}-\d\b", t1): refs.add(m.group(0))
    for m in re.finditer(r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b", t1): refs.add(m.group(0))
    for m in re.finditer(r"\bTC-\d{3,6}\.\d{3}\.\d{2}-\d\b", t1, flags=re.I): refs.add(m.group(0))
    return sorted({re.sub(r"\s+", "", r) for r in refs})

def remove_self_reference(refs: List[str], processo: str) -> List[str]:
    if not refs or processo in (None, "", MISSING): return refs
    p_norm = re.sub(r"\s+", "", processo)
    return [r for r in refs if re.sub(r"\s+", "", r) != p_norm]

# ----------------------------
# Extração de Partes (parties)
# ----------------------------

# Labels de papel — longest-first para evitar match parcial.
# Cada tupla: (regex_pattern, papel_normalizado)
_ROLE_LABELS = [
    # Compound labels (must precede shorter variants)
    (r"Respons[áa]vel\(?(?:is)?\)?\s+pela\s+Homologa[çc][ãa]o\s+do\s+Certame\s+Licitat[óo]rio\s*:", "RESPONSAVEL"),
    (r"Respons[áa]vel\s+pela\s+Ratifica[çc][ãa]o\s+da\s+Dispensa\s+de\s+Licita[çc][ãa]o(?:\s+e\s+pelo\s+Instrumento)?\s*:", "RESPONSAVEL"),
    (r"Respons[áa]veis?\s+pelos?\s+Instrumentos?\s*:", "RESPONSAVEL"),
    (r"Respons[áa]vel\(?(?:is)?\)?\s+pelos?\(?s?\)?\s+Instrumentos?\(?s?\)?\s*:", "RESPONSAVEL"),
    (r"Procurador(?:a)?\s+(?:-?\s*)?Geral\s+do\s+Minist[ée]rio\s+P[úu]blico(?:\s+de\s+Contas)?(?:\s+Substitut[oa])?\s*:", "PROCURADOR"),
    (r"Procurador(?:a)?\s+de\s+Contas\s*:", "PROCURADOR"),
    (r"Procurador(?:a)?\s+da\s+Fazenda\s*:", "PROCURADOR"),
    # Standard labels
    (r"Contratada\(?s?\)?\s*:", "CONTRATADA"),
    (r"Contratante\(?s?\)?\s*:", "CONTRATANTE"),
    (r"Convenente\(?s?\)?\s*:", "CONVENENTE"),
    (r"Conveniada\(?s?\)?\s*:", "CONVENIADA"),
    (r"Recorrente\(?s?\)?\s*:", "RECORRENTE"),
    (r"Recorrido\(?a?\)?\(?s?\)?\s*:", "RECORRIDO"),
    (r"Interessado\(?a?\)?\(?s?\)?\s*:", "INTERESSADO"),
    (r"Representante\(?s?\)?\s*:", "REPRESENTANTE"),
    (r"Representada?\(?s?\)?\s*:", "REPRESENTADA"),
    (r"Licitante\(?s?\)?\s*:", "LICITANTE"),
    (r"Impetrante\(?s?\)?\s*:", "IMPETRANTE"),
    (r"Impetrado\(?a?\)?\s*:", "IMPETRADO"),
    (r"Denunciante\(?s?\)?\s*:", "DENUNCIANTE"),
    (r"Denunciado\(?a?\)?\(?s?\)?\s*:", "DENUNCIADO"),
    (r"Advogados?\(?s?\)?\s*:", "ADVOGADO"),
    (r"Respons[áa]ve(?:l\(?(?:is)?\)?|is)\s*:", "RESPONSAVEL"),
]

# Compiled role label patterns (case-insensitive)
_ROLE_LABELS_C = [(re.compile(p, re.IGNORECASE), papel) for p, papel in _ROLE_LABELS]

# Section boundary — terminates a party-value capture
_HEADER_END_RE = re.compile(
    r"(?:"
    r"\bEMENTA\b"
    r"|\bRELAT[ÓO]RIO\b"
    r"|\bVOTO\b"
    r"|\bDISPOSITIVO\b"
    r"|\bVISTOS\b"
    r"|\bACORDAM\b"
    r")",
    re.IGNORECASE,
)

_VALUE_END_RE = re.compile(
    r"(?:"
    r"\bObjeto\s*:"
    r"|\bEm\s+Julgamento\s*:"
    r"|\bAssunto\s*:"
    r"|\bEMENTA\b"
    r"|\bAC[ÓO]RD[ÃA]O\b"
    r"|\bRELAT[ÓO]RIO\b"
    r"|\bVOTO\b"
    r"|\bDISPOSITIVO\b"
    r"|\bVISTOS\b"
    r"|\bFiscaliza[çc][ãa]o\s+atual\s*:"
    r"|\bFiscalizada\s+por\s*:"
    r")",
    re.IGNORECASE,
)

# CNPJ / CPF / OAB patterns
_CNPJ_RE = re.compile(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b")
_CPF_RE = re.compile(r"\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b")
_OAB_RE = re.compile(
    r"(?:"
    r"\s*[-–—]\s*OAB[/\s]*[A-Z]{2}\s*(?:n[º°.]?\s*)?\d{1,6}(?:\.\d{3})?"
    r"|\s*\(OAB[/\s]*[A-Z]{2}\s*(?:n[º°.]?\s*)?\d{1,6}(?:\.\d{3})?\)"
    r")",
    re.IGNORECASE,
)
_TRAILING_CNPJ_RE = re.compile(r"\s*[-–—,]\s*CNPJ\s*[:/]?\s*\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", re.IGNORECASE)

# Cargo in parentheses
_CARGO_RE = re.compile(r"\(([^)]{3,80})\)")

# Classification: PRIVADA
_PRIVADA_SUFFIXES = re.compile(
    r"\b(?:LTDA\.?|S[/.]?A\.?|EIRELI|EPP)\b"
    r"|\bME\b(?!\s*(?:DE|DO|DA|DOS|DAS)\b)",
    re.IGNORECASE,
)
_PRIVADA_KEYWORDS = re.compile(
    r"\b(?:ENGENHARIA|CONSTRUCAO|COMERCIO|CONSULTORIA|SERVICOS|"
    r"TECNOLOGIA|ASSESSORIA|REFEICOES|PAVIMENTACAO|INFORMATICA|"
    r"COMUNICACAO|INCORPORADORA|CONSTRUTORA|EMPREENDIMENTOS|"
    r"TRANSPORTE|LIMPEZA|SEGURANCA|MANUTENCAO|LOCACAO|"
    r"DISTRIBUIDORA|EDITORA|GRAFICA|INDUSTRIA|SUPERMERCADO|"
    r"FORNECEDORA|IMPORTADORA|EXPORTADORA)\b",
    re.IGNORECASE,
)

# Classification: PUBLICA (high confidence)
_PUBLICA_KEYWORDS_HIGH = re.compile(
    r"\b(?:PREFEITURA|MUNICIPIO\s+DE|SECRETARIA\s+(?:DE\s+ESTADO|MUNICIPAL)|"
    r"ESTADO\s+DE|CAMARA\s+MUNICIPAL|AUTARQUIA|FUNDACAO\s+PUBLICA|"
    r"GOVERNO|TRIBUNAL|MINISTERIO|"
    r"UNIVERSIDADE\s+(?:ESTADUAL|FEDERAL)|"
    r"INSTITUTO\s+FEDERAL|"
    r"COMPANHIA\s+DE\s+SANEAMENTO|COMPANHIA\s+D[OAE]\s+ESTADO|"
    r"SABESP|CETESB|DAEE|DERSA|CDHU|CPTM|EMTU|SPPREV|IPESP)\b",
    re.IGNORECASE,
)

# Classification: PUBLICA (medium confidence)
_PUBLICA_KEYWORDS_MEDIUM = re.compile(
    r"\b(?:FUNDACAO|INSTITUTO)\b",
    re.IGNORECASE,
)

# Classification: PF by cargo
_PF_CARGO_KEYWORDS = re.compile(
    r"\b(?:PREFEITO|SECRETARIO|PRESIDENTE|DIRETOR|"
    r"SUPERINTENDENTE|GOVERNADOR|VEREADOR|GESTOR|"
    r"COORDENADOR|ORDENADOR|TESOUREIRO|CONTADOR)\b",
    re.IGNORECASE,
)

# Papeis that are always PF
_PF_PAPEIS = frozenset({"RESPONSAVEL", "RECORRENTE", "PROCURADOR", "ADVOGADO"})
# Papeis with default public/private heuristic
_PUBLIC_DEFAULT_PAPEIS = frozenset({"CONTRATANTE", "CONVENENTE"})
_PRIVATE_DEFAULT_PAPEIS = frozenset({"CONTRATADA", "CONVENIADA", "LICITANTE"})
# Institutional papeis: collapse whitespace, split only on ";" (no newline+uppercase split)
_PAPEIS_INSTITUICAO = frozenset({
    "CONTRATANTE", "CONTRATADA", "CONVENENTE", "CONVENIADA",
    "LICITANTE", "INTERESSADO", "REPRESENTANTE", "REPRESENTADA",
})


def _extract_header_window(text: str) -> str:
    """Return the header region of the document (before EMENTA/RELATÓRIO/VOTO).

    Caps at 12000 chars to limit false positives and keep runtime low.
    """
    cap = text[:12000]
    m = _HEADER_END_RE.search(cap)
    if m:
        return cap[:m.start()]
    return cap


def _classify_tipo_parte(
    nome_upper: str, papel: str, cargo: Optional[str]
) -> Tuple[str, str]:
    """Classify a party as PRIVADA/PUBLICA/PF/DESCONHECIDA with confidence.

    Order: PUBLICA_HIGH wins over PRIVADA if both match (e.g., estatal companies).
    """
    # Rule 1: certain PF roles (ADVOGADO, RESPONSAVEL, RECORRENTE, PROCURADOR)
    if papel in _PF_PAPEIS:
        return ("PF", "high")

    # Rule 2: PUBLICA high-confidence keywords (checked BEFORE PRIVADA per user req D)
    if _PUBLICA_KEYWORDS_HIGH.search(nome_upper):
        return ("PUBLICA", "high")

    # Rule 3: PRIVADA suffixes (LTDA, S/A, EIRELI, EPP)
    if _PRIVADA_SUFFIXES.search(nome_upper):
        return ("PRIVADA", "high")

    # Rule 4: PRIVADA keywords (ENGENHARIA, CONSTRUCAO, etc.)
    if _PRIVADA_KEYWORDS.search(nome_upper):
        return ("PRIVADA", "high")

    # Rule 5: PUBLICA medium (FUNDACAO, INSTITUTO without PUBLICA)
    if _PUBLICA_KEYWORDS_MEDIUM.search(nome_upper):
        return ("PUBLICA", "medium")

    # Rule 6: PF by cargo
    if cargo:
        cargo_upper = safe_upper(cargo)
        if _PF_CARGO_KEYWORDS.search(cargo_upper):
            return ("PF", "medium")

    # Rule 7: papel-based low-confidence default
    if papel in _PUBLIC_DEFAULT_PAPEIS:
        return ("PUBLICA", "low")
    if papel in _PRIVATE_DEFAULT_PAPEIS:
        return ("PRIVADA", "low")

    return ("DESCONHECIDA", "low")


def _looks_like_entity(fragment: str) -> bool:
    """Heuristic: does this fragment look like a named entity (company/org/person)?

    True if it contains a company suffix/keyword, OR is a multi-token sequence
    starting with uppercase.
    """
    fu = safe_upper(fragment.strip())
    if not fu or len(fu) < 3:
        return False
    if _PRIVADA_SUFFIXES.search(fu) or _PRIVADA_KEYWORDS.search(fu):
        return True
    if _PUBLICA_KEYWORDS_HIGH.search(fu) or _PUBLICA_KEYWORDS_MEDIUM.search(fu):
        return True
    # Multi-token sequence (>= 2 words, first starts with uppercase-like char)
    tokens = fu.split()
    if len(tokens) >= 2 and len(tokens[0]) >= 2:
        return True
    return False


def _clean_nome(raw: str) -> str:
    """Normalize a party name: collapse whitespace, fix hyphen linewraps, trim."""
    s = re.sub(r"\s+", " ", raw).strip()
    # Fix broken hyphen linewraps (e.g., "Constru-\n ção" → already collapsed)
    s = re.sub(r"-\s+", "-", s)
    # Trim trailing punctuation
    s = s.strip(" \t\n\r,;.–—-")
    return s


def extract_partes(text: str) -> List[dict]:
    """Extract parties from TCE document header sections.

    Operates only on the header window (before EMENTA/RELATÓRIO/VOTO, max 12000 chars).
    Returns list of dicts: {nome_raw, tipo_parte, papel, cnpj_cpf, confidence, cargo}.
    """
    header = _extract_header_window(normalize_text(text))
    if not header or len(header) < 10:
        return []

    # Find all label positions
    label_hits: List[Tuple[int, int, str]] = []
    for pattern_c, papel in _ROLE_LABELS_C:
        for m in pattern_c.finditer(header):
            label_hits.append((m.start(), m.end(), papel))

    # Add section/value boundary positions as terminators
    for m in _VALUE_END_RE.finditer(header):
        label_hits.append((m.start(), m.start(), "__BOUNDARY__"))

    if not label_hits:
        return []

    label_hits.sort(key=lambda x: x[0])

    # For each label, capture text until next label/boundary
    raw_parties: List[Tuple[str, str]] = []  # (papel, value)
    for i, (start, end, papel) in enumerate(label_hits):
        if papel == "__BOUNDARY__":
            continue
        # Value extends to next hit or +500 chars
        if i + 1 < len(label_hits):
            value_end = label_hits[i + 1][0]
        else:
            value_end = min(end + 500, len(header))
        value = header[end:value_end].strip()
        # Trim at double newline
        dbl_nl = value.find("\n\n")
        if dbl_nl > 0:
            value = value[:dbl_nl].strip()
        if not value or len(value) < 3:
            continue
        raw_parties.append((papel, value))

    # Split, classify, dedup
    results: List[dict] = []
    seen: set = set()

    for papel, value in raw_parties:
        # Filter out digital signature watermarks
        if re.search(r"C[ÓO]PIA\s+DE\s+DOCUMENTO\s+ASSINADO\s+DIGITALMENTE", value, re.I):
            continue

        # Split strategy depends on papel type
        if papel in _PAPEIS_INSTITUICAO:
            # Institutional: collapse all whitespace first, then split only on ";"
            value_norm = re.sub(r"\s+", " ", value).strip()
            fragments = re.split(r"\s*;\s*", value_norm)
        else:
            # Person roles: split on ";" and newline-with-uppercase
            fragments = re.split(r"\s*;\s*|\n\s*(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", value)
            # Collapse whitespace inside each fragment
            fragments = [re.sub(r"\s+", " ", f).strip() for f in fragments]

        # Conservative " e " split (req C):
        # Do NOT split if the full fragment ends with a company suffix (LTDA, S/A, etc.)
        # Only split when BOTH sides independently look like entities.
        expanded: List[str] = []
        for frag in fragments:
            frag_upper = safe_upper(frag)
            # If whole fragment has a company suffix at end, it's one entity — skip split
            if _PRIVADA_SUFFIXES.search(frag_upper):
                expanded.append(frag)
                continue
            parts = re.split(r"\s+e\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ])", frag)
            if len(parts) <= 1:
                expanded.append(frag)
            else:
                all_ok = all(_looks_like_entity(p) for p in parts)
                if all_ok:
                    expanded.extend(parts)
                else:
                    expanded.append(frag)  # keep unsplit

        for raw_name in expanded:
            nome = _clean_nome(raw_name)
            if len(nome) < 3:
                continue

            # Extract cargo from parenthetical
            cargo = None
            cargo_m = _CARGO_RE.search(nome)
            if cargo_m:
                cargo = cargo_m.group(1).strip()

            # Extract CNPJ/CPF
            cnpj_cpf = None
            cnpj_m = _CNPJ_RE.search(nome)
            if cnpj_m:
                cnpj_cpf = cnpj_m.group(1)
                # Strip trailing CNPJ from nome_raw (req E)
                nome = _TRAILING_CNPJ_RE.sub("", nome).strip()
            else:
                cpf_m = _CPF_RE.search(nome)
                if cpf_m:
                    cnpj_cpf = cpf_m.group(1)

            # Strip OAB from advogado names (req E)
            if papel == "ADVOGADO":
                nome = _OAB_RE.sub("", nome).strip()
                nome = nome.strip(" ,;.–—-")
                # OAB in cargo is not a real cargo — clear it
                if cargo and re.search(r"OAB", cargo, re.I):
                    cargo = None

            nome = _clean_nome(nome)
            if len(nome) < 3:
                continue

            nome_upper = safe_upper(nome)

            # Dedup
            dedup_key = (nome_upper, papel)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Classify
            tipo_parte, confidence = _classify_tipo_parte(nome_upper, papel, cargo)

            # Post-classification: CPF override
            if cnpj_cpf and _CPF_RE.fullmatch(cnpj_cpf) and tipo_parte != "PF":
                tipo_parte, confidence = "PF", "medium"

            results.append({
                "nome_raw": nome,
                "tipo_parte": tipo_parte,
                "papel": papel,
                "cnpj_cpf": cnpj_cpf,
                "confidence": confidence,
                "cargo": cargo,
            })

    return results


# ----------------------------
# procedural_stage / claim_pattern
# ----------------------------
PROCEDURAL_STAGE_KW = {
    "EDITAL": [r"\bEDITAL\b", r"\bTERMO\s+DE\s+REFER[ÊE]NCIA\b", r"\bPROJETO\s+B[ÁA]SICO\b", r"\bESPECIFICA[ÇC][ÃA]O\b"],
    "HABILITACAO": [r"\bHABILITA[ÇC][ÃA]O\b", r"\bDOCUMENTA[ÇC][ÃA]O\b", r"\bQUALIFICA[ÇC][ÃA]O\s+T[ÉE]CNICA\b", r"\bBALAN[ÇC]O\s+PATRIMONIAL\b"],
    "JULGAMENTO": [r"\bJULGAMENTO\b", r"\bCRIT[ÉE]RIO\s+DE\s+JULGAMENTO\b", r"\bMENOR\s+PRE[ÇC]O\b", r"\bPROPOSTAS?\b", r"\bLANCES?\b"],
    "CONTRATACAO": [r"\bCONTRATO\b", r"\bFORMALIZA[ÇC][ÃA]O\b", r"\bATA\s+DE\s+REGISTRO\s+DE\s+PRE[ÇC]OS\b", r"\bADJUDICA[ÇC][ÃA]O\b", r"\bHOMOLOGA[ÇC][ÃA]O\b"],
    "EXECUCAO": [r"\bEXECU[ÇC][ÃA]O\b", r"\bMEDI[ÇC][ÃA]O\b", r"\bPAGAMENTO\b", r"\bEMPENHO\b", r"\bTERMO\s+ADITIVO\b", r"\bLIQUIDA[ÇC][ÃA]O\b"],
}

CLAIM_PATTERNS = {
    "RESTRICAO_COMPETITIVIDADE": r"\b(restri[çc][ãa]o\s+[àa]\s+competitividade|frustra[çc][ãa]o\s+do\s+car[áa]ter\s+competitivo|direcionamento)\b",
    "PRAZO_EXIGUO": r"\b(prazos?\s+ex[ií]guos?|prazo\s+insuficiente|prazo\s+desarrazoado)\b",
    "PESQUISA_PRECO_INSUFICIENTE": r"\b(pesquisa\s+de\s+pre[çc]os?\s+insuficiente|apenas\s+\d+\s+fornecedores|cota[çc][ãa]o\s+de\s+pre[çc]os?)\b",
    "ETP_AUSENTE_OU_INCOMPLETO": r"\b(estudo\s+t[ée]cnico\s+preliminar\s+(ausente|incompleto)|aus[êe]ncia\s+de\s+estudo\s+t[ée]cnico)\b",
    "DOCUMENTO_NOVO_DILIGENCIA": r"\b(documento\s+novo|dilig[êe]ncia\s+destinada\s+a\s+esclarecer|art\.\s*43\s*,?\s*§\s*3[ºo])\b",
    "REGULARIDADE_FISCAL_TRABALHISTA": r"\b(regularidade\s+fiscal|regularidade\s+trabalhista|certid[õo]es?\s+negativas?)\b",
    "DISPENSA_INEXIGIBILIDADE": r"\b(dispensa\s+de\s+licita[çc][ãa]o|inexigibilidade\s+de\s+licita[çc][ãa]o)\b",
    "PARECER_JURIDICO_GENERICO": r"\b(parecer\s+jur[ií]dico\s+gen[ée]rico|aus[êe]ncia\s+de\s+an[áa]lise\s+jur[ií]dica)\b",
}

def classify_procedural_stage(text: str) -> str:
    if not text or text == MISSING: return MISSING
    t = safe_upper(text)
    scores = {k: 0 for k in PROCEDURAL_STAGE_KW}
    for stage, pats in PROCEDURAL_STAGE_KW.items():
        for pat in pats:
            scores[stage] += len(re.findall(pat, t, flags=re.I))
    best = max(scores.items(), key=lambda x: x[1])
    return best[0] if best[1] > 0 else MISSING

def detect_claim_patterns(text: str) -> List[str]:
    if not text or text == MISSING: return []
    t = safe_upper(text)
    hits = []
    for name, pat in CLAIM_PATTERNS.items():
        if re.search(pat, t, flags=re.I): hits.append(name)
    return hits

# ----------------------------
# outcome/effect (somente dispositivo!)
# ----------------------------
def classify_outcome_effect_from_dispositivo(dispositivo: str) -> Tuple[str, str]:
    if not dispositivo or dispositivo == MISSING:
        return MISSING, MISSING
    d = safe_upper(dispositivo)

    holding = MISSING
    if re.search(r"\bJULGAR\s+IRREGULAR\w*\b|\bMULTA\b|\bAPLICA[\xc7C][\xc3A]O\s+DE\s+MULTA\b|\bPENALIDADE\b|\bCONDENA\b|\bRESSARCIMENTO\b|\bSAN[\xc7C][\xc3A]O\b|\bIMPOSI[\xc7C][\xc3A]O\s+DE\s+MULTA\b", d):
        holding = "SANCIONOU"
    elif re.search(r"\bDETERMINA\w*\b|\bDETERMINOU\b|\bRECOMENDA\b|\bALERTA\b|\bCI[\xcaE]NCIA\b|\bADEQUA[\xc7C][\xc3A]O\b|\bCORRE[\xc7C][\xc3A]O\b|\bFIXAR\s+PRAZO\b|\bDETERMINA[\xc7C][\xc3A]O\b|\bRESSALVAS?\b", d):
        holding = "DETERMINOU_AJUSTE"
    elif re.search(r"\bAFASTA\w*\b|\bREJEITA\w*\b|\bIMPROCEDENTE\b|\bIMPROCED[\xcaE]NCIA\b|\bN[\xc3A]O\s+CONHECER\b|\bNEGA\w*\s+\S*\s*PROVIMENTO\b|\bINDEFERIR\b", d):
        holding = "AFASTOU"
    elif re.search(r"\bREGULAR\w*\b|\bDAR\s+PROVIMENTO\b|\bDEU\s+PROVIMENTO\b|\bPROVIDO\b", d):
        holding = "ABSOLVEU"
    elif re.search(r"\bARQUIVA\w*\b|\bARQUIVE-?SE\b|\bARQUIVOU\b", d):
        holding = "ARQUIVOU"
    elif re.search(r"\bORIENTA[\xc7C][\xc3A]O\b|\bORIENTOU\b|\bESCLARECIMENTO\b", d):
        holding = "ORIENTOU"

    if holding != "SANCIONOU" and re.search(r"\bIRREGULAR\w*\b", d):
        if re.search(r"\bMULTA\b", d):
            holding = "SANCIONOU"
        elif holding == MISSING:
            holding = "DETERMINOU_AJUSTE"

    effect = MISSING
    if holding == "SANCIONOU":
        effect = "RIGORIZA"
    elif holding == "DETERMINOU_AJUSTE":
        effect = "RIGORIZA" if re.search(r"\bIRREGULAR\b", d) else "CONDICIONAL"
    elif holding in ("ABSOLVEU", "ARQUIVOU", "AFASTOU"):
        effect = "FLEXIBILIZA"
    elif holding == "ORIENTOU":
        effect = "CONDICIONAL"
    return holding, effect

def infer_year(text: str, data_julgamento: str, data_publicacao: str) -> str:
    for dt in (data_julgamento, data_publicacao):
        if dt and dt != MISSING and re.search(r"\d{2}\/\d{2}\/\d{4}", dt):
            return dt[-4:]
    m = re.search(r"\b(19\d{2}|20\d{2})\b", to_single_line(text))
    if m: return m.group(1)
    return MISSING

def authority_score(tribunal_type: str, orgao_julgador: str) -> str:
    base = {"STF": 1.0, "STJ": 0.9, "TCU": 0.9, "TCE": 0.75, "TJ": 0.7, "OUTRO": 0.6}.get(tribunal_type, 0.6)
    if orgao_julgador and orgao_julgador != MISSING:
        o = safe_upper(orgao_julgador)
        if re.search(r"\bPLEN[ÁA]RIO\b|\bTRIBUNAL\s+PLENO\b", o): base = min(1.0, base + 0.05)
        if re.search(r"\bC[ÂA]MARA\b", o): base = max(0.6, base - 0.02)
    return f"{base:.2f}"

def is_current_from_year(year: str, threshold_years: int = 8) -> str:
    if not year or year == MISSING: return MISSING
    try:
        y = int(year)
        return str((datetime.utcnow().year - y) <= threshold_years)
    except Exception:
        return MISSING

def extract_orgao_julgador(text: str) -> str:
    t = normalize_text(text)
    t_upper = safe_upper(t)
    # Try explicit label first
    m = re.search(r"\bORG[ÃA]O\s+JULGADOR\s*[:\-]\s*([^\n]{3,80})", t, flags=re.I)
    if m:
        val = re.sub(r"\s{2,}", " ", m.group(1)).strip()
        # Truncate at known boundaries
        for stop in ["EMENTA", "ACORDAM", "PROCESSO", "RELATOR"]:
            idx = val.upper().find(stop)
            if idx > 0: val = val[:idx].strip()
        if len(val) >= 3: return val
    # Try known patterns in upper text
    m = re.search(r"\b(PRIMEIRA|SEGUNDA|TERCEIRA|QUARTA|QUINTA)\s+C[ÂA]MARA\b", t_upper)
    if m: return m.group(0).title()
    if re.search(r"\bTRIBUNAL\s+PLENO\b", t_upper): return "TRIBUNAL PLENO"
    if re.search(r"\bPLEN[ÁA]RIO\b", t_upper): return "PLENARIO"
    return MISSING

# ----------------------------
# Citação principal + speaker
# ----------------------------
SPEAKER_HINTS = [
    ("RELATOR", r"\bRELATOR\b|\bVOTO\s+DO\s+RELATOR\b|\bCONSELHEIRO\b.*\bRELATOR\b"),
    ("TRIBUNAL", r"\bACORDAM\b|\bDECIS[AÃ]O\b|\bDISPOSITIVO\b"),
    ("MINISTERIO_PUBLICO", r"\bMINIST[ÉE]RIO\s+P[ÚU]BLICO\b|\bMPC\b|\bPROCURADOR\b"),
    ("UNANIMIDADE", r"\b[AÀ]\s+UNANIMIDADE\b|\bPOR\s+UNANIMIDADE\b"),
]

DECISIVE_KW = [
    r"\bDECLARAR\b", r"\bJULGAR\b", r"\bIRREGULARIDADE\b", r"\bREGULARIDADE\b",
    r"\bIMPROCED[ÊE]NCIA\b", r"\bARQUIVAMENTO\b", r"\bAPLICAR\s+MULTA\b|\bMULTA\b",
    r"\bNEGAR[-\s]?LHE\s+PROVIMENTO\b|\bDAR[-\s]?LHE\s+PROVIMENTO\b",
    r"\bABSOLVER\b", r"\bDETERMINAR\b", r"\bRECOMENDA[ÇC][ÃA]O\b|\bRECOMENDAR\b",
    r"\bINIDONEIDADE\b", r"\bSUSPENDER\b|\bANULAR\b",
]

def _guess_speaker(block: str) -> str:
    b = safe_upper(block)
    for name, pat in SPEAKER_HINTS:
        if re.search(pat, b, flags=re.I): return name
    return MISSING

def extract_key_citation(dispositivo: str) -> Tuple[str, str, str]:
    if not dispositivo or dispositivo == MISSING:
        return MISSING, MISSING, MISSING
    frases = re.split(r"[.;]", normalize_text(dispositivo))
    frases = [f.strip() for f in frases if len(f.strip()) > 30]
    if not frases:
        snippet = dispositivo[:300].strip()
        return snippet, MISSING, "DISPOSITIVO"
    keywords = r"\b(?:irregular|regular|procedente|improcedente|multa|determina|recomenda|arquiv|nega\s+provimento|d[a\xe1e\xe9\xea]\s+provimento|sanciona|condena|ressarcimento|penalidade)\b"
    best = None
    best_score = -1
    for frase in frases:
        score = len(re.findall(keywords, frase, re.I))
        if score > best_score:
            best_score = score
            best = frase
    if not best:
        best = frases[0]
    if len(best) > 300:
        best = best[:297] + "..."
    return best, MISSING, "DISPOSITIVO"

def parse_text(text: str, include_text: bool = False) -> Dict[str, object]:
    text = normalize_text(text)
    text_1 = to_single_line(text)
    uf = detect_uf(text)
    tribunal_type = detect_tribunal_type(text)
    tribunal_name = detect_tribunal_name(text, tribunal_type, uf)
    region = detect_region(uf) if tribunal_type != "TCU" else MISSING
    processo = extract_processo(text)
    acordao_num = extract_acordao_numero(text)
    relator = extract_relator(text)
    orgao_julgador = extract_orgao_julgador(text)
    ementa = extract_ementa(text)
    dispositivo = extract_dispositivo(text)
    procedural_stage = classify_procedural_stage(ementa)
    if procedural_stage == MISSING: procedural_stage = classify_procedural_stage(dispositivo)
    if procedural_stage == MISSING: procedural_stage = classify_procedural_stage(text)
    claim_patterns = detect_claim_patterns(ementa if ementa != MISSING else (dispositivo if dispositivo != MISSING else text))
    if dispositivo != MISSING:
        holding_outcome, effect = classify_outcome_effect_from_dispositivo(dispositivo)
    else:
        holding_outcome, effect = (MISSING, MISSING)
    pub_no, pub_dt = extract_publicacao(text)
    julg_dt = extract_data_julgamento(text)
    year = infer_year(text, julg_dt, pub_dt)
    auth = authority_score(tribunal_type, orgao_julgador)
    current = is_current_from_year(year)
    refs = extract_references(text)
    refs = remove_self_reference(refs, processo)
    key_cit, key_speaker, key_src = extract_key_citation(dispositivo)
    partes = extract_partes(text)
    partes_privadas = [p for p in partes if p["tipo_parte"] == "PRIVADA"]
    partes_publicas = [p for p in partes if p["tipo_parte"] == "PUBLICA"]
    out: Dict[str, object] = {
        "tribunal_type": tribunal_type, "tribunal_name": tribunal_name,
        "uf": (MISSING if tribunal_type == "TCU" else uf),
        "region": (MISSING if tribunal_type == "TCU" else region),
        "processo": processo, "acordao_numero": acordao_num,
        "relator": relator, "orgao_julgador": orgao_julgador,
        "ementa": ementa, "dispositivo": dispositivo,
        "holding_outcome": holding_outcome, "effect": effect,
        "publication_number": pub_no, "publication_date": pub_dt, "julgamento_date": julg_dt,
        "references": refs, "linked_processes": refs,
        "procedural_stage": procedural_stage, "claim_pattern": claim_patterns,
        "authority_score": auth, "year": year, "is_current": current,
        "key_citation": key_cit, "key_citation_speaker": key_speaker, "key_citation_source": key_src,
        "party_extraction": {
            "version": 1,
            "partes": partes,
            "partes_privadas": partes_privadas,
            "partes_publicas": partes_publicas,
        },
    }
    if include_text:
        out["text"] = text
        out["text_1"] = text_1
    return out

def parse_pdf_bytes(pdf_bytes: bytes, include_text: bool = False) -> Dict[str, object]:
    ex = parse_bytes(pdf_bytes)
    return parse_text(ex["text"], include_text=include_text)

# ----------------------------
# Merge com metadados do scraper
# ----------------------------
SCRAPER_PRIORITY_FIELDS = {
    "download_url": True, "source_url": True, "pdf_type": True,
    "tribunal_type": True, "uf": True, "processo": True,
    "acordao_numero": True, "publication_date": True, "publication_number": True, "julgamento_date": True,
}

def merge_with_scraper_metadata(parser: Dict[str, object], scraper: Dict[str, object]) -> Dict[str, object]:
    merged = dict(parser)
    for k, v in (scraper or {}).items():
        if v is None: continue
        if isinstance(v, str) and not v.strip(): continue
        if k in SCRAPER_PRIORITY_FIELDS:
            merged[k] = v
        else:
            if k not in merged or merged.get(k) in (None, "", MISSING, []): merged[k] = v
    if merged.get("references") and merged.get("processo") not in (None, "", MISSING):
        merged["references"] = remove_self_reference(list(merged["references"]), str(merged["processo"]))
        merged["linked_processes"] = merged["references"]
    if merged.get("tribunal_type") == "TCU":
        merged["uf"] = MISSING
        merged["region"] = MISSING
    return merged
