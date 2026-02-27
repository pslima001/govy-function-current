"""
GOVY - TCU Manual Ingestion (HTML-first, PDF fallback)
=======================================================
Baixa o Manual de Licitacoes e Contratos do TCU pagina a pagina do site,
extrai texto/HTML/sha256, salva no Azure Blob Storage.

Uso:
  python scripts/kb/guides/ingest_tcu_manual.py \
    --run-id tcu_manual_2026-02-27 \
    --date-prefix 2026-02-27 \
    [--download-pdf true|false] \
    [--max-pages N] \
    [--dry-run]

Env vars:
  AZURE_STORAGE_CONNECTION_STRING ou AzureWebJobsStorage
  (ou GOVY_STORAGE_ACCOUNT para MI)
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

# ─── Config ──────────────────────────────────────────────────────────────────

MANUAL_BASE_URL = "https://licitacoesecontratos.tcu.gov.br/manual/"
MANUAL_PDF_URL = (
    "https://licitacoesecontratos.tcu.gov.br/wp-content/uploads/"
    "Manual-versao-SECOM-publicada-no-site-VERSAO-FINAL-ATUALIZADA-1_compressed-1.pdf"
)
STORAGE_CONTAINER = "kb-content"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_DELAY = 1.0  # seconds between requests (polite crawling)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _get_conn() -> str:
    conn = os.getenv("AZURE_STORAGE_CONNECTION_STRING") or os.getenv("AzureWebJobsStorage")
    if not conn:
        raise RuntimeError("Missing AZURE_STORAGE_CONNECTION_STRING or AzureWebJobsStorage")
    return conn


def _fetch_url(url: str, max_retries: int = 3) -> bytes:
    """Fetch URL with browser UA and retry logic."""
    import requests

    headers = {"User-Agent": BROWSER_UA}
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.content
        except (requests.ConnectionError, requests.Timeout, OSError) as e:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"  [RETRY {attempt+1}] {url}: {e} (waiting {wait}s)")
                time.sleep(wait)
            else:
                raise


def _extract_section_links(html_bytes: bytes) -> List[Dict[str, str]]:
    """Extract all manual section links from the main page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_bytes, "html.parser")
    base = "https://licitacoesecontratos.tcu.gov.br/"
    links = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith(base):
            continue
        # Filter: must match section pattern (number-prefix or known slug)
        path = href.replace(base, "").rstrip("/")
        if not path or path == "manual":
            continue
        # Must start with a digit (section pages) or be a known pattern
        if not re.match(r"^\d", path) and path not in ("801-2",):
            continue
        if href in seen:
            continue
        seen.add(href)
        title = a.get_text(strip=True) or path
        links.append({"url": href, "title": title, "path": path})

    return links


