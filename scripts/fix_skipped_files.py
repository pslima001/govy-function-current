#!/usr/bin/env python3
"""
Corrige os 5 arquivos skipped da Fase 0 e os re-ingere no pipeline.

Os 5 skipped:
  1. D12807.pdf           → Decreto 12.807
  2. INSTRUCAO NORMATIVA SEGES.pdf  → IN SEGES (inferir numero/ano do texto)
  3. L14133.pdf           → Lei 14.133/2021
  4. L14981.pdf           → Lei 14.981/2024
  5. LeideLicitaeseContratos14133traduzidaemingles.pdf → Lei 14.133 (english, skip or tag)

Uso:
    python scripts/fix_skipped_files.py --dry-run    # simula
    python scripts/fix_skipped_files.py              # grava no DB

Requer: POSTGRES_CONNSTR + Azure credentials
"""
from __future__ import annotations

import sys
import os
import logging
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from govy.legal.pipeline import process_one

logger = logging.getLogger(__name__)

# Metadata corrigida para os 5 skipped
FIXES = [
    {
        "blob_name": "D12807.pdf",
        "registry": {
            "doc_id": "decreto_12807_federal_br",
            "doc_type": "decreto",
            "number": "12807",
            "year": None,  # sera inferido do texto se possivel
            "title": "Decreto 12.807",
            "title_short": "Decreto 12.807",
        },
    },
    {
        "blob_name": "INSTRUCAO NORMATIVA SEGES.pdf",
        "registry": {
            "doc_id": "instrucao_normativa_seges_federal_br",
            "doc_type": "instrucao_normativa",
            "number": None,
            "year": None,
            "title": "Instrucao Normativa SEGES",
            "title_short": "IN SEGES",
        },
    },
    {
        "blob_name": "L14133.pdf",
        "registry": {
            "doc_id": "lei_14133_2021_federal_br",
            "doc_type": "lei",
            "number": "14133",
            "year": 2021,
            "title": "Lei 14.133/2021 - Lei de Licitacoes e Contratos",
            "title_short": "Lei 14.133/2021",
        },
    },
    {
        "blob_name": "L14981.pdf",
        "registry": {
            "doc_id": "lei_14981_2024_federal_br",
            "doc_type": "lei",
            "number": "14981",
            "year": 2024,
            "title": "Lei 14.981/2024",
            "title_short": "Lei 14.981/2024",
        },
    },
    {
        "blob_name": "LeideLicitaeseContratos14133traduzidaemingles.pdf",
        "registry": {
            "doc_id": "lei_14133_2021_en_federal_br",
            "doc_type": "lei",
            "number": "14133",
            "year": 2021,
            "title": "Lei 14.133/2021 - English translation",
            "title_short": "Lei 14.133/2021 (EN)",
        },
    },
]


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Fix 5 skipped files from Fase 0")
    parser.add_argument("--dry-run", action="store_true", help="Simula sem gravar")
    args = parser.parse_args()

    results = []
    for fix in FIXES:
        blob_name = fix["blob_name"]
        registry_entry = fix["registry"]

        print(f"\nProcessando: {blob_name} → {registry_entry['doc_id']}")

        try:
            result = process_one(
                blob_name=blob_name,
                dry_run=args.dry_run,
                registry_entry=registry_entry,
            )
            results.append(result)
            status = result.get("status", "?")
            chunks = result.get("chunks", 0)
            print(f"  [{status}] {chunks} chunks")
        except Exception as e:
            logger.exception("ERRO em %s: %s", blob_name, e)
            results.append({"blob_name": blob_name, "status": "error", "error": str(e)})

    print(f"\n{'='*60}")
    ok = sum(1 for r in results if r.get("status") in ("ok", "dry_run"))
    err = sum(1 for r in results if r.get("status") == "error")
    print(f"Total: {len(results)}, OK: {ok}, Errors: {err}")

    return 0 if err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
