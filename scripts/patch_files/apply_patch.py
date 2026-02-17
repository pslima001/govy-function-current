"""
apply_patch.py - Aplica melhorias no tce_parser_v3.py
Uso: python scripts/apply_patch.py
Deve estar no diretorio C:/govy/repos/govy-function-current
"""
import os, sys, shutil

PARSER = os.path.join("govy", "api", "tce_parser_v3.py")
PATCH_DIR = os.path.join("scripts", "patch_files")

REPLACEMENTS = [
    ("def extract_dispositivo(text: str) -> str:", "new_dispositivo.py"),
    ("def classify_outcome_effect_from_dispositivo(dispositivo: str) -> Tuple[str, str]:", "new_classify.py"),
    ("def extract_key_citation(dispositivo: str) -> Tuple[str, str, str]:", "new_key_citation.py"),
]

def find_func_end(lines, start):
    end = start + 1
    while end < len(lines):
        l = lines[end]
        if l.strip() and not l[0].isspace():
            if l.startswith("def ") or l.startswith("class ") or l.startswith("# ==="):
                break
        end += 1
    return end

def main():
    if not os.path.exists(PARSER):
        print(f"ERRO: {PARSER} nao encontrado! CWD={os.getcwd()}")
        sys.exit(1)

    shutil.copy2(PARSER, PARSER + ".bak")
    print(f"Backup: {PARSER}.bak")

    with open(PARSER, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # Encontrar ranges (de tras pra frente)
    ops = []
    for sig, filename in REPLACEMENTS:
        filepath = os.path.join(PATCH_DIR, filename)
        if not os.path.exists(filepath):
            print(f"ERRO: {filepath} nao encontrado!")
            sys.exit(1)
        start = None
        for i, line in enumerate(lines):
            if line.strip().startswith(sig):
                start = i
                break
        if start is None:
            print(f"AVISO: '{sig[:50]}...' nao encontrado no parser")
            continue
        end = find_func_end(lines, start)
        print(f"  {filename}: linhas {start+1}-{end} ({end-start} linhas)")
        with open(filepath, "r", encoding="utf-8") as f:
            new_code = f.read()
        ops.append((start, end, new_code))

    # Aplicar de tras pra frente
    ops.sort(key=lambda x: x[0], reverse=True)
    for start, end, new_code in ops:
        new_lines = new_code.rstrip("\n") + "\n\n"
        lines[start:end] = [new_lines]

    with open(PARSER, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"\nAtualizado: {PARSER}")
    import py_compile
    try:
        py_compile.compile(PARSER, doraise=True)
        print("COMPILACAO OK!")
    except py_compile.PyCompileError as e:
        print(f"ERRO: {e}")
        shutil.copy2(PARSER + ".bak", PARSER)
        print("Backup restaurado.")
        sys.exit(1)

if __name__ == "__main__":
    main()
