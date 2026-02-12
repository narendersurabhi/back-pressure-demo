"""Compact Postgres adapter with demo-mode toggles.

Features:
- When DEMO_MODE=True uses an in-memory store (no psycopg2 import required).
- When DEMO_MODE=False uses psycopg2.pool.SimpleConnectionPool.
- Provides execute/fetchall/fetchone and explicit init/close of pool.
- Keeps implementation intentionally small and easy to extend.
"""

import logging
import re
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from app.config import config

logger = logging.getLogger(__name__)


class PostgresAdapter:
    def __init__(self, cfg=config):
        self.cfg = cfg
        self._pool = None
        # demo in-memory store: table -> list of dict rows
        self._demo_store: Dict[str, List[Dict[str, Any]]] = {}

    def init_pool(self):
        if self.cfg.DEMO_MODE:
            logger.info("PostgresAdapter: DEMO_MODE enabled, skipping real pool initialization")
            return
        try:
            import psycopg2.pool as _pool  # type: ignore
        except Exception as e:
            raise RuntimeError("psycopg2 is required when DEMO_MODE is False") from e
        self._pool = _pool.SimpleConnectionPool(self.cfg.POOL_MIN, self.cfg.POOL_MAX, dsn=self.cfg.POSTGRES_DSN)
        logger.info("PostgresAdapter: connection pool initialized")

    @contextmanager
    def _real_conn(self):
        assert self._pool is not None, "Pool not initialized"
        conn = self._pool.getconn()
        try:
            yield conn
        finally:
            try:
                self._pool.putconn(conn)
            except Exception:
                # swallow - pool shutdown in progress maybe
                pass

    # Very small SQL helpers for demo store (supports simple INSERT and SELECT *)
    _insert_re = re.compile(r"INSERT\s+INTO\s+(?P<table>\w+)\s*\((?P<cols>[^)]+)\)\s*VALUES\s*\((?P<vals>[^)]+)\)", re.I)
    _select_re = re.compile(r"SELECT\s+\*\s+FROM\s+(?P<table>\w+)(?:\s+WHERE\s+(?P<where>.+))?", re.I)

    def execute(self, query: str, params: Optional[List[Any]] = None) -> None:
        """Execute a statement. In demo mode supports basic INSERT semantics."""
        if self.cfg.DEMO_MODE:
            m = self._insert_re.search(query)
            if not m:
                raise NotImplementedError("Demo adapter only supports simple INSERT statements for execute()")
            table = m.group("table")
            cols = [c.strip() for c in m.group("cols").split(",")]
            # params expected as tuple/list aligning with cols
            if params is None:
                raise ValueError("params required for demo INSERT")
            vals = list(params)
            if len(cols) != len(vals):
                raise ValueError("column/value length mismatch")
            row = dict(zip(cols, vals))
            self._demo_store.setdefault(table, []).append(row)
            logger.debug("Demo INSERT into %s: %s", table, row)
            return

        with self._real_conn() as conn:
            cur = conn.cursor()
            try:
                cur.execute(query, params)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()

    def fetchall(self, query: str, params: Optional[List[Any]] = None) -> List[Dict[str, Any]]:
        """Return list of dict rows. In demo mode supports SELECT * FROM <table> [WHERE col=%s]."""
        if self.cfg.DEMO_MODE:
            m = self._select_re.search(query)
            if not m:
                raise NotImplementedError("Demo adapter only supports simple SELECT * FROM <table> [WHERE col=%s]")
            table = m.group("table")
            where = m.group("where")
            rows = list(self._demo_store.get(table, []))
            if where and params:
                # very small WHERE parser: expects single equality like "col = %s"
                parts = where.split("=")
                if len(parts) != 2:
                    raise NotImplementedError("Demo WHERE supports single equality only")
                col = parts[0].strip()
                val = params[0]
                rows = [r for r in rows if r.get(col) == val]
            logger.debug("Demo SELECT from %s returned %d rows", table, len(rows))
            return rows

        with self._real_conn() as conn:
            cur = conn.cursor()
            try:
                cur.execute(query, params)
                cols = [desc[0] for desc in cur.description] if cur.description else []
                results = [dict(zip(cols, row)) for row in cur.fetchall()]
                return results
            finally:
                cur.close()

    def fetchone(self, query: str, params: Optional[List[Any]] = None) -> Optional[Dict[str, Any]]:
        rows = self.fetchall(query, params)
        return rows[0] if rows else None

    def close(self):
        if self._pool:
            try:
                self._pool.closeall()
            finally:
                self._pool = None
            logger.info("PostgresAdapter: pool closed")


# Small convenience singleton for quick use
_adapter_singleton: Optional[PostgresAdapter] = None


def get_adapter() -> PostgresAdapter:
    global _adapter_singleton
    if _adapter_singleton is None:
        _adapter_singleton = PostgresAdapter()
        try:
            _adapter_singleton.init_pool()
        except Exception:
            # init_pool may raise if psycopg2 missing when DEMO_MODE False
            logger.exception("Failed to init postgres pool")
            raise
    return _adapter_singleton
