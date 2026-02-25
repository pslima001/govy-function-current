#!/usr/bin/env python3
# scripts/watch_govbr_list.py
"""
CLI wrapper para watch de listas de legislacao do portal gov.br/compras.

Toda a logica core esta em govy.legal.watch_runner.
Este script e apenas o entrypoint CLI com argparse + salvamento de reports.

Uso:
  python scripts/watch_govbr_list.py --dry-run --limit 3
  python scripts/watch_govbr_list.py --list-url "https://www.gov.br/compras/.../instrucoes-normativas" --limit 5
  python scripts/watch_govbr_list.py --skip-ingest
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

# Garantir que raiz do projeto esta no path
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from govy.legal.watch_runner import watch_govbr_all

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("watch_govbr")


def _dated_path(base_path: str) -> str:
    """Adiciona data ao nome do arquivo: outputs/REPORT.md -> outputs/REPORT_20260224.md"""
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    root, ext = os.path.splitext(base_path)
    return f"{root}_{date_str}{ext}"


def save_reports(result: dict, output_base: str):
    """Salva report MD e JSON com data no nome."""
    os.makedirs(os.path.dirname(output_base) or ".", exist_ok=True)

    # MD report
    md_path = _dated_path(output_base)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(result["report_md"])
    logger.info("Report MD salvo em: %s", md_path)

    # JSON report
    json_base = os.path.splitext(output_base)[0]
    json_path = _dated_path(json_base + ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result["report_json"], f, ensure_ascii=False, indent=2)
    logger.info("Report JSON salvo em: %s", json_path)


def main():
    parser = argparse.ArgumentParser(description="Watcher de listas gov.br/compras")
    parser.add_argument("--dry-run", action="store_true", help="Nao grava no DB")
    parser.add_argument("--list-url", type=str, help="Processar apenas uma lista especifica")
    parser.add_argument("--limit", type=int, default=0, help="Max itens novos para ingerir (0=todos)")
    parser.add_argument("--skip-ingest", action="store_true", help="So registra em legal_source")
    parser.add_argument("--output", type=str, default="outputs/REPORT_WATCH_GOVBR.md", help="Caminho base do report")
    args = parser.parse_args()

    result = watch_govbr_all(
        dry_run=args.dry_run,
        limit=args.limit,
        skip_ingest=args.skip_ingest,
        list_url_filter=args.list_url,
    )

    # Salva reports com data no nome
    save_reports(result, args.output)

    # Summary
    logger.info(
        "=== Resumo final: %d novos, %d erros ===",
        result["total_new"], result["total_errors"],
    )


if __name__ == "__main__":
    main()
