import os
from typing import Any

def env(key: str, default: Any) -> Any:
    val = os.getenv(key)
    return type(default)(val) if val is not None and default is not None else (val if val is not None else default)

# Core settings (tweakable via env)
QUEUE_SIZE = int(env("QUEUE_SIZE", 50))
WORKERS = int(env("WORKERS", 4))
ENQUEUE_TIMEOUT = float(env("ENQUEUE_TIMEOUT", 0.05))
JOB_TIMEOUT = float(env("JOB_TIMEOUT", 5.0))
DOWNSTREAM_TIMEOUT = float(env("DOWNSTREAM_TIMEOUT", 2.0))
DOWNSTREAM_RETRIES = int(env("DOWNSTREAM_RETRIES", 2))
DOWNSTREAM_JITTER = float(env("DOWNSTREAM_JITTER", 0.08))
CB_FAILURE_THRESHOLD = int(env("CB_FAILURE_THRESHOLD", 5))
CB_RESET_SECONDS = int(env("CB_RESET_SECONDS", 10))
DEMO_DB = env("DEMO_DB", "true").lower() in ("1","true","yes")
DB_DSN = env("DB_DSN", "postgresql://user:pass@localhost/db")
CACHE_TTL = int(env("CACHE_TTL", 30))
DOWNSTREAM_FAIL_RATE = float(env("DOWNSTREAM_FAIL_RATE", 0.2))

# App metadata
APP_NAME = env("APP_NAME", "fastapi-backpressure-demo")
