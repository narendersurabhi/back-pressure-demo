# IMPLEMENTATION_PLAN

Goal: Create IMPLEMENTATION_PLAN.md and implement: worker pool + queue with backpressure, retry logic and circuit-breaker; add Postgres adapter with demo-mode toggles; add Prometheus metrics for queue depth, worker occupancy, rejected requests; add Locust tests for load/pressure tuning. Keep implementation compact.

## Steps
- [x] Step 1: Initialize repo and docs (files: README.md, IMPLEMENTATION_PLAN.md, requirements.txt, .gitignore)
- [x] Step 2: Create app entry and config (files: app/main.py, app/config.py, app/api.py)
- [x] Step 3: Add Prometheus metrics integration (files: app/metrics.py, app/main.py)
- [x] Step 4: Implement worker pool with backpressure, retries and circuit-breaker (files: app/worker.py, app/config.py)
- [x] Step 5: Add Postgres adapter and demo-mode toggles (files: app/adapters/postgres.py, app/config.py)
- [x] Step 6: Expose HTTP API endpoints for enqueuing and health (files: app/api.py, app/main.py)
- [x] Step 7: Add Locust load/pressure tuning tests (files: locust/locustfile.py, locust/README.md)
- [x] Step 8: Docker and tests (files: Dockerfile, docker-compose.yml, tests/test_worker.py, pytest.ini)
