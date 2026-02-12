import asyncio
import random
import time
from typing import Any
from . import config

class DownstreamError(Exception):
    pass

class CircuitBreaker:
    def __init__(self, fail_threshold: int, reset_seconds: int):
        self.fail_threshold = fail_threshold
        self.reset_seconds = reset_seconds
        self.fail_count = 0
        self.opened_at = 0.0

    def record_success(self) -> None:
        self.fail_count = 0

    def record_failure(self) -> None:
        self.fail_count += 1
        if self.fail_count >= self.fail_threshold:
            self.opened_at = time.time()

    def is_open(self) -> bool:
        if self.opened_at == 0:
            return False
        if time.time() - self.opened_at > self.reset_seconds:
            # move to half-open
            self.fail_count = 0
            self.opened_at = 0
            return False
        return True

class DownstreamClient:
    def __init__(self, timeout: float | None = None, retries: int = 2):
        self.timeout = timeout or config.DOWNSTREAM_TIMEOUT
        self.retries = retries
        self.cb = CircuitBreaker(config.CB_FAILURE_THRESHOLD, config.CB_RESET_SECONDS)

    async def _do_call(self, payload: dict) -> dict:
        # Simulate network latency and random failure
        await asyncio.sleep(random.uniform(0.01, 0.2))
        if random.random() < config.DOWNSTREAM_FAIL_RATE:
            raise DownstreamError("simulated downstream failure")
        # echo back with some processing
        return {"result": payload.get("value", None), "processed_at": time.time()}

    async def call(self, payload: dict) -> dict:
        if self.cb.is_open():
            raise DownstreamError("circuit-open")
        last_exc: Exception | None = None
        for attempt in range(1, self.retries + 2):
            try:
                return await asyncio.wait_for(self._do_call(payload), timeout=self.timeout)
            except Exception as exc:
                last_exc = exc
                # record failure and maybe open circuit
                self.cb.record_failure()
                if isinstance(exc, DownstreamError) and str(exc) == "circuit-open":
                    raise exc
                jitter = random.uniform(0, config.DOWNSTREAM_JITTER)
                await asyncio.sleep(jitter)
                continue
        raise last_exc or DownstreamError("unknown")