def _extract_page_content(html_bytes: bytes, url: str) -> Dict[str, Any]:
    """Extract structured content from a manual section page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_bytes, "html.parser")
    page: Dict[str, Any] = {"url": url}

    # Title: from div.main-title-header (TCU site structure)
    title_el = soup.find("div", class_="main-title-header")
    page["title"] = title_el.get_text(strip=True) if title_el else ""
    if not page["title"]:
        h2 = soup.find("h2")
        h1 = soup.find("h1")
        page["title"] = (h2 and h2.get_text(strip=True)) or (h1 and h1.get_text(strip=True)) or ""

    # Breadcrumb: from div.breadcrumb
    breadcrumb_el = soup.find("div", class_="breadcrumb")
    if not breadcrumb_el:
        breadcrumb_el = soup.find(class_=re.compile(r"breadcrumb", re.I))
    if breadcrumb_el:
        page["breadcrumb"] = breadcrumb_el.get_text(" > ", strip=True)
    else:
        page["breadcrumb"] = ""

    # Main content: div.main-content-general (TCU site structure)
    content_el = soup.find("div", class_="main-content-general")
    if not content_el:
        # Fallback selectors
        content_el = (
            soup.find("article")
            or soup.find("div", class_="entry-content")
            or soup.find("main")
        )

    if content_el:
        # Remove footer, nav, scripts from content
        for unwanted in content_el.find_all(["footer", "nav", "script", "style"]):
            unwanted.decompose()

        # Extract headings structure within content
        headings = []
        for tag in content_el.find_all(re.compile(r"^h[1-6]$")):
            headings.append({
                "level": int(tag.name[1]),
                "text": tag.get_text(strip=True),
            })
        page["headings"] = headings

        # Extract full text (clean)
        text = content_el.get_text("\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        page["text"] = text

        # Also save raw HTML of the content area
        page["html"] = str(content_el)
    else:
        body = soup.find("body")
        page["headings"] = []
        page["text"] = body.get_text("\n", strip=True) if body else ""
        page["html"] = str(body) if body else ""

    # SHA256 of normalized text
    normalized = re.sub(r"\s+", " ", page["text"]).strip()
    page["sha256_text"] = _sha256(normalized)
    page["char_count"] = len(page["text"])

    return page


# ─── Main Pipeline ───────────────────────────────────────────────────────────

def run_ingest(
    run_id: str,
    date_prefix: str,
    download_pdf: bool = True,
    max_pages: int = 0,
    dry_run: bool = False,
    storage_account: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the full ingestion pipeline."""

    retrieved_at = datetime.now(timezone.utc).isoformat()
    stats = {
        "run_id": run_id,
        "date_prefix": date_prefix,
        "retrieved_at_utc": retrieved_at,
        "source_url_html_base": MANUAL_BASE_URL,
        "source_url_pdf": MANUAL_PDF_URL,
        "pages_fetched": 0,
        "pages_skipped": 0,
        "pages_error": 0,
        "total_chars": 0,
        "pdf_downloaded": False,
        "pdf_sha256": "",
    }

    print(f"[1/5] Fetching main page: {MANUAL_BASE_URL}")
    main_html = _fetch_url(MANUAL_BASE_URL)
    section_links = _extract_section_links(main_html)
    print(f"  Found {len(section_links)} section links")

    if max_pages > 0:
        section_links = section_links[:max_pages]
        print(f"  Limited to {max_pages} pages (--max-pages)")

    # Fetch each section page
    print(f"[2/5] Fetching {len(section_links)} section pages...")
    pages: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for i, link in enumerate(section_links):
        url = link["url"]
        if (i + 1) % 20 == 0:
            print(f"  Progress: {i+1}/{len(section_links)}")

        if dry_run:
            pages.append({
                "url": url,
                "title": link["title"],
                "path": link["path"],
                "dry_run": True,
            })
            stats["pages_fetched"] += 1
            continue

        try:
            html_bytes = _fetch_url(url)
            page = _extract_page_content(html_bytes, url)
            page["path"] = link["path"]
            page["nav_title"] = link["title"]
            pages.append(page)
            stats["pages_fetched"] += 1
            stats["total_chars"] += page.get("char_count", 0)
            time.sleep(REQUEST_DELAY)
        except Exception as e:
            err = {"url": url, "error": str(e)}
            errors.append(err)
            stats["pages_error"] += 1
            print(f"  [ERROR] {url}: {e}")

    stats["errors"] = errors

    if dry_run:
        print(f"\n=== DRY RUN ===")
        print(f"Would fetch {len(pages)} pages")
        for p in pages[:5]:
            print(f"  {p['url']}")
        if len(pages) > 5:
            print(f"  ... +{len(pages)-5} more")
        stats["dry_run"] = True
        return stats

    # Build output JSON
    output = {
        "kind": "tcu_manual_pages_v1",
        "run_id": run_id,
        "retrieved_at_utc": retrieved_at,
        "source_url_html_base": MANUAL_BASE_URL,
        "source_url_pdf": MANUAL_PDF_URL,
        "page_count": len(pages),
        "total_chars": stats["total_chars"],
        "pages": pages,
    }

    # Upload to Blob
    print(f"[3/5] Uploading pages JSON to blob...")
    from azure.storage.blob import BlobServiceClient

    conn = _get_conn()
    blob_service = BlobServiceClient.from_connection_string(conn)
    container_client = blob_service.get_container_client(STORAGE_CONTAINER)

    # Ensure container exists
    try:
        container_client.create_container()
    except Exception:
        pass  # already exists

    pages_blob = f"guia_tcu/raw/{date_prefix}/manual_tcu_pages.json"
    pages_json = json.dumps(output, ensure_ascii=False, indent=2)
    container_client.upload_blob(pages_blob, pages_json, overwrite=True)
    print(f"  Uploaded: {STORAGE_CONTAINER}/{pages_blob} ({len(pages_json)} bytes)")

    # Download and upload PDF
    if download_pdf:
        print(f"[4/5] Downloading PDF...")
        try:
            pdf_bytes = _fetch_url(MANUAL_PDF_URL)
            pdf_sha = hashlib.sha256(pdf_bytes).hexdigest()
            stats["pdf_sha256"] = pdf_sha
            stats["pdf_downloaded"] = True

            pdf_blob = f"guia_tcu/raw/{date_prefix}/manual_tcu.pdf"
            container_client.upload_blob(pdf_blob, pdf_bytes, overwrite=True)
            print(f"  Uploaded: {STORAGE_CONTAINER}/{pdf_blob} ({len(pdf_bytes)} bytes, sha256={pdf_sha[:16]}...)")
        except Exception as e:
            print(f"  [ERROR] PDF download failed: {e}")
            stats["pdf_error"] = str(e)
    else:
        print(f"[4/5] PDF download skipped (--download-pdf false)")

    # Save metadata
    print(f"[5/5] Saving metadata...")
    metadata = {
        "kind": "tcu_manual_metadata_v1",
        "run_id": run_id,
        "date_prefix": date_prefix,
        "retrieved_at_utc": retrieved_at,
        "source_url_html_base": MANUAL_BASE_URL,
        "source_url_pdf": MANUAL_PDF_URL,
        "page_count": len(pages),
        "total_chars": stats["total_chars"],
        "pages_error": stats["pages_error"],
        "pdf_downloaded": stats["pdf_downloaded"],
        "pdf_sha256": stats["pdf_sha256"],
        "errors": errors,
    }
    meta_blob = f"guia_tcu/metadata/{date_prefix}/manual_tcu.metadata.json"
    meta_json = json.dumps(metadata, ensure_ascii=False, indent=2)
    container_client.upload_blob(meta_blob, meta_json, overwrite=True)
    print(f"  Uploaded: {STORAGE_CONTAINER}/{meta_blob}")

    # Report
    print(f"\n{'='*60}")
    print(f"INGEST REPORT — TCU Manual")
    print(f"{'='*60}")
    print(f"Run ID:          {run_id}")
    print(f"Date:            {date_prefix}")
    print(f"Pages fetched:   {stats['pages_fetched']}")
    print(f"Pages errors:    {stats['pages_error']}")
    print(f"Total chars:     {stats['total_chars']:,}")
    print(f"PDF downloaded:  {stats['pdf_downloaded']}")
    if stats["pdf_sha256"]:
        print(f"PDF SHA256:      {stats['pdf_sha256'][:32]}...")
    print(f"Blobs:")
    print(f"  {STORAGE_CONTAINER}/{pages_blob}")
    if stats["pdf_downloaded"]:
        print(f"  {STORAGE_CONTAINER}/{pdf_blob}")
    print(f"  {STORAGE_CONTAINER}/{meta_blob}")

    return stats


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Ingest TCU Manual (HTML-first, PDF fallback)")
    ap.add_argument("--run-id", required=True, help="Unique run identifier (e.g. tcu_manual_2026-02-27)")
    ap.add_argument("--date-prefix", default=datetime.now().strftime("%Y-%m-%d"),
                     help="Date prefix for blob paths (default: today)")
    ap.add_argument("--download-pdf", default="true", choices=["true", "false"],
                     help="Download PDF to blob (default: true)")
    ap.add_argument("--max-pages", type=int, default=0,
                     help="Limit number of pages to fetch (0=all)")
    ap.add_argument("--dry-run", action="store_true",
                     help="Show what would be fetched without downloading")
    args = ap.parse_args()

    run_ingest(
        run_id=args.run_id,
        date_prefix=args.date_prefix,
        download_pdf=args.download_pdf.lower() == "true",
        max_pages=args.max_pages,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
