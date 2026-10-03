#!/bin/sh
set -e

# Run Gunicorn in production
exec gunicorn --workers "${WORKERS:-4}" --bind "${BIND:-0.0.0.0:5000}" "wsgi:app"
