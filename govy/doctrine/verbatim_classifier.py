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


def classify(chunk_content: str, source_text: str = "") -> dict:
    """Contract wrapper.

    Returns:
        {verbatim: bool, score: float}
    """
    if not chunk_content or not chunk_content.strip():
        return {"verbatim": False, "score": 0.0}

    is_verb = is_verbatim_legal_text(chunk_content)

    # Score heuristic: strong match = 1.0, medium = 0.6, none = 0.0
    text_lower = chunk_content.lower()
    strong = [
        r"\bac[oó]rd[aã]o\s+n[úo]?\s*\d+",
        r"\brelator[:\s]",
        r"\bementa\b",
        r"\bvoto\b",
        r"\bplen[aá]rio\b",
        r"\bturma\b",
        r"\bc[aâ]mara\b",
        r"\bprocesso\s+n[úo]?\s*\d+",
    ]
    medium = [
        r"\btcu\b",
        r"\bstj\b",
        r"\bstf\b",
        r"\btj[a-z]{1,3}\b",
        r"\bdesembargador\b",
        r"\bministro\b",
    ]
    strong_hits = sum(1 for p in strong if re.search(p, text_lower, re.IGNORECASE))
    medium_hits = sum(1 for p in medium if re.search(p, text_lower, re.IGNORECASE))

    if strong_hits > 0:
        score = min(0.7 + strong_hits * 0.1, 1.0)
    elif medium_hits >= 2:
        score = 0.5 + medium_hits * 0.05
    else:
        score = medium_hits * 0.15

    return {"verbatim": is_verb, "score": round(score, 2)}
