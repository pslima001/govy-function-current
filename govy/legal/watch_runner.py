# govy/legal/watch_runner.py
"""
Runner reutilizavel para watch de listas gov.br/compras.

Pode ser chamado de:
  - scripts/watch_govbr_list.py (CLI)
  - function_app.py (timer trigger)

Funcoes publicas:
  - watch_govbr_all(): orquestra todas as listas, retorna resultado em memoria
  - process_list(): processa uma lista individual
  - generate_report_md(): gera relatorio Markdown (retorna string)
  - generate_report_json(): gera JSON agregado (retorna dict)
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import ssl
import time
from datetime import datetime, timezone
from typing import List, Optional
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from govy.legal.govbr_parser import (
    GOVBR_LISTS,
    ListItem,
    caption_to_doc_id,
    extract_revocation_from_title,
    parse_list_page,
)
from govy.legal.html_extractor import extract_html
from govy.legal.models import LegalDocumentRow
from govy.legal.legal_chunker import chunk_legal_text
from govy.legal.db_writer import write_document
from govy.legal.effective_date_extractor import extract_effective_dates, update_document_dates
from govy.legal.relation_extractor import (
    RelationMatch,
    extract_relations,
    write_relations,
)

logger = logging.getLogger("watch_govbr")

# Pipeline constants
DEFAULT_JURISDICTION = "federal_br"

# Type display map (for title_short)
_TYPE_DISPLAY = {
    "instrucao_normativa": "IN",
    "portaria": "Portaria",
    "resolucao": "Resolucao",
    "orientacao_normativa": "ON",
    "lei": "Lei",
    "lei_complementar": "LC",
    "decreto": "Decreto",
}

# HTTP request delay (seconds)
REQUEST_DELAY = 3.0

# SSL context (some gov.br servers have cert issues)
_SSL_CTX = ssl.create_default_context()


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def _fetch_url(url: str) -> bytes:
    """Download URL com headers padrao e retry."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5",
    }
    req = Request(url, headers=headers)

    for attempt in range(3):
        try:
            with urlopen(req, context=_SSL_CTX, timeout=30) as resp:
                return resp.read()
        except (HTTPError, URLError, TimeoutError, ConnectionError, OSError) as e:
            logger.warning("Tentativa %d falhou para %s: %s", attempt + 1, url, e)
            if attempt < 2:
                time.sleep(3 * (attempt + 1))  # 3s, 6s backoff
            else:
                raise
    raise RuntimeError(f"Nao conseguiu baixar {url}")


def _fingerprint(html_bytes: bytes) -> str:
    """Calcula fingerprint SHA256 do HTML normalizado (sem whitespace variavel)."""
    text = html_bytes.decode("utf-8", errors="replace")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"publicado\s+\d{2}/\d{2}/\d{4}\s+\d{2}h\d{2}", "", text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── DB helpers (legal_source) ────────────────────────────────────────────────

def _get_source_row(doc_id: str) -> Optional[dict]:
    """Busca registro em legal_source."""
    from govy.db.connection import get_conn, release_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT doc_id, fingerprint, ingest_status, last_checked_at FROM legal_source WHERE doc_id = %s",
                (doc_id,),
            )
            row = cur.fetchone()
            if row:
                return {"doc_id": row[0], "fingerprint": row[1], "ingest_status": row[2], "last_checked_at": row[3]}
            return None
    finally:
        release_conn(conn)


