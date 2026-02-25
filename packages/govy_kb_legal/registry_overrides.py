# govy/legal/registry_overrides.py
"""
Aplica overrides manuais de metadata a documentos no DB.

Overrides sao definidos em normas-juridicas-registry/federal/overrides.json.
Cada override especifica doc_id, campos a atualizar, e motivo.

Uso:
  python -m govy.legal.registry_overrides [--dry-run]
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

OVERRIDES_PATH = Path(__file__).parent.parent.parent / "normas-juridicas-registry" / "federal" / "overrides.json"

# Campos permitidos para override
ALLOWED_FIELDS = {"published_at", "effective_from", "effective_to", "status_vigencia"}


def load_overrides(path: Optional[Path] = None) -> list:
    """Carrega overrides do JSON."""
    p = path or OVERRIDES_PATH
    if not p.exists():
        logger.warning("Overrides file not found: %s", p)
        return []
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("overrides", [])


def _parse_date(val: str) -> Optional[date]:
    """Parse YYYY-MM-DD string to date."""
    if not val:
        return None
    parts = val.split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def apply_overrides(dry_run: bool = False, path: Optional[Path] = None) -> List[dict]:
    """
    Aplica overrides ao DB.

    Returns:
        Lista de resultados: [{doc_id, status, fields_updated}]
    """
    overrides = load_overrides(path)
    if not overrides:
        logger.info("Nenhum override para aplicar.")
        return []

    from govy.db.connection import get_conn, release_conn

    results = []
    conn = get_conn()
    try:
        for ov in overrides:
            doc_id = ov.get("doc_id")
            reason = ov.get("reason", "")
            fields = ov.get("fields", {})

            if not doc_id or not fields:
                logger.warning("Override invalido (sem doc_id ou fields): %s", ov)
                continue

            # Filtra so campos permitidos
            update_fields = {k: v for k, v in fields.items() if k in ALLOWED_FIELDS}
            if not update_fields:
                logger.warning("Override %s: nenhum campo permitido", doc_id)
                continue

            # Verifica se doc existe
            with conn.cursor() as cur:
                cur.execute("SELECT doc_id FROM legal_document WHERE doc_id = %s", (doc_id,))
                if not cur.fetchone():
                    logger.warning("Override %s: doc_id nao encontrado no DB", doc_id)
                    results.append({"doc_id": doc_id, "status": "not_found"})
                    continue

            if dry_run:
                logger.info("DRY RUN override %s: %s (reason: %s)", doc_id, update_fields, reason)
                results.append({"doc_id": doc_id, "status": "dry_run", "fields": list(update_fields.keys())})
                continue

            # Build dynamic UPDATE
            set_parts = ["updated_at = now()"]
            params = []
            for k, v in update_fields.items():
                set_parts.append(f"{k} = %s")
                if k in ("published_at", "effective_from", "effective_to"):
                    params.append(_parse_date(v) if v else None)
                else:
                    params.append(v)
            params.append(doc_id)

            sql = f"UPDATE legal_document SET {', '.join(set_parts)} WHERE doc_id = %s"

            with conn.cursor() as cur:
                cur.execute(sql, params)

            conn.commit()
            logger.info("Override aplicado: %s → %s (reason: %s)", doc_id, update_fields, reason)
            results.append({
                "doc_id": doc_id,
                "status": "applied",
                "fields": list(update_fields.keys()),
            })

    except Exception:
        conn.rollback()
        logger.exception("Erro ao aplicar overrides")
        raise
    finally:
        release_conn(conn)

    return results


if __name__ == "__main__":
    import argparse
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Apply overrides to legal_document")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    results = apply_overrides(dry_run=args.dry_run)
    for r in results:
        print(f"  {r['doc_id']}: {r['status']}")
