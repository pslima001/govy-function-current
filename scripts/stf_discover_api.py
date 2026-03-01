"""
STF API Discovery Script
========================
Uses Playwright to navigate jurisprudencia.stf.jus.br, bypass AWS WAF,
and intercept the API calls the SPA makes to understand the backend endpoints.

Usage:
    python scripts/stf_discover_api.py
"""

import json
import sys
from playwright.sync_api import sync_playwright


SEARCH_URL = (
    "https://jurisprudencia.stf.jus.br/pages/search"
    "?base=acordaos"
    "&pesquisa_inteiro_teor=false"
    "&sinonimo=true"
    "&plural=true"
    "&radicais=false"
    "&buscaExata=true"
    "&page=1&pageSize=10"
    "&queryString=licita%C3%A7%C3%A3o"
    "&sort=_score&sortBy=desc"
    "&isAdvanced=true"
)


def main():
    api_calls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        # Intercept all network requests
        def on_response(response):
            url = response.url
            # Capture API calls (JSON responses, not static assets)
            if any(
                kw in url.lower()
                for kw in ["search", "pesquis", "api", "acordao", "query"]
            ):
                content_type = response.headers.get("content-type", "")
                if "json" in content_type or "application/json" in content_type:
                    try:
                        body = response.json()
                    except Exception:
                        body = "<could not parse>"
                    entry = {
                        "url": url,
                        "status": response.status,
                        "method": response.request.method,
                        "content_type": content_type,
                        "request_headers": dict(response.request.headers),
                        "body_preview": (
                            json.dumps(body, ensure_ascii=False)[:2000]
                            if isinstance(body, (dict, list))
                            else str(body)[:2000]
                        ),
                    }
                    # Capture POST body if available
                    if response.request.method == "POST":
                        try:
                            entry["request_body"] = response.request.post_data
                        except Exception:
                            entry["request_body"] = None
                    api_calls.append(entry)
                    print(f"\n[API] {response.request.method} {url}")
                    print(f"      Status: {response.status}")
                    print(f"      Content-Type: {content_type}")
                    if isinstance(body, dict):
                        keys = list(body.keys())[:10]
                        print(f"      Keys: {keys}")
                        if "result" in body:
                            print(f"      result keys: {list(body['result'].keys())[:10]}")

        page.on("response", on_response)

        print(f"Navigating to: {SEARCH_URL}")
        print("Waiting for WAF challenge to resolve...")
        page.goto(SEARCH_URL, wait_until="networkidle", timeout=60000)

        # Wait for results to appear
        print("Waiting for search results to load...")
        try:
            page.wait_for_selector("#scrollId", timeout=30000)
            print("Results loaded!")
        except Exception:
            print("Timeout waiting for results — checking page content...")
            print(f"Page title: {page.title()}")
            print(f"Page URL: {page.url}")

        # Wait a bit more for any lazy-loaded API calls
        page.wait_for_timeout(5000)

        # Also capture cookies for future direct API calls
        cookies = context.cookies()
        cookie_data = {c["name"]: c["value"] for c in cookies}

        # Try clicking on first result to see detail API call
        try:
            first_result = page.query_selector("#result-index-0 a")
            if first_result:
                print("\nClicking first result to capture detail API call...")
                first_result.click()
                page.wait_for_timeout(5000)
        except Exception as e:
            print(f"Could not click first result: {e}")

        browser.close()

    # Save results
    output = {
        "api_calls": api_calls,
        "cookies": cookie_data,
        "total_api_calls": len(api_calls),
    }

    output_path = "C:/govy/repos/govy-function-current/scripts/stf_api_discovery.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Discovery complete! {len(api_calls)} API calls captured.")
    print(f"Results saved to: {output_path}")
    print(f"{'='*60}")

    # Summary
    for i, call in enumerate(api_calls):
        print(f"\n--- API Call {i+1} ---")
        print(f"  Method: {call['method']}")
        print(f"  URL: {call['url']}")
        print(f"  Status: {call['status']}")
        if call.get("request_body"):
            print(f"  Request Body: {call['request_body'][:500]}")
        print(f"  Response Preview: {call['body_preview'][:500]}")


if __name__ == "__main__":
    main()
