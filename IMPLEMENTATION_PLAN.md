# IMPLEMENTATION_PLAN

Goal: You are a senior backend engineer. Build a compact production-style Python 3.11+ FastAPI repository that demonstrates explicit backpressure: concurrency limits, bounded queue with worker pool, load shedding with 429/503 and Retry-After, timeouts/retries/jitter and a circuit breaker for a simulated downstream, Postgres connection pooling with a no-DB demo mode, in-memory TTL cache for a read-heavy endpoint, Prometheus metrics, structured JSON logs, basic OpenTelemetry tracing, Locust load tests, Dockerfile and docker-compose, Makefile, CI, README with architecture and talk track. Keep dependencies minimal and implementation compact so it runs locally with 'make run' and in Docker with 'docker compose up'.

## Steps
- [x] Step 1: Project scaffold (repo metadata, Docker and compose) (files: README.md, Makefile, requirements.txt, Dockerfile, docker-compose.yml)
- [x] Step 2: Core FastAPI app, API routes and worker + downstream simulation (files: app/main.py, app/api.py, app/config.py, app/worker_pool.py, app/downstream.py)
- [x] Step 3: DB pool (no-db mode), in-memory TTL cache, Prometheus metrics, logging and tracing (files: app/db.py, app/cache.py, app/metrics.py, app/logging_config.py, app/tracer.py)
- [x] Step 4: Schemas, package init, simple tests and load test (Locust), dockerignore (files: app/schemas.py, app/__init__.py, tests/test_app.py, locustfile.py, .dockerignore)
- [x] Step 5: Run scripts and environment example for local/Docker runs (files: scripts/start.sh, .env.example, pytest.ini)
- [x] Step 6: CI workflow and docker-compose override for local dev (files: .github/workflows/ci.yml, docker-compose.override.yml)
