import os
import random
import re
import gevent
from locust import HttpUser, task, between

ENABLED = set([s.strip() for s in os.getenv("ENABLED_USERS", "steady,burst,ramp,monitor").split(",") if s.strip()])

def enabled(name):
    return 1 if name in ENABLED else 0

METRICS_PATH = os.getenv("METRICS_PATH", "/metrics")

def parse_metrics(text):
    # simple Prometheus-style parser for numeric gauges
    out = {}
    for line in text.splitlines():
        m = re.match(r"^(?P<name>[a-zA-Z0-9_]+)\s+(?P<val>[0-9+.eE-]+)$", line.strip())
        if m:
            out[m.group('name')] = float(m.group('val'))
    return out

class SteadyUser(HttpUser):
    """Steady, continuous arrival rate to exercise baseline throughput."""
    wait_time = between(0.2, 0.5)
    weight = enabled('steady')

    @task
    def enqueue(self):
        payload = {
            "job_id": random.randint(1, 1_000_000),
            "size": random.choice(["small", "med", "large"]),
        }
        with self.client.post("/enqueue", json=payload, catch_response=True, name="enqueue") as r:
            if r.status_code >= 500 or r.status_code == 429:
                r.failure(f"server:{r.status_code}")
            else:
                r.success()

class BurstyUser(HttpUser):
    """Burst pattern: many requests in a tight loop then pause.
    Configure BURST_SIZE and BURST_PAUSE via env.
    """
    wait_time = between(1, 2)
    weight = enabled('burst')
    burst_size = int(os.getenv("BURST_SIZE", "50"))
    burst_pause = float(os.getenv("BURST_PAUSE", "1"))

    @task
    def burst(self):
        for i in range(self.burst_size):
            self.client.post("/enqueue", json={"burst_idx": i}, name="enqueue.burst")
        gevent.sleep(self.burst_pause)

class RampUser(HttpUser):
    """Ramp test: ramp up batch sizes over a few steps to find breaking point.
    Configure RAMP_STEPS, RAMP_BATCH, RAMP_PAUSE via env.
    """
    wait_time = between(0, 0)
    weight = enabled('ramp')
    steps = int(os.getenv("RAMP_STEPS", "5"))
    batch = int(os.getenv("RAMP_BATCH", "20"))
    pause = float(os.getenv("RAMP_PAUSE", "2"))

    @task
    def ramp(self):
        # perform increasing-load batches
        for step in range(self.steps):
            count = self.batch * (step + 1)
            for i in range(count):
                self.client.post("/enqueue", json={"step": step, "i": i}, name="enqueue.ramp")
            gevent.sleep(self.pause)
        # cooldown
        gevent.sleep(self.pause * 2)

class MonitorUser(HttpUser):
    """Poll Prometheus metrics and print key values (queue_depth, worker_occupancy, rejected_requests).
    Helpful to observe backpressure/circuit-breaker behavior while tuning.
    """
    wait_time = between(5, 10)
    weight = enabled('monitor')

    @task
    def poll_metrics(self):
        r = self.client.get(METRICS_PATH, name="metrics")
        if r.status_code == 200:
            vals = parse_metrics(r.text)
            # print selected metrics for quick CLI visibility
            for k in ("queue_depth", "worker_occupancy", "rejected_requests"):
                if k in vals:
                    print(f"METRIC {k}={vals[k]}")
        else:
            print(f"metrics fetch failed: {r.status_code}")
