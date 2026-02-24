#!/usr/bin/env python3
"""
Batch ingest de legislacao: blob → extract → chunk → Postgres.

Uso:
    python scripts/legal_ingest_batch.py --dry-run           # simula sem gravar
    python scripts/legal_ingest_batch.py --limit 5           # primeiros 5
    python scripts/legal_ingest_batch.py --doc-id lei_14133_2021_federal_br
    python scripts/legal_ingest_batch.py                     # todos

Requer:
    POSTGRES_CONNSTR (env var) — connection string do Postgres
    Azure credentials (az login ou Managed Identity)
"""
from __future__ import annotations

import sys
import os
import json
import logging
import argparse
from datetime import datetime, timezone

# Adiciona raiz do projeto ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from govy.legal.pipeline import process_batch, list_raw_blobs


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Batch ingest de legislacao")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem gravar no DB")
    parser.add_argument("--limit", type=int, default=0, help="Max docs a processar (0=todos)")
    parser.add_argument("--doc-id", type=str, default=None, help="Processar apenas um doc_id")
    parser.add_argument("--list-blobs", action="store_true", help="Lista blobs e sai")
    parser.add_argument("--registry", type=str, default=None,
                        help="Path para JSON de registry com metadata overrides")
    parser.add_argument("--output", type=str, default=None,
                        help="Path para salvar resultado JSON")
    args = parser.parse_args()

    # List blobs mode
    if args.list_blobs:
        blobs = list_raw_blobs()
        for b in blobs:
            print(f"  {b['name']}  ({b['size']} bytes)")
        print(f"\nTotal: {len(blobs)} blobs")
        return 0

    # Load registry override if provided
    registry = None
    if args.registry:
        with open(args.registry, "r", encoding="utf-8") as f:
            registry = json.load(f)
        print(f"Registry carregado: {len(registry)} entradas")

    # Run batch
    results = process_batch(
        limit=args.limit,
        dry_run=args.dry_run,
        doc_id_filter=args.doc_id,
        registry=registry,
    )

    # Summary
    ok = sum(1 for r in results if r.get("status") == "ok")
    skipped = sum(1 for r in results if r.get("status") == "skipped")
    dry = sum(1 for r in results if r.get("status") == "dry_run")
    total_provisions = sum(r.get("provisions", 0) for r in results)
    total_chunks = sum(r.get("chunks", 0) for r in results)

    print(f"\n{'='*60}")
    print(f"Resultado do batch")
    print(f"{'='*60}")
    print(f"  Total processados: {len(results)}")
    print(f"  OK:                {ok}")
    print(f"  Skipped:           {skipped}")
    print(f"  Dry-run:           {dry}")
    print(f"  Total provisions:  {total_provisions}")
    print(f"  Total chunks:      {total_chunks}")

    # Detail per doc
    for r in results:
        status = r.get("status", "?")
        doc_id = r.get("doc_id", r.get("blob_name", "?"))
        chunks = r.get("chunks", 0)
        provisions = r.get("provisions", 0)
        print(f"  [{status}] {doc_id}: {provisions} provisions, {chunks} chunks")

    # Save output
    if args.output:
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": args.dry_run,
            "limit": args.limit,
            "summary": {
                "total": len(results), "ok": ok, "skipped": skipped, "dry_run": dry,
                "total_provisions": total_provisions, "total_chunks": total_chunks,
            },
            "results": results,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        print(f"\nRelatorio salvo em: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
