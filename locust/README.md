# Locust load/pressure tuning tests

## Purpose
- Provide compact Locust scenarios to exercise the worker-pool + queue implementation under different patterns: steady, bursty, and ramp-up. A monitoring user polls Prometheus metrics to observe queue depth, worker occupancy and rejected requests.

## How to use
- Configure which scenarios to enable via ENABLED_USERS (comma-separated): steady, burst, ramp, burst, monitor.
- Configure per-test parameters via environment variables:
  - BURST_SIZE (default 50)
  - BURST_PAUSE (default 1)
  - RAMP_STEPS (default 5)
  - RAMP_BATCH (default 20)
  - RAMP_PAUSE (default 2)
  - METRICS_PATH (default /metrics)

## Examples
- Steady baseline (50 users, spawn 5/sec, 10 minutes):
  ENABLED_USERS=steady locust -f locust/locustfile.py --headless -u 50 -r 5 -t 10m --host=http://localhost:8000

- Burst test (single burst generator):
  ENABLED_USERS=burst locust -f locust/locustfile.py --headless -u 5 -r 1 -t 5m --env BURST_SIZE=200 --host=http://localhost:8000

- Ramp test (find breaking point):
  ENABLED_USERS=ramp,monitor locust -f locust/locustfile.py --headless -u 20 -r 2 -t 15m --env RAMP_STEPS=8 --env RAMP_BATCH=30 --host=http://localhost:8000

## Tips for tuning
- Start with a steady run to establish baseline throughput and average queue depth.
- Use ramp tests to identify the user/load level that causes queue growth, higher worker occupancy and rejections (429).
- Use burst tests to validate backpressure and rejection behavior under short spikes.
- Monitor /metrics output (queue_depth, worker_occupancy, rejected_requests) while tuning worker pool size, queue limits, retry windows and circuit-breaker thresholds.

## Notes
- The script expects an HTTP endpoint /enqueue that accepts JSON job payloads and a Prometheus /metrics endpoint exposing gauges named queue_depth, worker_occupancy and rejected_requests for easy observation.
- Use ENABLED_USERS to focus Locust on a subset of scenarios. If multiple classes are enabled they will run concurrently and share the configured users count.
