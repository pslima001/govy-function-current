import json
import os
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import azure.functions as func
from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

from govy.run.extract_all import extract_all_params


# =========================================================
# TRIGGERS semânticos (só removemos se a linha estiver em header/footer)
# =========================================================

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(\+?55\s*)?(\(?\d{2}\)?\s*)?\d{4,5}[-\s]?\d{4}\b")

ADDRESS_HINT_RE = re.compile(
    r"\b(rua|av\.?|avenida|praça|travessa|rodovia|km|bairro|centro|cep|nº|no\.?|s/n)\b",
    re.IGNORECASE,
)
CEP_RE = re.compile(r"\b\d{2}\.?\d{3}-?\d{3}\b", re.IGNORECASE)
CNPJ_RE = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b", re.IGNORECASE)

ORG_KEYWORDS = [
    "consórcio municipal", "consorcio municipal",
    "consórcio estadual", "consorcio estadual",
    "prefeitura", "município", "municipio", "câmara", "camara",
    "batalhão", "batalhao",
    "ministério", "ministerio",
    "exército", "exercito", "marinha", "aeronáutica", "aeronautica",
    "tribunal", "hospital", "faculdade", "instituto", "escola",
    "agência", "agencia",
    "banco", "caixa",
    "conselho", "controladoria",
    "departamento", "empresa",
    "fundação", "fundacao",
    "fundo",
    "gabinete", "museu",
    "polícia", "policia",
    "presidência", "presidencia",
    "procuradoria", "secretaria",
    "senado", "congresso",
    "sebrae", "senai", "sesc",
]
ORG_KEYWORDS_NORM = [k.lower() for k in ORG_KEYWORDS]


# =========================================================
# Normalização de texto + ruído (inclui “ruído dentro da linha”)
# =========================================================

def _norm_line(s: str) -> str:
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    s = s.lower()
    s = s.replace("–", "-").replace("—", "-")
    return s


def _is_noise_line(n: str) -> bool:
    if not n or len(n) <= 1:
        return True
    if re.fullmatch(r"(p[aá]gina|pag)\s*\d+(\s*(de|/)\s*\d+)?", n):
        return True
    if re.fullmatch(r"fls\.?\s*\d+", n):
        return True
    if re.fullmatch(r"[-_*•\s]+", n):
        return True
    return False


NON_LATIN_RE = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff]")  # CJK
VOWELS_RE = re.compile(r"[aeiouáéíóúãõàêô]", re.IGNORECASE)

# ✅ V6.4.1: tokens OCR internos mais abrangentes
# Exemplos cobertos: REFFITVE, REFFITVA, REFFITYF, REFFITUJE, REFITVE, BEFFATVA, BEFFATVIA...
INTERNAL_OCR_TOKENS_RE = re.compile(
    r"\b("
    r"re+f+it+[a-z]{1,10}"        # reffit + sufixo
    r"|ref+it+[a-z]{1,10}"        # refit + sufixo
    r"|be+f+at+[a-z]{1,10}"       # beffat + sufixo
    r"|b+e*f+f+at+[a-z]{1,10}"    # variações
    r")\b",
    re.IGNORECASE,
)

def _strip_internal_ocr_tokens(raw: str) -> str:
    """Remove tokens OCR típicos mesmo quando aparecem no meio da linha."""
    if not raw:
        return raw
    out = INTERNAL_OCR_TOKENS_RE.sub("", raw)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def _is_linguistic_noise(raw: str, n: str) -> bool:
    if not raw:
        return True
    if NON_LATIN_RE.search(raw):
        return True

    if len(n) <= 2:
        if re.fullmatch(r"(kg|un|und|r\$|ce|sp|rj|mg|\d+)", n):
            return False
        return True

    if re.fullmatch(r"[\W_]+", n):
        return True

    letters = re.findall(r"[a-zà-ÿ]", n, flags=re.IGNORECASE)
    if len(letters) >= 6:
        vowels = VOWELS_RE.findall(n)
        if (len(vowels) / max(1, len(letters))) < 0.20:
            return True

    if re.search(r"(.)\1\1\1", n):
        return True

    return False


