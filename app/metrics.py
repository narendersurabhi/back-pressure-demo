from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client import exposition

# Use a dedicated registry for clarity; apps can expose this via /metrics
registry = CollectorRegistry()

requests_total = Counter("app_requests_total", "Total requests handled", registry=registry)
request_latency_seconds = Histogram("app_request_latency_seconds", "Request latency seconds", buckets=(0.005,0.01,0.05,0.1,0.5,1,5), registry=registry)
cache_hits = Counter("app_cache_hits_total", "Cache hits", registry=registry)
cache_misses = Counter("app_cache_misses_total", "Cache misses", registry=registry)
db_pool_connections = Gauge("app_db_pool_connections", "DB pool connections in use (approx)", registry=registry)


def metrics_asgi_app(scope, receive, send):
    """A minimal ASGI app that serves /metrics using the registry."""
    assert scope["type"] == "http"
    async def send_response(body: bytes, status: int = 200, content_type: str = "text/plain; version=0.0.4"):
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", content_type.encode())]})
        await send({"type": "http.response.body", "body": body})

    data = generate_latest(registry)
    await send_response(data)


def export_metrics() -> bytes:
    """Return the latest metrics payload (Prometheus text format)."""
    return generate_latest(registry)
