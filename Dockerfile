FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
# Create a minimal app at build-time so docker-compose is immediately useful
RUN mkdir -p /app/app
RUN cat > /app/app/main.py <<'PY'
from fastapi import FastAPI, Request, Response
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
tracer = trace.get_tracer(__name__)
log = structlog.get_logger()

app = FastAPI(title='fastapi-backpressure-demo')
REQUESTS = Counter('requests_total','Total HTTP requests', ['path','method','status'])

@app.middleware('http')
async def metrics_middleware(request: Request, call_next):
    with tracer.start_as_current_span('http_request'):
        resp = await call_next(request)
        REQUESTS.labels(path=request.url.path, method=request.method, status=str(resp.status_code)).inc()
        return resp

@app.get('/')
async def root():
    log.info('root_called')
    return {'ok': True, 'msg': 'placeholder app - full implementation coming soon'}

@app.get('/metrics')
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
PY

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
