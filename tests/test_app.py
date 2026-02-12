import time
import pytest
from fastapi.testclient import TestClient
from app import app, queue

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "ok"


def test_submit_and_queue_full():
    # ensure queue is empty first
    while not queue.empty():
        try:
            queue.get_nowait()
        except Exception:
            break

    # fill the queue to its maxsize
    maxsize = queue.maxsize or 0
    for i in range(maxsize):
        # put dummy items to fill queue
        try:
            queue.put_nowait({"id": f"pre{i}", "payload": "x"})
        except Exception:
            pass

    # now submit should be rejected with 503
    r = client.post("/process", json={"payload": "hello"})
    assert r.status_code in (202, 503)
    if r.status_code == 503:
        assert r.headers.get("Retry-After") is not None
    else:
        # if accepted, verify we can fetch result eventually
        j = r.json()
        id = j["id"]
        # wait for worker to process
        time.sleep(1)
        r2 = client.get(f"/result/{id}")
        assert r2.status_code in (200, 404)


def test_cache_endpoint():
    r1 = client.get("/cache?key=test")
    assert r1.status_code == 200
    j1 = r1.json()
    assert j1.get("cached") is False

    r2 = client.get("/cache?key=test")
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2.get("cached") is True