def _contains_org_keyword(n: str) -> bool:
    return any(k in n for k in ORG_KEYWORDS_NORM)


def _semantic_trigger(text: str) -> bool:
    if not text:
        return False
    if EMAIL_RE.search(text):
        return True
    if PHONE_RE.search(text):
        return True
    if CEP_RE.search(text):
        return True
    if CNPJ_RE.search(text):
        return True
    if ADDRESS_HINT_RE.search(text):
        return True
    if _contains_org_keyword(_norm_line(text)):
        return True
    return False


# =========================================================
# Geometria (Y) + fallback por ordem (mantém V6.3)
# =========================================================

def _line_y_bounds_norm(line, page_height: float) -> Tuple[float, float, bool]:
    poly = getattr(line, "polygon", None) or getattr(line, "bounding_polygon", None) or []
    ys = []
    for p in poly:
        y = getattr(p, "y", None)
        if y is not None:
            ys.append(float(y))
    if not ys or not page_height:
        return (0.5, 0.5, False)
    return (min(ys) / page_height, max(ys) / page_height, True)


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    k = int(round((len(v) - 1) * p))
    k = max(0, min(k, len(v) - 1))
    return v[k]


def calibrate_header_footer_y_v63(
    result,
    default_header_y_max: float = 0.18,
    default_footer_y_min: float = 0.88,
    header_top_cap: float = 0.35,
    footer_bottom_cap: float = 0.65,
) -> Tuple[float, float, Dict[str, Any]]:
    pages = getattr(result, "pages", None) or []
    if not pages:
        return default_header_y_max, default_footer_y_min, {"mode": "fallback_no_pages"}

    top_trigger_ys: List[float] = []
    bottom_trigger_ys: List[float] = []

    all_line_ymins: List[float] = []
    all_lines_norm_in_doc: List[str] = []
    line_records: List[Tuple[str, float]] = []

    geom_total = 0
    geom_valid = 0

    for p in pages:
        page_h = float(getattr(p, "height", 0) or 0)
        lines = getattr(p, "lines", None) or []
        for line in lines:
            raw = (getattr(line, "content", "") or "").strip()
            if not raw:
                continue
            n = _norm_line(raw)
            if not n:
                continue

            y_min_n, y_max_n, ok = _line_y_bounds_norm(line, page_h)
            geom_total += 1
            if ok:
                geom_valid += 1

            y_center = (y_min_n + y_max_n) / 2.0
            all_line_ymins.append(y_min_n)
            all_lines_norm_in_doc.append(n)
            line_records.append((n, y_center))

            if _semantic_trigger(raw):
                if y_center <= 0.50:
                    top_trigger_ys.append(y_max_n)
                else:
                    bottom_trigger_ys.append(y_min_n)

    geom_quality = geom_valid / max(1, geom_total)

    debug = {
        "mode": None,
        "top_trigger_count": len(top_trigger_ys),
        "bottom_trigger_count": len(bottom_trigger_ys),
        "geom_quality": geom_quality,
    }

    # Se não houver geometria, vai cair no fallback_line_order
    # Então aqui basta devolver os defaults.
    debug.update({"mode": "auto_repeated_or_geom", "header_y_max": default_header_y_max, "footer_y_min": default_footer_y_min})
    return default_header_y_max, default_footer_y_min, debug


def _region_by_y(y_min_n: float, y_max_n: float, header_y_max: float, footer_y_min: float) -> str:
    if y_max_n <= header_y_max:
        return "header"
    if y_min_n >= footer_y_min:
        return "footer"
    return "body"


# =========================================================
# Fallback por ordem (top/bottom) + remoção de número solto (mantém V6.4)
# =========================================================

MONEY_OR_DECIMAL_RE = re.compile(r"(r\$\s*)?[-+]?\s*[\d\.\s]+,\s*\d{1,2}", re.IGNORECASE)

