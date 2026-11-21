#!/bin/sh
set -e

# 1) Database migration + optional bootstrap admin, in a separate process that is NOT forked.
python scripts/prod/migrate.py

# 2) Gunicorn. Workers are forked from a process that never touched the database,
#    so each worker opens its own connections.
#    Render (native Python runtime) provides $PORT; Docker/local fall back to 5000.
exec gunicorn --workers "${WORKERS:-4}" --bind "${BIND:-0.0.0.0:${PORT:-5000}}" "wsgi:app"
