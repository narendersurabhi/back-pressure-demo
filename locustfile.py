import random
import time
from locust import HttpUser, task, between


class BackpressureUser(HttpUser):
    wait_time = between(0.01, 0.2)

    @task(3)
    def process(self):
        payload = {"payload": "load-" + str(random.randint(0, 1000))}
        with self.client.post("/process", json=payload, catch_response=True, timeout=5) as r:
            if r.status_code in (429, 503):
                # simple retry with jitter
                time.sleep(0.1 + random.random() * 0.2)
                r2 = self.client.post("/process", json=payload, catch_response=True, timeout=5)
                if r2.status_code >= 500:
                    r2.failure(f"server {r2.status_code}")
            elif r.status_code >= 500:
                r.failure(f"server {r.status_code}")

    @task(1)
    def cache(self):
        self.client.get(f"/cache?key=locust")
