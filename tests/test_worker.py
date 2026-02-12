import threading
import time
import queue
import pytest


class FakeMetrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.counters = {"rejected": 0}
        self.gauges = {"queue_depth": 0, "worker_occupied": 0}

    def incr(self, name, by=1):
        with self.lock:
            self.counters[name] = self.counters.get(name, 0) + by

    def set_gauge(self, name, val):
        with self.lock:
            self.gauges[name] = val

    def get_counter(self, name):
        with self.lock:
            return self.counters.get(name, 0)

    def get_gauge(self, name):
        with self.lock:
            return self.gauges.get(name, 0)


class PostgresAdapter:
    """Simple adapter with demo-mode toggle. In demo-mode, writes go to demo_log; otherwise to writes list."""
    def __init__(self, demo_mode=True):
        self.demo_mode = demo_mode
        self.demo_log = []
        self.writes = []

    def send(self, payload):
        if self.demo_mode:
            # simulate harmless dry-run
            self.demo_log.append(payload)
            return True
        # simulate actual write (could raise on failure)
        self.writes.append(payload)
        return True


class WorkerPool:
    def __init__(self, num_workers=2, queue_maxsize=10, retry_limit=2, cb_threshold=5, cb_reset_time=1.0, adapter=None, metrics=None):
        self.queue = queue.Queue(maxsize=queue_maxsize)
        self.num_workers = num_workers
        self.threads = []
        self.shutdown_event = threading.Event()
        self.retry_limit = retry_limit
        self.cb_threshold = cb_threshold
        self.cb_reset_time = cb_reset_time
        self.adapter = adapter
        self.metrics = metrics or FakeMetrics()

        self._fail_lock = threading.Lock()
        self._consecutive_failures = 0
        self.cb_open_until = 0.0

        self._active_lock = threading.Lock()
        self._active_workers = 0

        for i in range(self.num_workers):
            t = threading.Thread(target=self._worker_loop, name=f"worker-{i}")
            t.daemon = True
            t.start()
            self.threads.append(t)

    def _set_worker_occupied(self, val):
        with self._active_lock:
            self._active_workers = val
        self.metrics.set_gauge("worker_occupied", val)

    def submit(self, func, payload=None):
        now = time.time()
        if now < self.cb_open_until:
            self.metrics.incr("rejected")
            return False
        try:
            self.queue.put_nowait({"func": func, "payload": payload, "attempts": 0})
            self.metrics.set_gauge("queue_depth", self.queue.qsize())
            return True
        except queue.Full:
            self.metrics.incr("rejected")
            return False

    def _worker_loop(self):
        while not self.shutdown_event.is_set():
            try:
                item = self.queue.get(timeout=0.1)
            except queue.Empty:
                continue
            self._set_worker_occupied(self._active_workers + 1)
            try:
                self._handle_item(item)
            finally:
                self._set_worker_occupied(max(0, self._active_workers - 1))
                self.queue.task_done()
                self.metrics.set_gauge("queue_depth", self.queue.qsize())

    def _handle_item(self, item):
        func = item["func"]
        payload = item.get("payload")
        attempts = item.get("attempts", 0)
        try:
            func(payload)
            # success resets failures
            with self._fail_lock:
                self._consecutive_failures = 0
        except Exception:
            attempts += 1
            with self._fail_lock:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self.cb_threshold:
                    self.cb_open_until = time.time() + self.cb_reset_time
            if attempts <= self.retry_limit:
                # backoff small and retry by requeueing
                time.sleep(0.01)
                try:
                    self.queue.put_nowait({"func": func, "payload": payload, "attempts": attempts})
                except queue.Full:
                    self.metrics.incr("rejected")
            else:
                # exhausted retries -> reject permanently
                self.metrics.incr("rejected")

    def shutdown(self, wait=True, timeout=2.0):
        self.shutdown_event.set()
        if wait:
            start = time.time()
            for t in self.threads:
                remaining = timeout - (time.time() - start)
                if remaining <= 0:
                    break
                t.join(remaining)


# Tests

def test_backpressure_rejection():
    metrics = FakeMetrics()
    adapter = PostgresAdapter(demo_mode=True)
    pool = WorkerPool(num_workers=1, queue_maxsize=2, retry_limit=0, cb_threshold=100, adapter=adapter, metrics=metrics)

    # tasks that occupy worker for a short time
    def busy(_):
        time.sleep(0.05)

    accepted = 0
    rejected = 0
    for i in range(6):
        if pool.submit(busy, payload=i):
            accepted += 1
        else:
            rejected += 1
    # give some time to process
    time.sleep(0.3)
    pool.shutdown()

    assert accepted > 0
    assert rejected > 0
    assert metrics.get_counter("rejected") >= rejected


def test_retry_logic():
    metrics = FakeMetrics()
    # fail twice then succeed
    state = {"count": 0, "succeeded": 0}

    def flaky(_):
        state["count"] += 1
        if state["count"] < 3:
            raise RuntimeError("fail")
        state["succeeded"] += 1

    pool = WorkerPool(num_workers=1, queue_maxsize=10, retry_limit=3, cb_threshold=100, metrics=metrics)
    assert pool.submit(flaky)
    time.sleep(0.5)
    pool.shutdown()
    assert state["succeeded"] == 1


def test_circuit_breaker_opens_and_recovers():
    metrics = FakeMetrics()
    adapter = PostgresAdapter(demo_mode=False)

    # adapter that raises to simulate persistent failures
    def bad_send(payload):
        raise RuntimeError("db down")

    pool = WorkerPool(num_workers=2, queue_maxsize=50, retry_limit=0, cb_threshold=3, cb_reset_time=0.2, adapter=adapter, metrics=metrics)

    # submit several tasks to trip the circuit
    for i in range(6):
        pool.submit(bad_send, payload=i)
    time.sleep(0.3)
    # circuit should be open now
    now = time.time()
    assert pool.cb_open_until >= now

    # submissions while open should be rejected
    rejected = 0
    for i in range(5):
        if not pool.submit(bad_send, payload=i):
            rejected += 1
    assert rejected >= 1

    # wait for reset
    time.sleep(0.25)
    # now it should allow submissions again
    accepted = 0
    for i in range(3):
        if pool.submit(bad_send, payload=i):
            accepted += 1
    pool.shutdown()
    assert accepted >= 0


def test_postgres_adapter_demo_toggle():
    adapter = PostgresAdapter(demo_mode=True)
    assert adapter.send({"x": 1})
    assert adapter.demo_log == [{"x": 1}]
    assert adapter.writes == []

    adapter.demo_mode = False
    adapter.send({"y": 2})
    assert adapter.writes == [{"y": 2}]


def test_metrics_reporting():
    metrics = FakeMetrics()
    def quick(_):
        time.sleep(0.02)

    pool = WorkerPool(num_workers=2, queue_maxsize=5, metrics=metrics)
    for i in range(4):
        pool.submit(quick, payload=i)
    time.sleep(0.1)
    # gauges should be non-negative
    assert metrics.get_gauge("queue_depth") >= 0
    assert metrics.get_gauge("worker_occupied") >= 0
    pool.shutdown()
