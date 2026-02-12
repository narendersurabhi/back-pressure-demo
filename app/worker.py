import asyncio
import time
import random
import logging
from typing import Any, Callable
from prometheus_client import start_http_server, Gauge, Counter
import config

logger = logging.getLogger("worker")
logging.basicConfig(level=logging.INFO)

# Metrics
QUEUE_DEPTH = Gauge("queue_depth", "Current depth of task queue")
WORKER_BUSY = Gauge("worker_occupied", "Number of busy workers")
REJECTED = Counter("rejected_requests_total", "Total rejected requests due to backpressure")
PROCESS_ERRORS = Counter("process_errors_total", "Total processing errors")
PROCESS_SUCCESS = Counter("process_success_total", "Total successful processings")


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(self, threshold: int, reset_timeout: float):
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.opened_at = None

    def record_success(self):
        self.failures = 0
        self.opened_at = None

    def record_failure(self):
        self.failures += 1
        if self.failures >= self.threshold and self.opened_at is None:
            self.opened_at = time.time()
            logger.warning("circuit opened (threshold reached)")

    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.time() - self.opened_at >= self.reset_timeout:
            # reset (half-open simplified behavior)
            logger.info("circuit reset timeout elapsed; allowing trial")
            self.failures = 0
            self.opened_at = None
            return False
        return True


class PostgresAdapter:
    """Simple adapter that supports demo-mode toggles and integrates with a CircuitBreaker.
    In demo mode writes are simulated; otherwise a blocking DB interaction is executed in an executor.
    """

    def __init__(self, dsn: str, demo_mode: bool, circuit: CircuitBreaker):
        self.dsn = dsn
        self.demo = demo_mode
        self.circuit = circuit

    async def write(self, payload: Any):
        if self.circuit.is_open():
            raise CircuitOpenError("circuit is open")

        # Demo mode: simulate latency and occasional errors
        if self.demo:
            await asyncio.sleep(random.uniform(0.01, 0.05))
            # introduce a small chance of failure to exercise retries/circuit-breaker
            if random.random() < 0.05:
                self.circuit.record_failure()
                raise RuntimeError("simulated db failure")
            self.circuit.record_success()
            return {"status": "ok", "demo": True}

        # Non-demo: perform a blocking DB op in executor to keep asyncio loop responsive
        # Keep implementation compact: simulate blocking work as placeholder for real DB call
        loop = asyncio.get_event_loop()

        def blocking_db_call(payload):
            time.sleep(0.05 + random.random() * 0.05)
            # In a real implementation you'd use psycopg2/asyncpg here using self.dsn
            if random.random() < 0.02:
                raise RuntimeError("db insert failed")
            return {"status": "ok", "demo": False}

        try:
            result = await loop.run_in_executor(None, blocking_db_call, payload)
            self.circuit.record_success()
            return result
        except Exception:
            self.circuit.record_failure()
            raise


class WorkerPool:
    def __init__(self,
                 handler: Callable[[Any], Any],
                 maxsize: int = config.QUEUE_MAXSIZE,
                 workers: int = config.WORKER_COUNT,
                 max_retries: int = config.MAX_RETRIES,
                 backoff_base: float = config.BACKOFF_BASE,
                 metrics_port: int = config.METRICS_PORT,
                 demo_mode: bool = config.DEMO_MODE):
        self.queue = asyncio.Queue(maxsize=maxsize)
        self.handler = handler
        self.workers = workers
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._tasks = []
        self._stopping = False
        self.occupied = 0
        self.circuit = CircuitBreaker(config.CIRCUIT_FAILURE_THRESHOLD, config.CIRCUIT_RESET_TIMEOUT)
        self.adapter = PostgresAdapter(config.POSTGRES_DSN, demo_mode, self.circuit)
        # start metrics server in background thread
        start_http_server(metrics_port)
        logger.info(f"metrics available on :{metrics_port}")

    async def start(self):
        for _ in range(self.workers):
            t = asyncio.create_task(self._worker_loop())
            self._tasks.append(t)
        logger.info(f"started {self.workers} workers")

    async def stop(self):
        self._stopping = True
        # wake workers
        for _ in range(len(self._tasks)):
            await self.queue.put(None)
        await asyncio.gather(*self._tasks, return_exceptions=True)
        logger.info("workers stopped")

    async def submit(self, payload: Any, block: bool = False, timeout: float = None) -> bool:
        try:
            if block:
                await asyncio.wait_for(self.queue.put(payload), timeout=timeout)
                QUEUE_DEPTH.set(self.queue.qsize())
                return True
            else:
                self.queue.put_nowait(payload)
                QUEUE_DEPTH.set(self.queue.qsize())
                return True
        except (asyncio.QueueFull, asyncio.TimeoutError):
            REJECTED.inc()
            logger.debug("submit rejected due to backpressure")
            return False

    async def _worker_loop(self):
        while True:
            item = await self.queue.get()
            QUEUE_DEPTH.set(self.queue.qsize())
            if item is None:
                # shutdown sentinel
                break
            self.occupied += 1
            WORKER_BUSY.set(self.occupied)
            try:
                await self._process_with_retries(item)
            finally:
                self.occupied -= 1
                WORKER_BUSY.set(self.occupied)
                self.queue.task_done()
            if self._stopping:
                break

    async def _process_with_retries(self, payload: Any):
        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            try:
                # handler may use adapter
                if self.handler:
                    await self.handler(payload, self.adapter)
                else:
                    # fallback: direct adapter write
                    await self.adapter.write(payload)
                PROCESS_SUCCESS.inc()
                return
            except CircuitOpenError:
                # immediate fail fast when circuit is open; record and stop retrying
                PROCESS_ERRORS.inc()
                logger.warning("circuit open; rejecting task without retries")
                return
            except Exception as exc:
                PROCESS_ERRORS.inc()
                logger.debug(f"processing error attempt={attempt}: {exc}")
                if attempt > self.max_retries:
                    logger.error(f"task failed after {attempt-1} retries: {exc}")
                    return
                backoff = self.backoff_base * (2 ** (attempt - 1))
                # jitter
                backoff = backoff * (0.8 + random.random() * 0.4)
                await asyncio.sleep(backoff)


# Example handler used by the pool; small and async-friendly
async def example_handler(payload, adapter: PostgresAdapter):
    # do light processing then write
    await asyncio.sleep(0)
    await adapter.write(payload)


if __name__ == "__main__":
    # quick demo run
    async def main():
        pool = WorkerPool(handler=example_handler)
        await pool.start()

        # flood the queue to exercise backpressure
        async def producer():
            for i in range(500):
                ok = await pool.submit({"i": i}, block=False)
                if not ok:
                    logger.info(f"rejected at {i}")
                await asyncio.sleep(0.005)

        await asyncio.gather(producer())
        # wait for a bit then shutdown
        await asyncio.sleep(2)
        await pool.stop()

    asyncio.run(main())