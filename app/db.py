"""Single source of database connections for the whole application.

Two backends, same `sqlite3`-style API for every caller:
- Local SQLite file (default; development, tests, hosts with a persistent disk).
- Turso (hosted libSQL) when TURSO_DATABASE_URL is set, through the pure-Python HTTP client in
  app/turso_http.py (no native driver, no threads: safe with gunicorn's forked workers). Rows are
  name-addressable like sqlite3.Row and constraint failures raise sqlite3.IntegrityError, so the
  rest of the code is unchanged.
"""
import os
import sqlite3
from contextlib import contextmanager

from flask import current_app, has_app_context

DEFAULT_DB_NAME = "My_Medical_Shope.db"


def _setting(name, default=None):
    if has_app_context():
        return current_app.config.get(name, default)
    return os.getenv(name, default)


def get_database_name():
    """Configured DB path (app config inside an app context, env var otherwise)."""
    return _setting("DATABASE_NAME") or DEFAULT_DB_NAME


def turso_url():
    return (_setting("TURSO_DATABASE_URL") or "").strip()


def is_remote(db_name=None):
    """True when the configured database (not an explicitly named other file) lives on Turso."""
    return bool(turso_url()) and (db_name is None or db_name in (get_database_name(), turso_url()))


def get_db(db_name=None):
    """Open a connection with FK enforcement and name-addressable rows.

    The caller owns the connection and must close it (or use `db_connection`).
    """
    if is_remote(db_name):
        from app.turso_http import TursoConnection
        return TursoConnection(turso_url(), (_setting("TURSO_AUTH_TOKEN") or "").strip(),
                               setup_sql=("PRAGMA foreign_keys=ON",),
                               timeout=float(_setting("TURSO_TIMEOUT_SECONDS") or 15))
    conn = sqlite3.connect(db_name or get_database_name(), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_connection(immediate=False, db_name=None):
    """Yield a connection; commit on success, roll back on error, always close.

    immediate=True starts `BEGIN IMMEDIATE` (take the write lock up front), which
    every stock-changing flow must use.
    """
    conn = get_db(db_name)
    try:
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
