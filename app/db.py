import os
import asyncio
from typing import Any, Optional

_pool: Optional[Any] = None

class NoDBPool:
    """A tiny no-db pool that simulates latency for demo mode."""
    def __init__(self, latency: float = 0.01):
        self.latency = latency

    async def fetchrow(self, query: str, *args):
        await asyncio.sleep(self.latency)
        # return a predictable demo row
        return {"id": 1, "query": query, "args": args}

    async def execute(self, query: str, *args):
        await asyncio.sleep(self.latency)
        return "OK"

    async def close(self):
        return


try:
    import asyncpg
except Exception:  # pragma: no cover - optional
    asyncpg = None


class AsyncPGPoolWrapper:
    def __init__(self, pool: Any):
        self._pool = pool

    async def fetchrow(self, query: str, *args):
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def execute(self, query: str, *args):
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def close(self):
        await self._pool.close()


async def init_db(dsn: Optional[str] = None, min_size: int = 1, max_size: int = 10):
    """Initialize a global DB pool. If dsn is None or 'no-db', use a demo in-memory pool."""
    global _pool
    dsn = dsn or os.getenv("DATABASE_URL", "no-db")
    if dsn == "no-db" or not dsn:
        _pool = NoDBPool()
        return _pool

    if asyncpg is None:
        # fallback to no-db if asyncpg is absent
        _pool = NoDBPool()
        return _pool

    # create a real asyncpg pool
    _pool = AsyncPGPoolWrapper(await asyncpg.create_pool(dsn, min_size=min_size, max_size=max_size))
    return _pool


def get_db():
    if _pool is None:
        raise RuntimeError("DB pool not initialized. Call init_db() first.")
    return _pool


async def close_db():
    global _pool
    if _pool is None:
        return
    try:
        await _pool.close()
    finally:
        _pool = None


async def health_check(timeout: float = 1.0) -> bool:
    """Simple health check that runs a trivial query or simulates one in no-db mode."""
    try:
        pool = get_db()
    except RuntimeError:
        return False

    try:
        coro = pool.fetchrow("SELECT 1")
        await asyncio.wait_for(coro, timeout=timeout)
        return True
    except Exception:
        return False
