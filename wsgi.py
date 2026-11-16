import os
import random
import sqlite3
import time

from app import create_app

env = os.getenv("FLASK_ENV", "development")
app = create_app(env)


def _with_retry(fn, attempts=6):
    """Gunicorn workers start together; on a shared database (Turso) their migrations can collide
    on the write lock, so retry busy/locked errors instead of crashing the worker."""
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if attempt == attempts or not ("locked" in message or "busy" in message):
                raise
            app.logger.warning("Database busy during startup (attempt %s/%s); retrying", attempt, attempts)
            time.sleep(attempt + random.random())


# Auto-create missing tables on startup (idempotent, additive only, no backup copy).
with app.app_context():
    from app.services.bootstrap import bootstrap_admin
    from app.services.db_init import init_db

    _with_retry(lambda: init_db(backup=False))
    _with_retry(bootstrap_admin)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config.get("DEBUG", False))
