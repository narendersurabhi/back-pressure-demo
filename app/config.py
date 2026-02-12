import os
from dataclasses import dataclass


def _bool_env(name, default=False):
    v = os.getenv(name)
    if v is None:
        return default
    return v.lower() in ("1", "true", "yes", "y")


@dataclass
class Config:
    # Postgres DSN, e.g. "postgresql://user:pass@localhost:5432/dbname"
    POSTGRES_DSN: str
    POOL_MIN: int
    POOL_MAX: int
    DEMO_MODE: bool
    # simple tuning knobs
    QUERY_TIMEOUT_SEC: int


config = Config(
    POSTGRES_DSN=os.getenv("POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/postgres"),
    POOL_MIN=int(os.getenv("POSTGRES_POOL_MIN", "1")),
    POOL_MAX=int(os.getenv("POSTGRES_POOL_MAX", "5")),
    DEMO_MODE=_bool_env("DEMO_MODE", default=True),
    QUERY_TIMEOUT_SEC=int(os.getenv("QUERY_TIMEOUT_SEC", "5")),
)
