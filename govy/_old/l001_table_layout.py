# src/govy/extractors/l001_table_layout.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class ExtractResultList:
    values: List[str]
    evidence: Optional[str]
    score: int


# ------------ helpers de normalização ------------
def _norm(s: str) -> str:
    s = (s or "").replace("\uFFFD", "")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip(" \n\r\t,;-–—")


def _dedup_key(s: str) -> str:
    s = _norm(s).lower()
    s = re.sub(r"\bcep[:\s]*\d{2}\.?\d{3}[-.]?\d{3}\b", "", s, flags=re.I)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


# ------------ critérios de endereço ------------
LOGRADOURO_RE = re.compile(r"\b(rua|r\.|avenida|av\.?|estrada|travessa|alameda|largo|praça|praca)\b", re.I)
BR_RODOVIA_RE = re.compile(r"\bBR[-\s]?\d{2,3}\b", re.I)
PR_RODOVIA_RE = re.compile(r"\bPR[-\s]?\d{2,3}\b", re.I)
NUM_RE = re.compile(r"\b(\d{1,5}|SN|S/N)\b", re.I)


def _is_valid_address(endereco: str, numero: str = "") -> bool:
    s = _norm((endereco or "") + " " + (numero or ""))
    low = s.lower()

    has_street = LOGRADOURO_RE.search(s) is not None
    has_rodovia = (BR_RODOVIA_RE.search(s) is not None) or (PR_RODOVIA_RE.search(s) is not None)
    if not (has_street or has_rodovia):
        return False

    if low.startswith("br") and BR_RODOVIA_RE.search(s) is None:
        return False

    if not (NUM_RE.search(s) or " km" in low):
        return False

    return True


