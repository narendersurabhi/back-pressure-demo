from prometheus_client import Counter, Gauge, Histogram

# Prometheus metrics
QUEUE_DEPTH = Gauge('app_queue_depth', 'Number of items in the work queue')
WORKER_OCCUPIED = Gauge('app_worker_occupied', 'Number of workers currently processing tasks')
REJECTED_REQUESTS = Counter('app_rejected_requests_total', 'Number of requests rejected due to backpressure or circuit-breaker')
TASK_LATENCY = Histogram('app_task_latency_seconds', 'Task processing latency in seconds')


def set_queue_depth(n: int):
    QUEUE_DEPTH.set(n)


def inc_worker():
    WORKER_OCCUPIED.inc()


def dec_worker():
    WORKER_OCCUPIED.dec()


def inc_rejected():
    REJECTED_REQUESTS.inc()


def observe_latency(sec: float):
    TASK_LATENCY.observe(sec)
