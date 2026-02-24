#!/usr/bin/env python3
# govy/db/run_migrations.py
"""
Runner de migrations SQL sequenciais.

Uso:
    python -m govy.db.run_migrations          # roda todas pendentes
    python -m govy.db.run_migrations --status  # mostra historico

Requer: POSTGRES_CONNSTR env var.
"""
from __future__ import annotations

import os
import sys
import glob
import hashlib
import logging
import argparse
from datetime import datetime, timezone

from govy.db.connection import get_conn, release_conn

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")

HISTORY_DDL = """
CREATE TABLE IF NOT EXISTS _migration_history (
    id          SERIAL PRIMARY KEY,
    filename    VARCHAR(200) NOT NULL UNIQUE,
    checksum    VARCHAR(64)  NOT NULL,
    applied_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);
"""


def _sha256_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return hashlib.sha256(f.read().encode("utf-8")).hexdigest()


def _ensure_history_table(conn):
    with conn.cursor() as cur:
        cur.execute(HISTORY_DDL)
    conn.commit()


def _get_applied(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM _migration_history ORDER BY id")
        return {row[0] for row in cur.fetchall()}


def _list_migrations() -> list[str]:
    pattern = os.path.join(MIGRATIONS_DIR, "*.sql")
    files = sorted(glob.glob(pattern))
    return files


def run_migrations():
    conn = get_conn()
    try:
        _ensure_history_table(conn)
        applied = _get_applied(conn)
        migrations = _list_migrations()

        pending = [
            m for m in migrations
            if os.path.basename(m) not in applied
        ]

        if not pending:
            logger.info("Nenhuma migration pendente.")
            print("Nenhuma migration pendente.")
            return 0

        for mpath in pending:
            fname = os.path.basename(mpath)
            checksum = _sha256_file(mpath)

            with open(mpath, "r", encoding="utf-8") as f:
                sql = f.read()

            logger.info("Aplicando migration: %s", fname)
            print(f"Aplicando: {fname} ...", end=" ")

            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO _migration_history (filename, checksum) VALUES (%s, %s)",
                        (fname, checksum),
                    )
                conn.commit()
                print("OK")
            except Exception as e:
                conn.rollback()
                logger.error("FALHA em %s: %s", fname, e)
                print(f"FALHA: {e}")
                return 1

        total = len(pending)
        print(f"\n{total} migration(s) aplicada(s) com sucesso.")
        return 0

    finally:
        release_conn(conn)


def show_status():
    conn = get_conn()
    try:
        _ensure_history_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT filename, checksum, applied_at "
                "FROM _migration_history ORDER BY id"
            )
            rows = cur.fetchall()

        migrations = _list_migrations()
        applied_set = {r[0] for r in rows}

        print(f"\n{'='*60}")
        print("Migration History")
        print(f"{'='*60}")

        if rows:
            for fname, checksum, applied_at in rows:
                ts = applied_at.strftime("%Y-%m-%d %H:%M:%S")
                print(f"  [OK] {fname}  ({ts})")

        pending = [
            os.path.basename(m) for m in migrations
            if os.path.basename(m) not in applied_set
        ]
        if pending:
            print()
            for fname in pending:
                print(f"  [--] {fname}  (pendente)")

        print(f"\nTotal: {len(rows)} aplicada(s), {len(pending)} pendente(s)")
        return 0

    finally:
        release_conn(conn)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="GOVY DB Migrations")
    parser.add_argument("--status", action="store_true", help="Mostra historico")
    args = parser.parse_args()

    if args.status:
        return show_status()
    return run_migrations()


if __name__ == "__main__":
    sys.exit(main())
