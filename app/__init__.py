import asyncio
import time
import uuid
import random
import logging
from typing import Any
from fastapi import FastAPI, HTTPException, Response, Request
from starlette.responses import JSONResponse
from .schemas import ProcessRequest, ProcessResponse, Health

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger("backpressure")

app = FastAPI(title="backpressure-demo")

# Backpressure / queue / worker pool config
QUEUE_MAXSIZE = 10
WORKERS = 3
TASK_TIMEOUT = 2.0
RETRY_AFTER_SEC = 1

# runtime state
queue: asyncio.Queue = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
results: dict[str, dict[str, Any]] = {}
start_time = time.time()

# simple circuit breaker state
_cb = {"failures": 0, "open_until": 0}
CB_FAILURE_THRESHOLD = 5
CB_OPEN_SECONDS = 5

# simple TTL cache for read-heavy endpoint
_cache: dict[str, tuple[float, Any]] = {}
CACHE_TTL = 5.0


async def simulated_downstream(payload: str) -> str:
    """Simulated unreliable downstream: random failures and latency."""
    now = time.time()
    if _cb["open_until"] > now:
        raise RuntimeError("circuit-open")

    # simulate latency
    await asyncio.sleep(0.2 + random.random() * 0.4)

    # random failure
    if random.random() < 0.2:
        raise RuntimeError("downstream-failure")

    return payload[::-1]


async def process_item(item: dict):
    id = item["id"]
    payload = item["payload"]
    results[id] = {"status": "processing"}
    attempt = 0
    while attempt < 3:
        attempt += 1
        try:
            res = await asyncio.wait_for(simulated_downstream(payload), timeout=TASK_TIMEOUT)
            results[id] = {"status": "done", "result": res}
            # success resets circuit breaker
            _cb["failures"] = 0
            return
        except Exception as exc:
            log.info({"event": "task-fail", "id": id, "err": str(exc), "attempt": attempt})
            _cb["failures"] += 1
            if _cb["failures"] >= CB_FAILURE_THRESHOLD:
                _cb["open_until"] = time.time() + CB_OPEN_SECONDS
                log.info({"event": "circuit-open", "open_until": _cb["open_until"]})
            # simple backoff with jitter
            await asyncio.sleep(0.1 * attempt + random.random() * 0.1)
    results[id] = {"status": "failed", "error": "max-retries"}


async def worker_loop(idx: int):
    log.info({"event": "worker-start", "idx": idx})
    while True:
        item = await queue.get()
        try:
            await process_item(item)
        except Exception as exc:
            log.info({"event": "worker-except", "err": str(exc)})
        finally:
            queue.task_done()


@app.on_event("startup")
async def startup():
    # start worker pool
    for i in range(WORKERS):
        asyncio.create_task(worker_loop(i))
    log.info({"event": "startup", "workers": WORKERS, "queue_maxsize": QUEUE_MAXSIZE})


@app.post("/process", response_model=ProcessResponse, status_code=202)
async def submit(req: ProcessRequest):
    # quick fail if circuit is open
    if _cb["open_until"] > time.time():
        return JSONResponse({"detail": "service temporarily unavailable"}, status_code=503, headers={"Retry-After": str(RETRY_AFTER_SEC)})

    id = uuid.uuid4().hex
    item = {"id": id, "payload": req.payload}
    try:
        queue.put_nowait(item)
    except asyncio.QueueFull:
        return JSONResponse({"detail": "backlog full"}, status_code=503, headers={"Retry-After": str(RETRY_AFTER_SEC)})
    results[id] = {"status": "queued"}
    return {"id": id, "status": "accepted"}


@app.get("/result/{id}")
async def get_result(id: str):
    r = results.get(id)
    if not r:
        raise HTTPException(status_code=404, detail="not found")
    return r


@app.get("/health", response_model=Health)
async def health():
    return {"status": "ok", "uptime": time.time() - start_time}


@app.get("/cache")
async def get_cached(key: str = "time"):
    now = time.time()
    v = _cache.get(key)
    if v and v[0] > now:
        return {"key": key, "value": v[1], "cached": True}
    # populate cache (cheap computation)
    val = {"ts": now, "rand": random.random()}
    _cache[key] = (now + CACHE_TTL, val)
    return {"key": key, "value": val, "cached": False}


__all__ = ["app"]
