#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

# Load .env if present
if [ -f .env ]; then
  set -o allexport
  # shellcheck disable=SC1091
  source .env
  set +o allexport
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
UVICORN_WORKERS="${UVICORN_WORKERS:-1}"
NO_DB="${NO_DB:-false}"

# Derive DB host/port from DB_URL if needed
if [ "${NO_DB}" != "true" ]; then
  if { [ -z "${DB_HOST:-}" ] || [ -z "${DB_PORT:-}" ]; } && [ -n "${DB_URL:-}" ]; then
    read DB_HOST DB_PORT <<<$(python - <<'PY'
import os,urllib.parse as u
p=u.urlparse(os.environ.get('DB_URL',''))
print((p.hostname or 'localhost')+' '+str(p.port or 5432))
PY
)
  fi
  DB_HOST="${DB_HOST:-localhost}"
  DB_PORT="${DB_PORT:-5432}"

  echo "Waiting for database ${DB_HOST}:${DB_PORT}..."
  retries=30
  until bash -c "cat < /dev/tcp/${DB_HOST}/${DB_PORT}" >/dev/null 2>&1; do
    retries=$((retries-1))
    if [ $retries -le 0 ]; then
      echo "Timed out waiting for ${DB_HOST}:${DB_PORT}"
      exit 1
    fi
    sleep 1
  done
  echo "Database is available"
fi

# Default runtime flags
: ${PYTHONUNBUFFERED:=1}
export PYTHONUNBUFFERED

# Start app
exec uvicorn app.main:app --host "$HOST" --port "$PORT" --workers "$UVICORN_WORKERS" --proxy-headers
