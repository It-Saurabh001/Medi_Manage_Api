#!/bin/sh
set -e

# 1) Database migration + optional bootstrap admin, in a separate process that is NOT forked.
python scripts/prod/migrate.py

# 2) Gunicorn. Workers are forked from a process that never touched the database,
#    so each worker opens its own connections.
exec gunicorn --workers "${WORKERS:-4}" --bind "${BIND:-0.0.0.0:5000}" "wsgi:app"
