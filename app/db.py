"""Single source of SQLite connections for the whole application."""
import os
import sqlite3
from contextlib import contextmanager

from flask import current_app, has_app_context

DEFAULT_DB_NAME = "My_Medical_Shope.db"


def get_database_name():
    """Configured DB path (app config inside an app context, env var otherwise)."""
    if has_app_context():
        return current_app.config.get("DATABASE_NAME") or DEFAULT_DB_NAME
    return os.getenv("DATABASE_NAME", DEFAULT_DB_NAME)


def get_db(db_name=None):
    """Open a connection with WAL, busy timeout, FK enforcement and Row factory.

    The caller owns the connection and must close it (or use `db_connection`).
    """
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
