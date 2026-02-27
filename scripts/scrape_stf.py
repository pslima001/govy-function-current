"""
STF Jurisprudência Scraper
===========================
Scrapes acórdãos from jurisprudencia.stf.jus.br using Playwright + requests.

Strategy:
  1. Playwright navigates the SPA to pass AWS WAF challenge
  2. Intercepts the search API call to capture the exact ES query body
  3. Extracts session cookies (aws-waf-token, AWSALB)
  4. Uses requests with those cookies to paginate through ALL results
  5. Saves each acórdão as JSON to local output dir
  6. (Optional) Upload to Azure Blob Storage

Usage:
    python scripts/scrape_stf.py [--upload]
    python scripts/scrape_stf.py --page-size 50 --max-results 100  # test mode

Output:
    scripts/stf_output/stf/acordaos/{sjur_id}.json  (one file per acórdão)
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Full search URL from user (licitação ou pregão ou licitante ou
# "concorrência pública" ou certame não concurso não crime não criminal)
SEARCH_URL = (
    "https://jurisprudencia.stf.jus.br/pages/search"
    "?base=acordaos"
    "&pesquisa_inteiro_teor=false"
    "&sinonimo=true"
    "&plural=true"
    "&radicais=false"
    "&buscaExata=true"
    "&page=1&pageSize=10"
    "&queryString=licita%C3%A7%C3%A3o%20ou%20preg%C3%A3o%20ou%20licitante"
    "%20ou%20%22concorr%C3%AAncia%20p%C3%BAblica%22"
    "%20ou%20certame%20n%C3%A3o%20concurso"
    "%20n%C3%A3o%20crime%20n%C3%A3o%20criminal"
    "&sort=_score&sortBy=desc"
    "&isAdvanced=true"
)

API_SEARCH_URL = "https://jurisprudencia.stf.jus.br/api/search/search"
API_DETAIL_URL = "https://jurisprudencia.stf.jus.br/api/search/get"

OUTPUT_DIR = Path("scripts/stf_output/stf/acordaos")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Referer": "https://jurisprudencia.stf.jus.br/pages/search",
    "Origin": "https://jurisprudencia.stf.jus.br",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("stf-scraper")


class WafExpiredError(Exception):
    """Raised when the AWS WAF token has expired."""
    pass


# ---------------------------------------------------------------------------
# Phase 1: Use Playwright to pass WAF and capture the API query + cookies
# ---------------------------------------------------------------------------

def get_waf_cookies_and_query():
    """
    Opens the STF search page in Playwright, waits for WAF challenge,
    captures the search API request body and session cookies.
    Returns (cookies_dict, search_query_body, search_id, total_hits).
    """
    captured = {"query_body": None, "search_id": None, "total_hits": 0}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
        )
        page = context.new_page()

        def on_response(response):
            if (
                response.url == API_SEARCH_URL
                and response.request.method == "POST"
                and captured["query_body"] is None
            ):
                try:
                    body = response.json()
                    captured["query_body"] = response.request.post_data
                    captured["search_id"] = body.get("search_id")
                    total = body.get("result", {}).get("hits", {}).get("total", {})
                    captured["total_hits"] = (
                        total.get("value", 0) if isinstance(total, dict) else total
                    )
                    log.info(
                        f"Captured search query — total hits: {captured['total_hits']}, "
                        f"search_id: {captured['search_id']}"
                    )
                except Exception as e:
                    log.warning(f"Failed to parse search response: {e}")

        page.on("response", on_response)

        log.info("Opening STF search page (passing WAF challenge)...")
        page.goto(SEARCH_URL, wait_until="networkidle", timeout=90000)

        # Wait for results to appear
        try:
            page.wait_for_selector("#scrollId", timeout=30000)
            log.info("Search results loaded!")
        except Exception:
            log.warning(f"Timeout waiting for results. Page title: {page.title()}")

        page.wait_for_timeout(3000)

        # Extract cookies
        cookies = context.cookies()
        cookie_dict = {c["name"]: c["value"] for c in cookies}

        browser.close()

    if captured["query_body"] is None:
        raise RuntimeError("Failed to capture search API query body")

    return cookie_dict, captured["query_body"], captured["search_id"], captured["total_hits"]


# ---------------------------------------------------------------------------
# Phase 2: Paginate through all results using direct API calls
# ---------------------------------------------------------------------------

def build_session(cookies: dict) -> requests.Session:
    """Build requests session with WAF cookies."""
    session = requests.Session()
    session.headers.update(HEADERS)
    session.verify = False  # STF has certificate issues
    for name, value in cookies.items():
        session.cookies.set(name, value, domain="jurisprudencia.stf.jus.br")
    return session


def search_page(session: requests.Session, query_body_str: str, page_from: int, page_size: int):
    """
    Execute one search API call with modified from/size.
    Returns (hits_list, total_count).
    """
    query_body = json.loads(query_body_str)

    # Override pagination
    query_body["from"] = page_from
    query_body["size"] = page_size

    # Remove aggregations to speed up pagination (only needed on first page)
    if page_from > 0:
        query_body.pop("aggs", None)

    # Remove highlight for speed (we save the full _source)
    query_body.pop("highlight", None)

    resp = session.post(API_SEARCH_URL, json=query_body, timeout=60)

    # WAF may return 202 with empty body, or 403
    if resp.status_code in (202, 403) or len(resp.content) == 0:
        raise WafExpiredError(f"WAF token expired (status={resp.status_code})")

    resp.raise_for_status()

    data = resp.json()
    result = data.get("result", {})
    hits_obj = result.get("hits", {})
    total = hits_obj.get("total", {})
    total_count = total.get("value", 0) if isinstance(total, dict) else total
    hits = hits_obj.get("hits", [])

    return hits, total_count


def fetch_detail(session: requests.Session, doc_id: str, search_id: str):
    """Fetch full detail for a single document."""
    url = f"{API_DETAIL_URL}/{doc_id}?search_id={search_id}"
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def save_acordao(doc: dict, output_dir: Path):
    """Save a single acórdão JSON to output directory."""
    doc_id = doc.get("id") or doc.get("dg_unique") or doc.get("_id", "unknown")
    filepath = output_dir / f"{doc_id}.json"

    # Wrap in envelope compatible with GOVY juris-raw format
    envelope = {
        "source": "stf",
        "source_api": "jurisprudencia.stf.jus.br",
        "doc_id": doc_id,
        "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scraper_version": "stf_scraper_v1.0",
        "data": doc,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)

    return filepath


# ---------------------------------------------------------------------------
# Phase 3 (optional): Upload to Azure Blob Storage
# ---------------------------------------------------------------------------

def upload_to_blob(output_dir: Path):
    """Upload all scraped JSONs to sttcejurisprudencia/juris-raw/stf/acordaos/."""
    try:
        from azure.storage.blob import BlobServiceClient, ContentSettings
    except ImportError:
        log.error("azure-storage-blob not installed. Skipping upload.")
        return

    conn_str = os.environ.get("TCE_STORAGE_CONNECTION")
    if not conn_str:
        log.error("TCE_STORAGE_CONNECTION not set. Skipping upload.")
        return

    service = BlobServiceClient.from_connection_string(conn_str)
    container = service.get_container_client("juris-raw")

    uploaded = 0
    for json_file in sorted(output_dir.glob("*.json")):
        blob_name = f"stf/acordaos/{json_file.name}"
        with open(json_file, "rb") as f:
            container.get_blob_client(blob_name).upload_blob(
                f,
                overwrite=True,
                content_settings=ContentSettings(
                    content_type="application/json; charset=utf-8"
                ),
            )
        uploaded += 1
        if uploaded % 100 == 0:
            log.info(f"  Uploaded {uploaded} blobs...")

    log.info(f"Upload complete: {uploaded} blobs → juris-raw/stf/acordaos/")
    return uploaded


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="STF Jurisprudência Scraper")
    parser.add_argument("--page-size", type=int, default=10,
                        help="Results per API page (default: 10, max observed: 250)")
    parser.add_argument("--max-results", type=int, default=0,
                        help="Max results to fetch (0 = all)")
    parser.add_argument("--upload", action="store_true",
                        help="Upload results to Azure Blob Storage")
    parser.add_argument("--delay", type=float, default=1.5,
                        help="Delay between API calls in seconds (default: 1.5)")
    parser.add_argument("--output-dir", type=str, default=str(OUTPUT_DIR),
                        help="Output directory for JSON files")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Phase 1: Get WAF cookies + search query
    log.info("=" * 60)
    log.info("PHASE 1: Passing WAF challenge with Playwright...")
    log.info("=" * 60)

    cookies, query_body_str, search_id, total_hits = get_waf_cookies_and_query()

    log.info(f"WAF cookies obtained: {list(cookies.keys())}")
    log.info(f"Total results: {total_hits}")
    log.info(f"Search ID: {search_id}")

    # Phase 2: Paginate through all results
    log.info("=" * 60)
    log.info("PHASE 2: Fetching all results via API...")
    log.info("=" * 60)

    session = build_session(cookies)

    max_results = args.max_results if args.max_results > 0 else total_hits
    page_size = args.page_size
    fetched = 0
    saved = 0
    skipped = 0
    errors = 0
    page_from = 0

    while fetched < max_results:
        remaining = max_results - fetched
        current_size = min(page_size, remaining)

        try:
            hits, _ = search_page(session, query_body_str, page_from, current_size)
        except (WafExpiredError, requests.exceptions.HTTPError, requests.exceptions.JSONDecodeError) as e:
            log.warning(f"Request failed ({type(e).__name__}: {e}). Re-authenticating...")
            cookies, query_body_str, search_id, total_hits = get_waf_cookies_and_query()
            session = build_session(cookies)
            time.sleep(2)
            continue

        if not hits:
            log.info("No more results.")
            break

        for hit in hits:
            doc = hit.get("_source", {})
            doc_id = doc.get("id") or doc.get("dg_unique", "unknown")

            # Check if already exists
            filepath = output_dir / f"{doc_id}.json"
            if filepath.exists():
                skipped += 1
                fetched += 1
                continue

            try:
                save_acordao(doc, output_dir)
                saved += 1
            except Exception as e:
                log.error(f"Error saving {doc_id}: {e}")
                errors += 1

            fetched += 1

        page_from += len(hits)

        log.info(
            f"Progress: {fetched}/{max_results} "
            f"(saved={saved}, skipped={skipped}, errors={errors}) "
            f"— page_from={page_from}"
        )

        if len(hits) < current_size:
            log.info("Last page (fewer results than requested).")
            break

        # Polite delay
        time.sleep(args.delay)

    # Summary
    log.info("=" * 60)
    log.info("SCRAPING COMPLETE")
    log.info(f"  Total fetched: {fetched}")
    log.info(f"  Saved: {saved}")
    log.info(f"  Skipped (existing): {skipped}")
    log.info(f"  Errors: {errors}")
    log.info(f"  Output dir: {output_dir}")
    log.info("=" * 60)

    # Phase 3: Upload to Azure (optional)
    if args.upload:
        log.info("=" * 60)
        log.info("PHASE 3: Uploading to Azure Blob Storage...")
        log.info("=" * 60)
        upload_to_blob(output_dir)

    return fetched


if __name__ == "__main__":
    # Suppress SSL warnings for STF's certificate issues
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    sys.exit(0 if main() > 0 else 1)