def _upsert_source(
    doc_id: str,
    kind: str,
    source_url: str,
    list_url: str,
    caption_raw: str,
    status_hint: str,
    fingerprint: Optional[str] = None,
    ingest_status: str = "pending",
    error_message: Optional[str] = None,
):
    """Insere ou atualiza registro em legal_source."""
    from govy.db.connection import get_conn, release_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO legal_source (
                    doc_id, kind, source_url, list_url, caption_raw,
                    status_hint, fingerprint, ingest_status, error_message,
                    last_checked_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
                ON CONFLICT (doc_id) DO UPDATE SET
                    source_url      = EXCLUDED.source_url,
                    list_url        = EXCLUDED.list_url,
                    caption_raw     = EXCLUDED.caption_raw,
                    status_hint     = EXCLUDED.status_hint,
                    fingerprint     = COALESCE(EXCLUDED.fingerprint, legal_source.fingerprint),
                    ingest_status   = EXCLUDED.ingest_status,
                    error_message   = EXCLUDED.error_message,
                    last_checked_at = now(),
                    updated_at      = now()
            """, (
                doc_id, kind, source_url, list_url, caption_raw,
                status_hint, fingerprint, ingest_status, error_message,
            ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def _update_source_status(
    doc_id: str,
    ingest_status: str,
    fingerprint: Optional[str] = None,
    error_message: Optional[str] = None,
):
    """Atualiza status de ingestao em legal_source, incluindo tracking fields."""
    from govy.db.connection import get_conn, release_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            if ingest_status == "ingested":
                # Sucesso: atualiza last_success_at
                if fingerprint:
                    cur.execute("""
                        UPDATE legal_source SET
                            ingest_status = %s, fingerprint = %s, error_message = NULL,
                            last_checked_at = now(), updated_at = now(),
                            last_success_at = now()
                        WHERE doc_id = %s
                    """, (ingest_status, fingerprint, doc_id))
                else:
                    cur.execute("""
                        UPDATE legal_source SET
                            ingest_status = %s, error_message = NULL,
                            last_checked_at = now(), updated_at = now(),
                            last_success_at = now()
                        WHERE doc_id = %s
                    """, (ingest_status, doc_id))
            elif ingest_status == "error":
                # Erro: atualiza last_error_reason
                cur.execute("""
                    UPDATE legal_source SET
                        ingest_status = %s, error_message = %s,
                        last_checked_at = now(), updated_at = now(),
                        last_error_reason = %s
                    WHERE doc_id = %s
                """, (ingest_status, error_message, error_message, doc_id))
            else:
                # Outros status (pending, etc.)
                if fingerprint:
                    cur.execute("""
                        UPDATE legal_source SET
                            ingest_status = %s, fingerprint = %s, error_message = %s,
                            last_checked_at = now(), updated_at = now()
                        WHERE doc_id = %s
                    """, (ingest_status, fingerprint, error_message, doc_id))
                else:
                    cur.execute("""
                        UPDATE legal_source SET
                            ingest_status = %s, error_message = %s,
                            last_checked_at = now(), updated_at = now()
                        WHERE doc_id = %s
                    """, (ingest_status, error_message, doc_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


def _update_vigencia_revogada(doc_id: str):
    """Marca documento como revogado em legal_document com confidence alta."""
    from govy.db.connection import get_conn, release_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE legal_document SET
                    status_vigencia = 'revogada',
                    updated_at = now()
                WHERE doc_id = %s
            """, (doc_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        release_conn(conn)


# ── Ingestao ─────────────────────────────────────────────────────────────────

def ingest_from_html(
    doc_id: str,
    kind: str,
    title: str,
    html_bytes: bytes,
    source_url: str,
    number: Optional[str] = None,
    year: Optional[int] = None,
    dry_run: bool = False,
) -> dict:
    """
    Ingere documento HTML no pipeline existente.

    1. extract_html -> ExtractionResult
    2. Build LegalDocumentRow
    3. chunk_legal_text -> provisions, chunks
    4. write_document -> DB
    5. extract_effective_dates + extract_relations -> DB

    Returns:
        dict com resultado
    """
    extraction = extract_html(html_bytes)

    if not extraction.text or extraction.char_count < 100:
        return {
            "doc_id": doc_id,
            "status": "skipped",
            "reason": f"texto muito curto ({extraction.char_count} chars)",
        }

    # Title short
    prefix = _TYPE_DISPLAY.get(kind, "Doc")
    if number and year:
        title_short = f"{prefix} {number}/{year}"
    else:
        title_short = doc_id

    # Chunk
    provisions, chunks = chunk_legal_text(extraction.text, doc_id, title_short)

    # Build document row
    doc = LegalDocumentRow(
        doc_id=doc_id,
        jurisdiction_id=DEFAULT_JURISDICTION,
        doc_type=kind,
        number=number,
        year=year,
        title=title,
        source_blob_path=None,
        source_format="html",
        text_sha256=extraction.sha256,
        char_count=extraction.char_count,
        provisions=provisions,
        chunks=chunks,
    )

    result = {
        "doc_id": doc_id,
        "kind": kind,
        "char_count": extraction.char_count,
        "provisions": len(provisions),
        "chunks": len(chunks),
        "source_url": source_url,
    }

    if dry_run:
        result["status"] = "dry_run"
        logger.info("DRY RUN: %s -> %d provisions, %d chunks", doc_id, len(provisions), len(chunks))
        return result

    # Write to DB
    db_result = write_document(doc)
    result["status"] = "ok"
    result["db_result"] = db_result

    # Extract dates
    try:
        dates = extract_effective_dates(extraction.text, doc_id)
        update_document_dates(doc_id, dates)
        result["dates"] = {
            "published_at": str(dates.published_at) if dates.published_at else None,
            "effective_from": str(dates.effective_from) if dates.effective_from else None,
            "status_vigencia": dates.status_vigencia,
        }
    except Exception as e:
        logger.warning("Erro ao extrair datas para %s: %s", doc_id, e)

    # Extract relations
    try:
        relations = extract_relations(extraction.text, doc_id)
        if relations:
            write_relations(doc_id, relations)
            result["relations"] = len(relations)
    except Exception as e:
        logger.warning("Erro ao extrair relacoes para %s: %s", doc_id, e)

    return result


# ── Logica principal ─────────────────────────────────────────────────────────

def fetch_all_list_items(list_url: str) -> List[ListItem]:
    """Baixa todas as paginas de uma lista e retorna todos os itens."""
    all_items = []
    current_url = list_url
    page = 1

    while current_url:
        logger.info("  Pagina %d: %s", page, current_url)
        html = _fetch_url(current_url)
        result = parse_list_page(html.decode("utf-8", errors="replace"), current_url)
        all_items.extend(result.items)
        logger.info("  -> %d itens nesta pagina", len(result.items))

        current_url = result.next_page_url
        page += 1

        if current_url:
            time.sleep(REQUEST_DELAY)

    return all_items


def process_list(
    list_config: dict,
    dry_run: bool = False,
    limit: int = 0,
    skip_ingest: bool = False,
    skip_recent_hours: float = 0,
) -> dict:
    """
    Processa uma lista completa.

    Args:
        list_config: dict com url, kind, status_hint
        dry_run: se True, nao grava no DB
        limit: max itens novos a ingerir (0=todos)
        skip_ingest: se True, registra em legal_source mas nao baixa detalhes
        skip_recent_hours: se > 0, pula items com last_checked_at < N horas atras (fast path para timer)

    Returns:
        dict com estatisticas da lista
    """
    list_url = list_config["url"]
    kind = list_config["kind"]
    status_hint = list_config["status_hint"]

    logger.info("=== Lista: %s (%s, %s) ===", list_url, kind, status_hint)

    # 1. Fetch all items from list
    items = fetch_all_list_items(list_url)
    logger.info("Total itens na lista: %d", len(items))

    stats = {
        "list_url": list_url,
        "kind": kind,
        "status_hint": status_hint,
        "total_items": len(items),
        "new": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
        "error_details": [],
    }

    ingested_count = 0

    for i, item in enumerate(items, 1):
        if not item.doc_id:
            logger.warning("  [%d/%d] Sem doc_id para: %s", i, len(items), item.caption_raw[:60])
            stats["errors"] += 1
            stats["error_details"].append({
                "caption": item.caption_raw[:100],
                "error": "caption_to_doc_id falhou",
            })
            continue

        if limit > 0 and ingested_count >= limit:
            stats["skipped"] += 1
            continue

        logger.info("  [%d/%d] %s -> %s", i, len(items), item.doc_id, item.detail_url[:80])

        try:
            # Check if already exists in legal_source
            existing = None
            if not dry_run:
                existing = _get_source_row(item.doc_id)

            # Fast-skip: se item foi checado recentemente, pular sem baixar
            if skip_recent_hours > 0 and existing and existing.get("ingest_status") == "ingested":
                last_checked = existing.get("last_checked_at")
                if last_checked:
                    from datetime import timezone
                    if last_checked.tzinfo is None:
                        last_checked = last_checked.replace(tzinfo=timezone.utc)
                    age_hours = (datetime.now(timezone.utc) - last_checked).total_seconds() / 3600
                    if age_hours < skip_recent_hours:
                        stats["skipped"] += 1
                        continue

            if skip_ingest:
                # Apenas registra na legal_source
                if not dry_run:
                    _upsert_source(
                        doc_id=item.doc_id,
                        kind=kind,
                        source_url=item.detail_url,
                        list_url=list_url,
                        caption_raw=item.caption_raw,
                        status_hint=status_hint,
                    )
                stats["new"] += 1
                continue

            # Download detail page
            time.sleep(REQUEST_DELAY)
            detail_html = _fetch_url(item.detail_url)
            fp = _fingerprint(detail_html)

            if existing and existing.get("fingerprint") == fp and existing.get("ingest_status") == "ingested":
                # Sem mudanca — apenas atualiza last_checked
                if not dry_run:
                    _update_source_status(item.doc_id, "ingested", fp)
                stats["skipped"] += 1
                logger.info("    -> skip (fingerprint inalterado)")
                continue

            is_update = existing and existing.get("ingest_status") == "ingested"

            # Register in legal_source
            if not dry_run:
                _upsert_source(
                    doc_id=item.doc_id,
                    kind=kind,
                    source_url=item.detail_url,
                    list_url=list_url,
                    caption_raw=item.caption_raw,
                    status_hint=status_hint,
                    fingerprint=fp,
                    ingest_status="pending",
                )

            # Ingest
            result = ingest_from_html(
                doc_id=item.doc_id,
                kind=kind,
                title=item.caption_raw,
                html_bytes=detail_html,
                source_url=item.detail_url,
                number=item.number,
                year=item.year,
                dry_run=dry_run,
            )

            if result.get("status") in ("ok", "dry_run"):
                ingested_count += 1
                if is_update:
                    stats["updated"] += 1
                else:
                    stats["new"] += 1

                # Update legal_source status
                if not dry_run and result.get("status") == "ok":
                    _update_source_status(item.doc_id, "ingested", fp)

                # Handle revogada lists
                if status_hint == "revogada" and not dry_run and result.get("status") == "ok":
                    _update_vigencia_revogada(item.doc_id)

                    # Extract revocation from title
                    rev_ref = extract_revocation_from_title(item.caption_raw)
                    if rev_ref:
                        _write_title_revocation_relation(item.doc_id, rev_ref, item.caption_raw)

                logger.info(
                    "    -> %s: %d provisions, %d chunks",
                    result.get("status"), result.get("provisions", 0), result.get("chunks", 0),
                )
            else:
                stats["skipped"] += 1
                logger.info("    -> %s: %s", result.get("status"), result.get("reason", ""))

        except Exception as e:
            stats["errors"] += 1
            stats["error_details"].append({
                "doc_id": item.doc_id,
                "error": str(e),
            })
            logger.exception("    -> ERRO para %s: %s", item.doc_id, e)

            if not dry_run:
                try:
                    _update_source_status(item.doc_id, "error", error_message=str(e)[:500])
                except Exception:
                    pass

    logger.info(
        "  Resultado: %d total, %d novos, %d atualizados, %d skip, %d erros",
        stats["total_items"], stats["new"], stats["updated"], stats["skipped"], stats["errors"],
    )
    return stats


def _write_title_revocation_relation(doc_id: str, rev_ref: str, caption: str):
    """Grava relacao de revogacao extraida do titulo da lista."""
    parsed = caption_to_doc_id(rev_ref)
    target_doc_id = parsed[0] if parsed else None

    from govy.db.connection import get_conn, release_conn
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO legal_relation (
                    source_doc_id, target_doc_id, target_ref,
                    relation_type, source_provision, notes,
                    confidence, needs_review,
                    evidence_text, evidence_pattern, evidence_position
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                doc_id,
                target_doc_id,
                rev_ref,
                "revoga",
                None,
                "Revogacao detectada no titulo da lista gov.br/compras",
                "high",
                False,
                caption[:300],
                "govbr_list_title",
                0,
            ))
        conn.commit()
        logger.info("  Relacao revogacao via titulo gravada para %s", doc_id)
    except Exception as e:
        conn.rollback()
        logger.warning("  Erro ao gravar relacao titulo para %s: %s", doc_id, e)
    finally:
        release_conn(conn)


# ── Report generators ────────────────────────────────────────────────────────

def generate_report_md(all_stats: List[dict]) -> str:
    """Gera relatorio Markdown e retorna como string."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Relatório Watch gov.br/compras",
        f"",
        f"**Data**: {now}",
        f"",
        f"## Resumo por Lista",
        f"",
        f"| Lista | Kind | Status | Total | Novos | Atualiz. | Skip | Erros |",
        f"|-------|------|--------|------:|------:|---------:|-----:|------:|",
    ]

    totals = {"total": 0, "new": 0, "updated": 0, "skipped": 0, "errors": 0}

    for s in all_stats:
        url_short = s["list_url"].split("/legislacao/")[-1] if "/legislacao/" in s["list_url"] else s["list_url"]
        lines.append(
            f"| {url_short} | {s['kind']} | {s['status_hint']} | "
            f"{s['total_items']} | {s['new']} | {s['updated']} | {s['skipped']} | {s['errors']} |"
        )
        totals["total"] += s["total_items"]
        totals["new"] += s["new"]
        totals["updated"] += s["updated"]
        totals["skipped"] += s["skipped"]
        totals["errors"] += s["errors"]

    lines.append(
        f"| **TOTAL** | | | "
        f"**{totals['total']}** | **{totals['new']}** | **{totals['updated']}** | "
        f"**{totals['skipped']}** | **{totals['errors']}** |"
    )

    # Errors section
    all_errors = []
    for s in all_stats:
        all_errors.extend(s.get("error_details", []))

    if all_errors:
        lines.append("")
        lines.append("## Erros")
        lines.append("")
        for err in all_errors:
            doc = err.get("doc_id", err.get("caption", "?"))
            lines.append(f"- **{doc}**: {err['error']}")

    lines.append("")
    lines.append("---")
    lines.append(f"*Gerado automaticamente por `govy.legal.watch_runner`*")

    return "\n".join(lines) + "\n"


def generate_report_json(all_stats: List[dict], timestamp: str) -> dict:
    """Gera JSON agregado com stats por lista + totais."""
    total_new = sum(s["new"] for s in all_stats)
    total_errors = sum(s["errors"] for s in all_stats)
    total_updated = sum(s["updated"] for s in all_stats)
    total_skipped = sum(s["skipped"] for s in all_stats)
    total_items = sum(s["total_items"] for s in all_stats)

    return {
        "timestamp": timestamp,
        "totals": {
            "items": total_items,
            "new": total_new,
            "updated": total_updated,
            "skipped": total_skipped,
            "errors": total_errors,
        },
        "lists": [
            {
                "url": s["list_url"],
                "kind": s["kind"],
                "status_hint": s["status_hint"],
                "total_items": s["total_items"],
                "new": s["new"],
                "updated": s["updated"],
                "skipped": s["skipped"],
                "errors": s["errors"],
                "error_details": s.get("error_details", []),
            }
            for s in all_stats
        ],
    }


# ── Orchestrator ─────────────────────────────────────────────────────────────

def watch_govbr_all(
    list_configs: list = None,
    dry_run: bool = False,
    limit: int = 0,
    skip_ingest: bool = False,
    list_url_filter: Optional[str] = None,
    skip_recent_hours: float = 0,
) -> dict:
    """
    Processa todas as listas gov.br/compras.

    Args:
        list_configs: lista de configs (default=GOVBR_LISTS)
        dry_run: se True, nao grava no DB
        limit: max itens novos a ingerir por lista (0=todos)
        skip_ingest: se True, registra em legal_source mas nao baixa detalhes
        list_url_filter: se fornecido, filtra por URL (match exato ou parcial)
        skip_recent_hours: se > 0, pula items com last_checked_at < N horas atras

    Returns:
        {
            "all_stats": [...],
            "report_md": str,
            "report_json": dict,
            "total_new": int,
            "total_errors": int,
            "timestamp": str,
        }
    """
    if list_configs is None:
        list_configs = GOVBR_LISTS

    # Filtrar por URL se solicitado
    if list_url_filter:
        filtered = [l for l in list_configs if l["url"] == list_url_filter]
        if not filtered:
            filtered = [l for l in list_configs if list_url_filter in l["url"]]
        if not filtered:
            raise ValueError(f"Nenhuma lista encontrada para URL: {list_url_filter}")
        list_configs = filtered

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    logger.info("=== Watch gov.br/compras iniciado ===")
    logger.info("dry_run=%s, limit=%d, skip_ingest=%s, listas=%d",
                dry_run, limit, skip_ingest, len(list_configs))

    all_stats = []
    for list_config in list_configs:
        try:
            stats = process_list(
                list_config=list_config,
                dry_run=dry_run,
                limit=limit,
                skip_ingest=skip_ingest,
                skip_recent_hours=skip_recent_hours,
            )
            all_stats.append(stats)
        except Exception as e:
            logger.exception("ERRO fatal na lista %s: %s", list_config["url"], e)
            all_stats.append({
                "list_url": list_config["url"],
                "kind": list_config["kind"],
                "status_hint": list_config["status_hint"],
                "total_items": 0,
                "new": 0,
                "updated": 0,
                "skipped": 0,
                "errors": 1,
                "error_details": [{"error": str(e)}],
            })

    total_new = sum(s["new"] for s in all_stats)
    total_errors = sum(s["errors"] for s in all_stats)

    report_md = generate_report_md(all_stats)
    report_json = generate_report_json(all_stats, timestamp)

    logger.info("=== Watch concluido: %d novos, %d erros ===", total_new, total_errors)

    return {
        "all_stats": all_stats,
        "report_md": report_md,
        "report_json": report_json,
        "total_new": total_new,
        "total_errors": total_errors,
        "timestamp": timestamp,
    }
