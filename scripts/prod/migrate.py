"""Pre-start database step: schema migration and optional bootstrap admin.

Runs once in its own process BEFORE gunicorn starts (see scripts/prod/start.sh), instead of in
wsgi.py, so gunicorn workers never inherit database state from a parent process and do not all
run the migration at the same time.
"""
import os
import random
import sqlite3
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app import create_app  # noqa: E402

ATTEMPTS = 6


def _with_retry(label, fn):
    """Retry only lock/busy errors (e.g. a concurrent deploy holding the write lock)."""
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if attempt == ATTEMPTS or not ("locked" in message or "busy" in message):
                raise
            print(f"[migrate] {label}: database busy (attempt {attempt}/{ATTEMPTS}), retrying", flush=True)
            time.sleep(attempt + random.random())


def main():
    env = os.getenv("FLASK_ENV", "development")
    app = create_app(env)
    from app.services.bootstrap import bootstrap_admin
    from app.services.db_init import init_db

    with app.app_context():
        result = _with_retry("init_db", lambda: init_db(backup=False))
        print(f"[migrate] database ready: {result['database']}", flush=True)
        _with_retry("bootstrap", bootstrap_admin)
    print("[migrate] done", flush=True)


if __name__ == "__main__":
    main()