def clean_content_fallback_line_order(
    pages: List[List[Tuple[str, str]]],
    top_n: int = 8,
    bottom_n: int = 8,
    repeat_ratio: float = 0.60
) -> Tuple[str, Dict[str, Any]]:
    hf_norms: List[str] = []
    per_page: List[List[Tuple[str, str, str]]] = []

    for items in pages:
        norms = [n for _, n in items]
        n_total = len(norms)
        top_idx = set(range(0, min(top_n, n_total)))
        bottom_idx = set(range(max(0, n_total - bottom_n), n_total))

        page_regs: List[Tuple[str, str, str]] = []
        for i, (raw, n) in enumerate(items):
            if i in top_idx:
                region = "header"
            elif i in bottom_idx:
                region = "footer"
            else:
                region = "body"

            page_regs.append((raw, n, region))
            if region in ("header", "footer") and not _is_noise_line(n):
                hf_norms.append(n)

        per_page.append(page_regs)

    cnt = Counter(hf_norms)
    threshold = max(2, int(len(per_page) * repeat_ratio))
    repeated_hf = {k for k, v in cnt.items() if v >= threshold}

    removed_stats = {
        "removed_noise": 0,
        "removed_linguistic_noise": 0,
        "removed_repeated_hf": 0,
        "removed_semantic_hf": 0,
        "removed_internal_ocr_tokens": 0,
        "removed_lonely_numbers": 0,
    }

    cleaned_pages: List[str] = []
    for page_regs in per_page:
        kept_lines: List[str] = []

        for raw, n, region in page_regs:
            if _is_noise_line(n):
                removed_stats["removed_noise"] += 1
                continue

            raw2 = _strip_internal_ocr_tokens(raw)
            if raw2 != raw:
                removed_stats["removed_internal_ocr_tokens"] += 1
            raw = raw2
            n = _norm_line(raw)

            if not raw or _is_linguistic_noise(raw, n):
                removed_stats["removed_linguistic_noise"] += 1
                continue

            if region in ("header", "footer") and n in repeated_hf:
                removed_stats["removed_repeated_hf"] += 1
                continue

            if region in ("header", "footer") and _semantic_trigger(raw):
                removed_stats["removed_semantic_hf"] += 1
                continue

            kept_lines.append(raw)

        # remover “número solto” entre dois valores monetários
        kept2: List[str] = []
        for i, line in enumerate(kept_lines):
            n = _norm_line(line)
            if re.fullmatch(r"\d{1,3}", n):
                prev_line = kept_lines[i - 1] if i > 0 else ""
                next_line = kept_lines[i + 1] if i + 1 < len(kept_lines) else ""
                if (MONEY_OR_DECIMAL_RE.search(prev_line) and MONEY_OR_DECIMAL_RE.search(next_line)):
                    removed_stats["removed_lonely_numbers"] += 1
                    continue
            kept2.append(line)

        page_text = "\n".join(kept2).strip()
        if page_text:
            cleaned_pages.append(page_text)

    clean = "\n\n=== PAGE BREAK ===\n\n".join(cleaned_pages).strip()
    debug = {
        "mode": "fallback_line_order",
        "top_n": top_n,
        "bottom_n": bottom_n,
        "repeat_ratio": repeat_ratio,
        "repeated_hf_count": len(repeated_hf),
        "removed_stats": removed_stats,
    }
    return clean, debug


def clean_content_by_page_using_y_or_fallback(
    result,
    header_y_max: float,
    footer_y_min: float,
    repeat_ratio: float,
    geom_quality: float,
    geom_quality_threshold: float = 0.70
) -> Tuple[str, Dict[str, Any]]:
    pages = getattr(result, "pages", None) or []
    if not pages:
        return (getattr(result, "content", "") or "").strip(), {"mode": "fallback_no_pages"}

    per_page_simple: List[List[Tuple[str, str]]] = []

    for p in pages:
        lines = getattr(p, "lines", None) or []
        simple_items: List[Tuple[str, str]] = []

        for line in lines:
            raw = (getattr(line, "content", "") or "").strip()
            if not raw:
                continue

            # ✅ V6.4.1: strip interno antes de tudo
            raw = _strip_internal_ocr_tokens(raw)

            n = _norm_line(raw)
            if not n:
                continue
            simple_items.append((raw, n))

        per_page_simple.append(simple_items)

    # como os seus docs estão com geom_quality ~0, vamos direto pro fallback
    clean, dbg = clean_content_fallback_line_order(per_page_simple, top_n=8, bottom_n=8, repeat_ratio=repeat_ratio)
    dbg["geom_quality"] = geom_quality
    dbg["geom_quality_threshold"] = geom_quality_threshold
    return clean, dbg


