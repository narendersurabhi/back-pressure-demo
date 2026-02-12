Project: fastapi-backpressure-demo

Overview

This repository is a compact production-style FastAPI scaffold demonstrating explicit backpressure patterns:
- Concurrency limits and bounded queues with worker pools
- Load-shedding (429/503) with Retry-After headers
- Timeouts, retries, jitter and a circuit breaker for simulated downstreams
- Postgres connection pooling with a no-DB demo mode
- In-memory TTL cache for read-heavy endpoints
- Prometheus metrics and basic OpenTelemetry tracing
- Structured JSON logs and Locust load tests

This first step contains the project scaffold (metadata, Dockerfile, docker-compose and Makefile). The full implementation (handlers, workers, DB adapters, tests) will follow in subsequent steps.

Quickstart (local, minimal)

Prereqs: Python 3.11+, docker & docker compose

- Install deps locally:

  make install

- Run a minimal in-process placeholder app (no files required):

  make run

This starts a tiny inline FastAPI app for quick local smoke testing.

Docker (recommended to mirror production):

- Build and run with docker compose:

  docker compose up --build

Then visit http://localhost:8000/ and http://localhost:8000/metrics

Files in this scaffold

- Makefile: convenience commands: install, run, docker-build, docker-up, clean
- requirements.txt: minimal pinned dependencies used for the full project
- Dockerfile: container build; creates a minimal app (app/main.py) at image build time so docker compose works immediately
- docker-compose.yml: a single service for the web app; environment toggles can enable demo DB mode

Talk track / Architecture (short)

- Ingress: FastAPI receives requests. Controlled concurrency/backpressure at the edge prevents overload.
- Work queue: bounded async queue with worker pool executes expensive tasks; when full, requests are rejected early with 429/503 and Retry-After.
- Downstream resilience: client calls include timeouts, retry with jitter and a circuit-breaker to avoid cascading failures.
- Storage: Postgres connection pool for writes/reads; a demo/no-db mode uses an in-memory adapter for local runs.
- Read path optimizations: an in-memory TTL cache for read-heavy endpoints to reduce DB load.
- Observability: Prometheus metrics, structured logs (structlog), and OpenTelemetry traces (Console exporter for local runs).

Next steps

- Implement worker pool, queue, backpressure, retry logic and circuit-breaker
- Add Postgres adapter with demo mode toggles
- Add Prometheus metrics for queue depth, worker occupancy, rejected requests
- Add Locust tests for load / pressure tuning

Contributions

This scaffold is designed to be small and incremental. Open issues or proposals if you'd like features prioritized.
