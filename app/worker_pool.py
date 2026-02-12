import asyncio
import logging
import time
import uuid
from typing import Any
from prometheus_client import Counter, Gauge
from . import config
from .downstream import DownstreamClient, DownstreamError

log = logging.getLogger("worker_pool")

QUEUE_FULL = "queue_full"

metric_jobs_received = Counter("jobs_received_total", "Jobs received")
metric_jobs_failed = Counter("jobs_failed_total", "Jobs failed")
metric_jobs_processed = Counter("jobs_processed_total", "Jobs processed")
metric_queue_size = Gauge("job_queue_size", "Current queue size")
metric_active_workers = Gauge("active_workers", "Active worker count")
metric_downstream_errors = Counter("downstream_errors_total", "Downstream errors")
metric_circuit_open = Gauge("circuit_open", "Circuit breaker open (0/1)")

class QueueFullError(Exception):
    pass

class WorkerPool:
    def __init__(self, queue_size: int, workers: int, downstream: DownstreamClient):
        self.queue: asyncio.Queue[tuple[str, dict, asyncio.Future]] = asyncio.Queue(maxsize=queue_size)
        self.workers = workers
        self.downstream = downstream
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for _ in range(self.workers):
            t = asyncio.create_task(self._worker_loop())
            self._tasks.append(t)
        log.info("worker pool started", extra={"workers": self.workers})

    async def stop(self) -> None:
        self._running = False
        for t in self._tasks:
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def submit(self, payload: dict, timeout: float | None = None) -> str:
        metric_jobs_received.inc()
        job_id = uuid.uuid4().hex
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        try:
            # try put with small timeout for backpressure
            if timeout is None:
                self.queue.put_nowait((job_id, payload, fut))
            else:
                await asyncio.wait_for(self.queue.put((job_id, payload, fut)), timeout=timeout)
            metric_queue_size.set(self.queue.qsize())
            return job_id
        except (asyncio.QueueFull, asyncio.TimeoutError):
            metric_jobs_failed.inc()
            raise QueueFullError()

    async def _worker_loop(self) -> None:
        while self._running:
            try:
                job_id, payload, fut = await self.queue.get()
                metric_queue_size.set(self.queue.qsize())
                metric_active_workers.inc()
                try:
                    # call downstream with overall timeout
                    res = await asyncio.wait_for(self.downstream.call(payload), timeout=config.JOB_TIMEOUT)
                    metric_jobs_processed.inc()
                    fut.set_result(res)
                except Exception as exc:
                    metric_jobs_failed.inc()
                    metric_downstream_errors.inc()
                    if getattr(self.downstream.cb, "is_open", lambda: False)():
                        metric_circuit_open.set(1)
                    else:
                        metric_circuit_open.set(0)
                    fut.set_exception(exc)
                    log.exception("job failed", extra={"job_id": job_id})
                finally:
                    metric_active_workers.dec()
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception:
                log.exception("worker loop unexpected")
                await asyncio.sleep(0.1)
