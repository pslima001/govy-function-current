# govy/db/connection.py
"""
Pool de conexoes Postgres — singleton, lazy init.

Uso:
    from govy.db.connection import get_conn, release_conn

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    finally:
        release_conn(conn)

Config:
    POSTGRES_CONNSTR (env var): connection string completa
    Formato: "host=... port=5432 dbname=govy user=... password=... sslmode=require"
"""
from __future__ import annotations

import os
import logging
import threading

import psycopg2
from psycopg2 import pool as pg_pool

logger = logging.getLogger(__name__)

_pool: pg_pool.SimpleConnectionPool | None = None
_lock = threading.Lock()

MIN_CONN = 1
MAX_CONN = 5


def _get_connstr() -> str:
    connstr = os.environ.get("POSTGRES_CONNSTR", "")
    if not connstr:
        raise RuntimeError(
            "POSTGRES_CONNSTR nao configurada. "
            "Defina como app setting ou env var."
        )
    return connstr


def _init_pool() -> pg_pool.SimpleConnectionPool:
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                connstr = _get_connstr()
                _pool = pg_pool.SimpleConnectionPool(
                    MIN_CONN, MAX_CONN, connstr
                )
                logger.info("Postgres pool inicializado (max=%d)", MAX_CONN)
    return _pool


def get_conn():
    """Retorna uma conexao do pool."""
    p = _init_pool()
    conn = p.getconn()
    conn.autocommit = False
    return conn


def release_conn(conn, close: bool = False):
    """Devolve conexao ao pool."""
    if _pool is not None and conn is not None:
        _pool.putconn(conn, close=close)


def close_pool():
    """Fecha todas as conexoes (shutdown)."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None
        logger.info("Postgres pool fechado")
