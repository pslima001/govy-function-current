# src/govy/io/textract_reader.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class TextractReadResult:
    """
    Resultado padronizado da camada 1 (Textract-first).
    - text: texto linearizado (linhas ordenadas por Page/Top/Left)
    - table_cells: lista de textos de células (útil p/ tabelas)
    - meta: métricas básicas p/ quality gate
    - textract_json: JSON completo do Textract (Blocks com Geometry/BoundingBox)
    """
    text: str
    table_cells: List[str]
    meta: Dict[str, Any]
    textract_json: Dict[str, Any]



def load_textract_json(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Textract JSON não encontrado: {p}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _bbox_key(block: Dict[str, Any]) -> Tuple[int, float, float]:
    page = int(block.get("Page") or 1)
    bbox = (((block.get("Geometry") or {}).get("BoundingBox")) or {})
    top = float(bbox.get("Top") or 0.0)
    left = float(bbox.get("Left") or 0.0)
    return (page, top, left)


def extract_lines_in_reading_order(textract: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Retorna blocos LINE ordenados por Page, Top, Left.
    Serve bem para a maioria dos editais (não perfeito em layouts complexos).
    """
    blocks = textract.get("Blocks") or []
    lines = [b for b in blocks if b.get("BlockType") == "LINE" and b.get("Text")]
    lines.sort(key=_bbox_key)
    return lines


def _clean_text(s: str) -> str:
    if not s:
        return ""
    # remove caracteres "quebrados" comuns (replacement char)
    s = s.replace("\uFFFD", "")  # '�'
    # normaliza espaços
    s = re.sub(r"[ \t]+", " ", s)
    # normaliza quebras excessivas
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def join_text_from_lines(lines: List[Dict[str, Any]]) -> str:
    raw = "\n".join([str(l.get("Text") or "").strip() for l in lines if l.get("Text")])
    # remove '�' e normaliza espaços
    raw = raw.replace("\uFFFD", "")
    raw = re.sub(r"[ \t]+", " ", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()




def extract_table_cells(textract: Dict[str, Any]) -> List[str]:
    """
    Extrai textos dos blocos CELL.
    Ajuda muito quando endereços/prazos ficam presos em tabelas.
    """
    out: List[str] = []
    blocks = textract.get("Blocks") or []
    for b in blocks:
        if b.get("BlockType") == "CELL":
            txt = str(b.get("Text") or "")
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                out.append(txt)
    return out


def compute_basic_meta(text: str, lines: List[Dict[str, Any]], table_cells: List[str]) -> Dict[str, Any]:
    """
    Métricas simples para o quality gate:
    - n_chars_text: tamanho do texto
    - n_lines: quantidade de linhas
    - n_table_cells: quantidade de células com texto
    - has_many_garbled_tokens: heurística simples de "texto quebrado"
    """
    n_chars = len(text)
    n_lines = len(lines)
    n_cells = len(table_cells)

    # Heurística simples: muitas sequências estranhas podem indicar OCR ruim
    # (ex.: 'IIII', 'l l l', símbolos repetidos)
    garbled_hits = 0
    sample = text[:20000].lower()
    if re.search(r"(?:\b[i|l]{5,}\b)|(?:[^\w\s]{8,})", sample):
        garbled_hits += 1

    return {
        "n_chars_text": n_chars,
        "n_lines": n_lines,
        "n_table_cells": n_cells,
        "garbled_flag": bool(garbled_hits),
    }


def read_textract(path: str | Path, nome_pdf: Optional[str] = None) -> TextractReadResult:
    """
    Função principal da camada 1.
    Entrada: caminho do JSON do Textract (analyzeDocResponse.json ou similar).
    Saída: TextractReadResult padronizado.
    """
    tj = load_textract_json(path)
    lines = extract_lines_in_reading_order(tj)
    text = join_text_from_lines(lines)
    cells = extract_table_cells(tj)
    meta = compute_basic_meta(text=text, lines=lines, table_cells=cells)

    if nome_pdf:
        meta["arquivo"] = nome_pdf
    meta["textract_json_path"] = str(Path(path))

    return TextractReadResult(text=text, table_cells=cells, meta=meta, textract_json=tj)
    