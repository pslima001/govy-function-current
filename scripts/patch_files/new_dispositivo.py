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

    m_end = re.search(end_pattern, window, flags=re.IGNORECASE | re.DOTALL)
    if m_end:
        bloco = window[:m_end.start()]
    else:
        bloco = window[:6000]

    bloco = re.sub(r"\s+", " ", bloco).strip()
    if len(bloco) < 80:
        return MISSING
    return bloco
