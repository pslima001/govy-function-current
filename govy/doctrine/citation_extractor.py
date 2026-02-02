from __future__ import annotations
import re
from typing import Dict, Optional

def extract_citation_meta(text: str) -> Dict[str, Optional[str]]:
    """Extrai metadados de citação de jurisprudência literal. Não inventa: só extrai o que existe no texto."""
    if not text:
        return {}
    result: Dict[str, Optional[str]] = {
        "tribunal": None,
        "orgao_julgador": None,
        "tipo_decisao": None,
        "numero": None,
        "processo": None,
        "relator": None,
        "data": None,
        "trecho_rotulo": None,
    }
    # Tribunal
    if re.search(r"\btcu\b", text, re.IGNORECASE):
        result["tribunal"] = "TCU"
    elif re.search(r"\bstj\b", text, re.IGNORECASE):
        result["tribunal"] = "STJ"
    elif re.search(r"\bstf\b", text, re.IGNORECASE):
        result["tribunal"] = "STF"
    else:
        m = re.search(r"\btj([a-z]{2})\b", text, re.IGNORECASE)
        if m:
            result["tribunal"] = f"TJ{m.group(1).upper()}"
    # Tipo decisão + número
    m = re.search(r"\b(ac[óo]rd[aã]o)\s+n[úo]?\s*([\d\.\/\-]+)", text, re.IGNORECASE)
    if m:
        result["tipo_decisao"] = "Acórdão"
        result["numero"] = m.group(2).strip()
    else:
        m = re.search(r"\b(ementa)\b", text, re.IGNORECASE)
        if m:
            result["tipo_decisao"] = "Ementa"
        m = re.search(r"\b(voto)\b", text, re.IGNORECASE)
        if m:
            result["tipo_decisao"] = "Voto"
    # Processo
    m = re.search(r"\bprocesso\s+n[úo]?\s*([\d\.\/\-]+)", text, re.IGNORECASE)
    if m:
        result["processo"] = m.group(1).strip()
    # Órgão julgador
    m = re.search(r"\b(plen[aá]rio|[\d]ª\s*turma|[\d]ª\s*c[aâ]mara)\b", text, re.IGNORECASE)
    if m:
        result["orgao_julgador"] = m.group(1).strip()
    # Relator
    m = re.search(r"\brelator[:\s]+([^\n\r,;\.]+)", text, re.IGNORECASE)
    if m:
        result["relator"] = m.group(1).strip()
    # Data
    m = re.search(r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b", text)
    if m:
        result["data"] = m.group(1).strip()
    # Trecho rótulo
    if re.search(r"\bementa\b", text, re.IGNORECASE):
        result["trecho_rotulo"] = "Ementa"
    elif re.search(r"\bvoto\b", text, re.IGNORECASE):
        result["trecho_rotulo"] = "Voto"
    return result