# =========================================================
# Normalização numérica (blindada) — mantém V6.3
# =========================================================

OCR_DOT_SPLIT_RE = re.compile(r"(?<!\d)(\d)\s*\.\s*(\d)\s*(\d)(?!\d)")

def _numeric_likeness_ratio(s: str) -> float:
    if not s:
        return 0.0
    allowed = re.findall(r"[0-9\.,\s\-\+rR\$]", s)
    return len(allowed) / max(1, len(s))


def normalize_number_ptbr(text: str) -> Optional[str]:
    if not text:
        return None
    raw = text.strip()

    if raw.count(",") >= 2:
        return None

    if _numeric_likeness_ratio(raw) < 0.70:
        return None

    raw = OCR_DOT_SPLIT_RE.sub(r"\1.\2\3", raw)

    matches = list(MONEY_OR_DECIMAL_RE.finditer(raw))
    if matches:
        raw = matches[-1].group(0)
    else:
        if re.search(r"[A-Za-zÀ-ÿ]", raw):
            return None

    raw = re.sub(r"(?i)r\$\s*", "", raw)
    raw = re.sub(r"\s+", "", raw)
    raw = raw.replace(".", "").replace(",", ".")

    if re.fullmatch(r"[-+]?\d+(\.\d{1,2})?", raw):
        if re.fullmatch(r"[-+]?\d+\.\d$", raw):
            raw += "0"
        return raw
    return None


