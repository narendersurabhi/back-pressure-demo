import time
import asyncio
from typing import Any, Callable, Dict, Optional, Awaitable

class TTLCache:
    def __init__(self):
        self._data: Dict[str, tuple[float, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    def _now(self) -> float:
        return time.monotonic()

    async def get(self, key: str) -> Optional[Any]:
        entry = self._data.get(key)
        if not entry:
            return None
        exp, val = entry
        if exp < self._now():
            # expired
            async with self._global_lock:
                # double-check inside lock
                entry2 = self._data.get(key)
                if entry2 and entry2[0] < self._now():
                    self._data.pop(key, None)
            return None
        return val

    async def set(self, key: str, value: Any, ttl: float = 60.0) -> None:
        exp = self._now() + ttl
        self._data[key] = (exp, value)

    async def get_or_set(self, key: str, loader: Callable[[], Awaitable[Any]], ttl: float = 60.0) -> Any:
        # fast path
        val = await self.get(key)
        if val is not None:
            return val
        # per-key lock to dedupe loaders
        async with self._global_lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
        async with lock:
            # another check after acquiring lock
            val = await self.get(key)
            if val is not None:
                return val
            val = await loader()
            await self.set(key, val, ttl)
            # cleanup locks to avoid growth
            async with self._global_lock:
                self._locks.pop(key, None)
            return val

    async def clear(self):
        self._data.clear()


_default_cache = TTLCache()

async def cache_get(key: str):
    return await _default_cache.get(key)

async def cache_get_or_set(key: str, loader: Callable[[], Awaitable[Any]], ttl: float = 60.0):
    return await _default_cache.get_or_set(key, loader, ttl)
