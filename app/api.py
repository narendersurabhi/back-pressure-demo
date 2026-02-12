from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio

app = FastAPI()

class TaskPayload(BaseModel):
    task: object | None = None
    meta: dict | None = None


def _queue():
    q = getattr(app.state, "queue", None)
    if q is None:
        raise RuntimeError("Queue not initialized")
    return q


@app.post("/enqueue")
async def enqueue(payload: TaskPayload):
    q = _queue()
    try:
        q.put_nowait(payload.dict())
    except asyncio.QueueFull:
        metrics = getattr(app.state, "metrics", None)
        if metrics is not None:
            metrics["rejected"] = metrics.get("rejected", 0) + 1
        raise HTTPException(status_code=429, detail="Queue full, backpressure applied")
    metrics = getattr(app.state, "metrics", None)
    if metrics is not None:
        metrics["enqueued"] = metrics.get("enqueued", 0) + 1
    return {"status": "accepted", "queue_depth": q.qsize(), "queue_capacity": q.maxsize}


@app.get("/health")
async def health():
    q = getattr(app.state, "queue", None)
    metrics = getattr(app.state, "metrics", {})
    return {
        "status": "ok",
        "queue_depth": q.qsize() if q is not None else None,
        "queue_capacity": q.maxsize if q is not None else None,
        "metrics": metrics,
    }


@app.get("/ready")
async def ready():
    return {"ready": bool(getattr(app.state, "ready", False))}
