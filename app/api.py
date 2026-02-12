import asyncio
import time
import logging
import json
from typing import Any
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from .config import *
from .worker_pool import WorkerPool, QueueFullError, metric_jobs_received
from .downstream import DownstreamClient

log = logging.getLogger("api")
app = FastAPI(title=APP_NAME)

# primitive in-memory TTL cache for read-heavy endpoint
_cache: dict[str, tuple[float, Any]] = {}

# components (populated at startup)
_pool: WorkerPool | None = None
_downstream: DownstreamClient | None = None

@app.on_event("startup")
async def startup_event() -> None:
    global _downstream, _pool
    # tracing: minimal, optional
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter
        trace.set_tracer_provider(TracerProvider())
        trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        log.info("otel tracer configured")
    except Exception:
        log.debug("otel not configured")
    _downstream = DownstreamClient(timeout=DOWNSTREAM_TIMEOUT, retries=DOWNSTREAM_RETRIES)
    _pool = WorkerPool(queue_size=QUEUE_SIZE, workers=WORKERS, downstream=_downstream)
    await _pool.start()
    log.info("api startup complete")

@app.on_event("shutdown")
async def shutdown_event() -> None:
    if _pool:
        await _pool.stop()

@app.post("/process")
async def process(request: Request) -> Any:
    payload = await request.json()
    metric_jobs_received.inc()
    try:
        job_id = await _pool.submit(payload, timeout=ENQUEUE_TIMEOUT)
    except QueueFullError:
        # queue full -> backpressure: ask client to retry later
        retry_after = 1
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="queue full", headers={"Retry-After": str(retry_after)})
    # Return accepted and let client poll or wait coroutines in real system
    return JSONResponse({"job_id": job_id}, status_code=status.HTTP_202_ACCEPTED)

@app.get("/item/{item_id}")
async def get_item(item_id: str) -> Any:
    now = time.time()
    cached = _cache.get(item_id)
    if cached and cached[0] > now:
        return {"id": item_id, "value": cached[1], "cached": True}
    # simulate DB read / demo
    if DEMO_DB:
        await asyncio.sleep(0.01)  # cheap local read
        value = {"from": "demo-db", "id": item_id}
    else:
        # placeholder for real async DB call
        await asyncio.sleep(0.02)
        value = {"from": "postgres", "id": item_id}
    _cache[item_id] = (now + CACHE_TTL, value)
    return {"id": item_id, "value": value, "cached": False}

@app.get("/metrics")
async def metrics() -> PlainTextResponse:
    data = generate_latest()
    return PlainTextResponse(data.decode(), media_type=CONTENT_TYPE_LATEST)

# health
@app.get("/healthz")
async def healthz() -> Any:
    return {"status": "ok"}
