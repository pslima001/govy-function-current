def classify_outcome_effect_from_dispositivo(dispositivo: str) -> Tuple[str, str]:
    if not dispositivo or dispositivo == MISSING:
        return MISSING, MISSING
    d = safe_upper(dispositivo)

    holding = MISSING
    if re.search(r"\bMULTA\b|\bAPLICA[\xc7C][\xc3A]O\s+DE\s+MULTA\b|\bPENALIDADE\b|\bCONDENA\b|\bRESSARCIMENTO\b|\bSAN[\xc7C][\xc3A]O\b|\bIMPOSI[\xc7C][\xc3A]O\s+DE\s+MULTA\b", d):
        holding = "SANCIONOU"
    elif re.search(r"\bDETERMINA\b|\bDETERMINOU\b|\bRECOMENDA\b|\bALERTA\b|\bCI[\xcaE]NCIA\b|\bADEQUA[\xc7C][\xc3A]O\b|\bCORRE[\xc7C][\xc3A]O\b|\bFIXAR\s+PRAZO\b|\bDETERMINA[\xc7C][\xc3A]O\b|\bRESSALVAS?\b", d):
        holding = "DETERMINOU_AJUSTE"
    elif re.search(r"\bAFASTAR\b|\bAFASTOU\b|\bREJEITAR\b|\bREJEITOU\b|\bIMPROCEDENTE\b|\bIMPROCED[\xcaE]NCIA\b|\bN[\xc3A]O\s+CONHECER\b|\bNEGAR\s+PROVIMENTO\b|\bNEGOU\s+PROVIMENTO\b|\bINDEFERIR\b", d):
        holding = "AFASTOU"
    elif re.search(r"\bREGULAR\b|\bREGULARIDADE\b|\bJULGAR\s+REGULAR\b|\bDAR\s+PROVIMENTO\b|\bDEU\s+PROVIMENTO\b|\bPROVIDO\b", d):
        holding = "ABSOLVEU"
    elif re.search(r"\bARQUIVAMENTO\b|\bARQUIVE-?SE\b|\bARQUIVAR\b|\bARQUIVOU\b", d):
        holding = "ARQUIVOU"
    elif re.search(r"\bORIENTA[\xc7C][\xc3A]O\b|\bORIENTOU\b|\bESCLARECIMENTO\b", d):
        holding = "ORIENTOU"

    if holding != "SANCIONOU" and re.search(r"\bIRREGULARIDADE\b|\bIRREGULAR\b", d):
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
