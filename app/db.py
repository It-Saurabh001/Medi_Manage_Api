"""Single source of database connections for the whole application.

Two backends, same `sqlite3`-style API for every caller:
- Local SQLite file (default; development, tests, hosts with a persistent disk).
- Turso (hosted libSQL) when TURSO_DATABASE_URL is set. The `libsql` driver returns plain
  tuples and raises ValueError, so `LibsqlConnection` adapts it: rows support `row["col"]`
  (case-insensitive, like sqlite3.Row) and constraint failures raise sqlite3.IntegrityError,
  so existing `except sqlite3.IntegrityError` handlers keep working unchanged.

DB_DRIVER=libsql forces the libsql driver on a local file (used to run the test suite through it).
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
        import libsql
        conn = LibsqlConnection(libsql.connect(turso_url(), auth_token=(_setting("TURSO_AUTH_TOKEN") or "").strip()))
        conn.execute("PRAGMA foreign_keys=ON")
        return conn
    path = db_name or get_database_name()
    if (_setting("DB_DRIVER") or "sqlite").strip().lower() == "libsql":
        import libsql
        conn = LibsqlConnection(libsql.connect(path, timeout=5))
    else:
        conn = sqlite3.connect(path, timeout=5)
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


# ---------------------------------------------------------------- libsql adapter
def _translate(exc):
    """Map a libsql error (always ValueError) onto the sqlite3 exception hierarchy."""
    message = str(exc)
    if "constraint failed" in message or "CONSTRAINT" in message:
        return sqlite3.IntegrityError(message)
    return sqlite3.OperationalError(message)


def _call(fn, *args):
    try:
        return fn(*args)
    except sqlite3.Error:
        raise
    except Exception as exc:  # libsql raises ValueError / libsql.Error for every SQL failure
        raise _translate(exc) from exc


class Row(tuple):
    """Tuple whose values can also be read by column name, case-insensitively (like sqlite3.Row)."""

    def __new__(cls, values, keys, index):
        row = super().__new__(cls, values)
        row._keys, row._index = keys, index
        return row

    def __getitem__(self, key):
        if isinstance(key, str):
            try:
                key = self._index[key.lower()]
            except KeyError:
                raise IndexError("No item with that key") from None
        return tuple.__getitem__(self, key)

    def keys(self):
        return list(self._keys)


class LibsqlCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._keys = self._index = None

    def _prepare(self):
        description = self._cursor.description or ()
        self._keys = tuple(col[0] for col in description)
        self._index = {}
        for i, name in enumerate(self._keys):
            self._index.setdefault(name.lower(), i)

    def _row(self, values):
        return None if values is None else Row(values, self._keys, self._index)

    def execute(self, sql, params=()):
        _call(self._cursor.execute, sql, tuple(params))
        self._prepare()
        return self

    def executemany(self, sql, seq_of_params):
        _call(self._cursor.executemany, sql, [tuple(p) for p in seq_of_params])
        self._prepare()
        return self

    def executescript(self, script):
        _call(self._cursor.executescript, script)
        return self

    def fetchone(self):
        return self._row(_call(self._cursor.fetchone))

    def fetchmany(self, size=None):
        rows = _call(self._cursor.fetchmany, size) if size is not None else _call(self._cursor.fetchmany)
        return [self._row(r) for r in rows]

    def fetchall(self):
        return [self._row(r) for r in _call(self._cursor.fetchall)]

    def __iter__(self):
        return iter(self.fetchall())

    @property
    def rowcount(self):
        return self._cursor.rowcount

    @property
    def lastrowid(self):
        return self._cursor.lastrowid

    @property
    def description(self):
        return self._cursor.description

    def close(self):
        self._cursor.close()


class LibsqlConnection:
    """sqlite3.Connection look-alike over a libsql connection (local file or Turso)."""

    def __init__(self, conn):
        self._conn = conn

    def cursor(self):
        return LibsqlCursor(self._conn.cursor())

    def execute(self, sql, params=()):
        return self.cursor().execute(sql, params)

    def executemany(self, sql, seq_of_params):
        return self.cursor().executemany(sql, seq_of_params)

    def executescript(self, script):
        return self.cursor().executescript(script)

    @property
    def in_transaction(self):
        return self._conn.in_transaction

    def commit(self):
        _call(self._conn.commit)

    def rollback(self):
        _call(self._conn.rollback)

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False
