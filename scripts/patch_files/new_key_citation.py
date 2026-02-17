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