def normalize_tables(tables: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    fixes: List[Dict[str, Any]] = []
    tables_norm: List[Dict[str, Any]] = []

    for tb in tables:
        tb2 = dict(tb)
        new_cells = []
        for c in tb.get("cells", []):
            c2 = dict(c)
            raw = c2.get("text", "")
            norm = normalize_number_ptbr(raw)
            if norm is not None and norm != raw:
                c2["text_norm"] = norm
                fixes.append({
                    "table_index": tb.get("table_index"),
                    "row": c2.get("row"),
                    "col": c2.get("col"),
                    "raw": raw,
                    "norm": norm,
                })
            new_cells.append(c2)
        tb2["cells"] = new_cells
        tables_norm.append(tb2)

    return tables_norm, fixes


# =========================================================
# Azure Function
# =========================================================

app = func.FunctionApp()


@app.function_name(name="parse_layout")
@app.route(route="parse_layout", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def parse_layout(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = req.get_json()
        blob_name = body.get("blob_name")
        if not blob_name:
            raise ValueError("Campo obrigatório: blob_name")
    except Exception:
        return func.HttpResponse(
            json.dumps({"error": "Envie JSON: {\"blob_name\": \"arquivo.pdf\"}"}),
            status_code=400,
            mimetype="application/json",
        )

    try:
        conn_str = os.environ["STORAGE_CONNECTION_STRING"]
        container = os.environ["BLOB_CONTAINER"]

        bsc = BlobServiceClient.from_connection_string(conn_str)
        blob = bsc.get_blob_client(container=container, blob=blob_name)
        pdf_bytes = blob.download_blob().readall()

        endpoint = os.environ["DOCINTEL_ENDPOINT"]
        key = os.environ["DOCINTEL_KEY"]

        client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
        poller = client.begin_analyze_document(
            "prebuilt-layout",
            body=pdf_bytes,
            content_type="application/pdf",
        )
        result = poller.result()

        tables: List[Dict[str, Any]] = []
        for t_idx, table in enumerate(result.tables or []):
            cells = []
            for cell in table.cells:
                cells.append({
                    "row": cell.row_index,
                    "col": cell.column_index,
                    "text": (cell.content or "").strip(),
                })
            tables.append({
                "table_index": t_idx,
                "row_count": table.row_count,
                "column_count": table.column_count,
                "cells": cells,
            })

        header_y_max, footer_y_min, calib_debug = calibrate_header_footer_y_v63(result)
        geom_quality = calib_debug.get("geom_quality", 0.0)

        content_raw = (result.content or "")
        content_clean, clean_debug = clean_content_by_page_using_y_or_fallback(
            result,
            header_y_max=header_y_max,
            footer_y_min=footer_y_min,
            repeat_ratio=0.60,
            geom_quality=geom_quality,
            geom_quality_threshold=0.70,
        )

        tables_norm, number_fixes = normalize_tables(tables)

        payload = {
            "blob_name": blob_name,
            "content_raw": content_raw,
            "content_clean": content_clean,
            "tables_norm": tables_norm,
            "number_fixes": number_fixes,
            "calibration_debug": calib_debug,
            "cleaning_debug": clean_debug,
        }

        return func.HttpResponse(
            json.dumps(payload, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json",
        )


@app.function_name(name="extract_params")
@app.route(route="extract_params", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def extract_params(req: func.HttpRequest) -> func.HttpResponse:
    """
    Pipeline completo (Azure DI -> limpeza -> tabelas -> parâmetros).
    Espera JSON: {"blob_name": "..."}.
    Retorna: {"blob_name":..., "params": {...}, "content_clean": "...", "tables_norm": [...]}.
    """
    try:
        body = req.get_json()
        blob_name = body.get("blob_name")
        include_debug = bool(body.get("include_debug", False))

        if not blob_name:
            return func.HttpResponse(
                json.dumps({"error": "blob_name é obrigatório"}, ensure_ascii=False),
                status_code=400,
                mimetype="application/json",
            )

        # ---- baixar PDF do Blob ----
        blob_service = BlobServiceClient.from_connection_string(os.environ["AZURE_STORAGE_CONNECTION_STRING"])
        container = os.environ["BLOB_CONTAINER_NAME"]
        blob_client = blob_service.get_blob_client(container=container, blob=blob_name)
        pdf_bytes = blob_client.download_blob().readall()

        # ---- analisar com Azure DI (prebuilt-layout) ----
        endpoint = os.environ["AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT"]
        key = os.environ["AZURE_DOCUMENT_INTELLIGENCE_KEY"]
        client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))

        poller = client.begin_analyze_document("prebuilt-layout", pdf_bytes)
        result = poller.result()

        content_raw = (result.content or "")

        # tabelas normalizadas (DI)
        tables: List[Dict[str, Any]] = []
        for t_idx, table in enumerate(result.tables or []):
            cells = []
            for cell in table.cells:
                cells.append({
                    "row": cell.row_index,
                    "col": cell.column_index,
                    "text": (cell.content or "").strip(),
                })
            tables.append({
                "table_index": t_idx,
                "row_count": table.row_count,
                "column_count": table.column_count,
                "cells": cells,
            })

        header_y_max, footer_y_min, calib_debug = calibrate_header_footer_y_v63(result)
        geom_quality = calib_debug.get("geom_quality", 0.0)

        content_clean = remove_header_footer_v63(
            result,
            header_y_max=header_y_max,
            footer_y_min=footer_y_min,
            repeat_ratio=0.60,
            geom_quality=geom_quality,
            geom_quality_threshold=0.70,
        )

        tables_norm, number_fixes = normalize_tables(tables)

        params = extract_all_params(content_clean=content_clean, tables_norm=tables_norm, include_debug=include_debug)

        payload = {
            "blob_name": blob_name,
            "params": params,
            # Mantemos para debug/inspeção no front-end simples
            "content_clean": content_clean,
            "tables_norm": tables_norm,
            "number_fixes": number_fixes,
        }
        if include_debug:
            payload["calibration_debug"] = calib_debug
            payload["geom_quality"] = geom_quality
            payload["header_y_max"] = header_y_max
            payload["footer_y_min"] = footer_y_min

        return func.HttpResponse(
            json.dumps(payload, ensure_ascii=False),
            status_code=200,
            mimetype="application/json",
        )

    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json",
        )
