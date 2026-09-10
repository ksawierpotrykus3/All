#!/usr/bin/env sh
set -e

mkdir -p /data
# Alembic migrations (best-effort: do not block startup when they fail,
# but DO surface the error in the logs instead of hiding it).
if [ -d /app/mvp/alembic ]; then
  if ! alembic -c /app/mvp/alembic.ini upgrade head; then
    echo "[entrypoint] WARNING: Alembic migration failed; continuing startup anyway" >&2
  fi
fi

exec uvicorn mvp.backend.main:app --host 0.0.0.0 --port 8000