# ------------ extração por layout ------------
def _get_words(textract_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    blocks = textract_json.get("Blocks") or []
    words = [b for b in blocks if b.get("BlockType") == "WORD" and b.get("Text")]
    out = []
    for w in words:
        bb = (((w.get("Geometry") or {}).get("BoundingBox")) or {})
        out.append({
            "text": str(w.get("Text")),
            "page": int(w.get("Page") or 1),
            "top": float(bb.get("Top") or 0.0),
            "left": float(bb.get("Left") or 0.0),
            "width": float(bb.get("Width") or 0.0),
        })
    return out


def _norm_header_token(t: str) -> str:
    t = _norm(t).lower()
    t = t.replace("ç", "c").replace("ã", "a").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    t = re.sub(r"[^a-z0-9]", "", t)
    return t


HEADER_CANON = {
    "cod": {"cod", "codmec", "mec"},
    "nre": {"nre"},
    "mun": {"mun", "municipio", "cidade"},
    "estab": {"estabelecimento", "escola", "unidade"},
    "end": {"endereco"},
    "num": {"n", "no", "numero"},
    "bairro": {"bairro"},
    "tel": {"telefone", "fone"},
}


def _find_header_row(words: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Encontra a linha de cabeçalho procurando tokens como ENDERECO/BAIRRO/TELEFONE próximos no TOP.
    Retorna: {"page": p, "top": t, "cols": {colname: left}}
    """
    # agrupa por (page, top_bucket)
    buckets: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
    for w in words:
        key = (w["page"], int(w["top"] * 1000))  # bucket fino por top
        buckets.setdefault(key, []).append(w)

    best = None
    best_score = 0

    for (page, topk), ws in buckets.items():
        # junta tokens normalizados
        tokens = [_norm_header_token(x["text"]) for x in ws]
        # pontua presença de colunas
        present = set()
        for tok, obj in zip(tokens, ws):
            for col, variants in HEADER_CANON.items():
                if tok in variants:
                    present.add(col)

        # precisamos de pelo menos END + BAIRRO + TEL para ter certeza que é a tabela certa
        score = 0
        for must in ["end", "bairro", "tel"]:
            if must in present:
                score += 3
        for extra in ["mun", "estab", "num"]:
            if extra in present:
                score += 1

        if score > best_score:
            best_score = score
            best = (page, topk, ws, tokens)

    if not best or best_score < 7:
        return None

    page, topk, ws, tokens = best

    cols: Dict[str, float] = {}
    for tok, obj in zip(tokens, ws):
        for col, variants in HEADER_CANON.items():
            if tok in variants:
                # guarda a posição mais à esquerda daquele "rótulo"
                cols[col] = min(cols.get(col, 1.0), obj["left"])

    return {"page": page, "topk": topk, "cols": cols, "score": best_score}


def _make_col_boundaries(cols_left: Dict[str, float]) -> List[Tuple[str, float, float]]:
    """
    Converte posições left das colunas em intervalos [L, R).
    """
    items = sorted(cols_left.items(), key=lambda x: x[1])
    bounds = []
    for i, (name, left) in enumerate(items):
        right = 1.0
        if i + 1 < len(items):
            right = (left + items[i + 1][1]) / 2.0
        bounds.append((name, left - 0.01, right))  # pequena folga
    return bounds


def _assign_col(x_left: float, boundaries: List[Tuple[str, float, float]]) -> Optional[str]:
    for name, L, R in boundaries:
        if L <= x_left < R:
            return name
    return None


def extract_l001_from_table_layout(textract_json: Dict[str, Any]) -> ExtractResultList:
    words = _get_words(textract_json)
    if not words:
        return ExtractResultList(values=[], evidence=None, score=0)

    header = _find_header_row(words)
    if not header:
        return ExtractResultList(values=[], evidence=None, score=0)

    page0 = header["page"]
    topk0 = header["topk"]
    boundaries = _make_col_boundaries(header["cols"])

    # pega palavras a partir do header (inclusive páginas seguintes)
    # e agrupa em linhas visuais por (page, row_bucket)
    rows: Dict[Tuple[int, int], Dict[str, List[str]]] = {}

    for w in words:
        if w["page"] < page0:
            continue
        # ignora o próprio header (mesmo top bucket) na página inicial
        if w["page"] == page0 and int(w["top"] * 1000) == topk0:
            continue

        col = _assign_col(w["left"], boundaries)
        if not col:
            continue

        # agrupa por linha visual (bucket top mais grosso)
        row_bucket = int(w["top"] * 100)  # mais grosso para juntar palavras na mesma linha
        key = (w["page"], row_bucket)
        rows.setdefault(key, {}).setdefault(col, []).append(w["text"])

    # monta endereços
    found: List[str] = []
    seen = set()
    evidence_lines: List[str] = []

    # ordena as linhas por page e top
    for (page, rb) in sorted(rows.keys(), key=lambda x: (x[0], x[1])):
        r = rows[(page, rb)]
        end = _norm(" ".join(r.get("end", [])))
        num = _norm(" ".join(r.get("num", [])))
        bairro = _norm(" ".join(r.get("bairro", [])))
        mun = _norm(" ".join(r.get("mun", [])))

        # se não tem endereco, não é linha da tabela
        if not end:
            continue

        # normaliza num
        num = num.upper().replace("S/N", "SN")

        # valida endereço
        if not _is_valid_address(end, num):
            continue

        parts = []
        if mun:
            parts.append(mun)
        # endereço completo
        addr = end
        if num and num not in ("0",):
            addr = f"{addr} {num}"
        if bairro:
            addr = f"{addr} - {bairro}"

        loc = _norm(addr)
        k = _dedup_key(loc)
        if not k or k in seen:
            continue
        seen.add(k)
        found.append(loc)

        if len(evidence_lines) < 10:
            evidence_lines.append(f"[p{page}] {loc}")

    score = 0
    if found:
        score = 14 + min(10, len(found) // 200)

    evidence = None
    if evidence_lines:
        evidence = "Amostra (10):\n" + "\n".join(evidence_lines)

    return ExtractResultList(values=found, evidence=evidence, score=score)
