from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
import time
import asyncio

app = FastAPI(title="compact-metrics-app")

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "Request latency seconds", ["method", "path"]
)
INPROGRESS = Gauge("inprogress_requests", "In-progress requests")


@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    INPROGRESS.inc()
    start = time.time()
    try:
        response = await call_next(request)
        status = str(response.status_code)
        return response
    finally:
        elapsed = time.time() - start
        REQUEST_LATENCY.labels(request.method, request.url.path).observe(elapsed)
        REQUEST_COUNT.labels(request.method, request.url.path, status).inc()
        INPROGRESS.dec()


@app.get("/")
async def root():
    return {"status": "ok"}


@app.get("/work")
async def work(delay: float = 0.1):
    """Simulate work. Use ?delay=0.5 to increase latency for load testing."""
    # non-blocking simulated work so app can handle concurrency
    await asyncio.sleep(delay)
    return {"delay": delay}


@app.get("/metrics")
def metrics():
    """Expose Prometheus metrics."""
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    # Quick way to run: python src/app.py (for local testing)
    import uvicorn

    uvicorn.run("src.app:app", host="0.0.0.0", port=8000)
