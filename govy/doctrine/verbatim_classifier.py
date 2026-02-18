from __future__ import annotations
import re


def is_verbatim_legal_text(text: str) -> bool:
    """Detecta se o texto é conteúdo literal de tribunal/corte (acórdão, decisão, ementa, voto)."""
    if not text or len(text.strip()) < 50:
        return False
    text_lower = text.lower()
    STRONG_PATTERNS = [
        r"\bac[oó]rd[aã]o\s+n[úo]?\s*\d+",
        r"\brelator[:\s]",
        r"\bementa\b",
        r"\bvoto\b",
        r"\bplen[aá]rio\b",
        r"\bturma\b",
        r"\bc[aâ]mara\b",
        r"\bprocesso\s+n[úo]?\s*\d+",
        r"\bresp\s+\d+",
        r"\bre\s+\d+",
        r"\badi\s+\d+",
        r"\bms\s+\d+",
    ]
    for pat in STRONG_PATTERNS:
        if re.search(pat, text_lower, flags=re.IGNORECASE):
            return True
    MEDIUM_PATTERNS = [
        r"\btcu\b",
        r"\bstj\b",
        r"\bstf\b",
        r"\btj[a-z]{1,3}\b",
        r"\bdesembargador\b",
        r"\bju[ií]z\b",
        r"\bministro\b",
        r"\bdecide-se\b",
        r"\bajulgo\b",
        r"\bacordam\b",
        r"\bante\s+o\s+exposto\b",
    ]
    medium_count = sum(1 for pat in MEDIUM_PATTERNS if re.search(pat, text_lower, flags=re.IGNORECASE))
    return medium_count >= 2
