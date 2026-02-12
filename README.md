# Async Worker Pool + Queue with Backpressure (prototype)

Compact prototype and plan for a resilient asynchronous worker pool with bounded queue/backpressure, retry logic, circuit-breaker, Postgres adapter (with demo-mode toggles), Prometheus metrics and Locust load tests for tuning.

Status: repo initialized with documentation and implementation plan. Code artifacts will follow in subsequent steps.

Prerequisites

- Python 3.9+
- Postgres (for full integration)

Quickstart (development)

1. Create and activate a virtualenv:
   python -m venv .venv && source .venv/bin/activate
2. Install deps:
   pip install -r requirements.txt
3. Read IMPLEMENTATION_PLAN.md for design, endpoints and test scenarios.

What will be implemented (high level)

- Bounded asyncio queue with configurable size and backpressure policy (reject or block caller)
- Worker pool using asyncio tasks and semaphore for worker occupancy
- Retry logic with exponential backoff + jitter
- Circuit-breaker protecting downstream Postgres adapter
- Postgres adapter with a demo mode (simulate responses, latency, failures)
- Prometheus metrics: queue depth, worker occupancy, rejected requests, processed successes/failures, retries, circuit-breaker state
- Locust scenarios to exercise normal load, spikes and sustained pressure to tune parameters

Contributing

Please follow the implementation plan in IMPLEMENTATION_PLAN.md. Open issues for design questions or trade-offs.