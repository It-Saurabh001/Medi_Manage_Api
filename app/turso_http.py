"""Pure-Python Turso (libSQL) client over the Hrana HTTP protocol (`POST /v2/pipeline`).

No native code and no background threads, so it is safe with gunicorn's forking workers.
It mimics the parts of `sqlite3.Connection` / `sqlite3.Cursor` that this app uses:

- Legacy implicit transactions (like Python's sqlite3 with isolation_level=""): a BEGIN is sent
  automatically before INSERT/UPDATE/DELETE/REPLACE when no transaction is open, so
  commit()/rollback() and `with conn:` behave exactly as they do with sqlite3.
- A Hrana stream (server-side connection) is kept open only while a transaction is open.
  Outside a transaction every statement runs in its own one-shot stream, which costs a single
  HTTP round trip (setup statements such as `PRAGMA foreign_keys=ON` ride along in it).
- SQL errors raise sqlite3.IntegrityError / sqlite3.OperationalError, so existing
  `except sqlite3.IntegrityError` handlers keep working.
- Rows are `app.db_rows.Row`: tuple values, also readable by column name (case-insensitive).
"""
import base64
import datetime
import http.client
import json
import os
import re
import sqlite3
import threading
from urllib.parse import urlsplit

from app.db_rows import Row

PIPELINE_PATH = "/v2/pipeline"
_DML = {"INSERT", "UPDATE", "DELETE", "REPLACE"}
_FIRST_WORD = re.compile(r"(?:\s|--[^\n]*(?:\n|$)|/\*.*?\*/)*([A-Za-z]+)", re.S)
_ROLLBACK_TO = re.compile(r"\s*ROLLBACK\s+(?:TRANSACTION\s+)?TO\b", re.I)
_RETRYABLE = (http.client.RemoteDisconnected, http.client.CannotSendRequest, ConnectionResetError,
              BrokenPipeError, ConnectionAbortedError)

_local = threading.local()


# ---------------------------------------------------------------- HTTP transport
def _http_base(url):
    """libsql://host -> https://host (also accepts https:// and http:// for a local server)."""
    url = url.strip().rstrip("/")
    if url.startswith("libsql://"):
        url = "https://" + url[len("libsql://"):]
    if not url.startswith(("https://", "http://")):
        raise ValueError("TURSO_DATABASE_URL must start with libsql://, https:// or http://")
    return url


def _connection_for(base, timeout):
    """One keep-alive HTTP connection per (process, thread, host). Never shared across a fork."""
    pool = getattr(_local, "pool", None)
    if pool is None or getattr(_local, "pid", None) != os.getpid():
        pool = _local.pool = {}
        _local.pid = os.getpid()
    parts = urlsplit(base)
    key = (parts.scheme, parts.netloc)
    conn = pool.get(key)
    if conn is None:
        cls = http.client.HTTPSConnection if parts.scheme == "https" else http.client.HTTPConnection
        conn = pool[key] = cls(parts.netloc, timeout=timeout)
        conn._fresh = True
    return pool, key, conn


def _post(base, token, body, timeout):
    payload = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    path = urlsplit(base).path.rstrip("/") + PIPELINE_PATH
    for attempt in (1, 2):
        pool, key, conn = _connection_for(base, timeout)
        reused = not getattr(conn, "_fresh", False)
        conn._fresh = False
        try:
            conn.request("POST", path, body=payload, headers=headers)
            response = conn.getresponse()
            raw = response.read()
            status = response.status
            break
        except _RETRYABLE as exc:
            conn.close()
            pool.pop(key, None)
            # A kept-alive connection the server already dropped: safe to resend once.
            if attempt == 2 or not reused:
                raise sqlite3.OperationalError(f"Turso unreachable: {type(exc).__name__}") from exc
        except (OSError, http.client.HTTPException) as exc:
            conn.close()
            pool.pop(key, None)
            raise sqlite3.OperationalError(f"Turso unreachable: {type(exc).__name__}: {exc}") from exc
    if status != 200:
        detail = raw.decode("utf-8", "replace")[:300]
        try:
            detail = json.loads(detail).get("error", detail)
        except ValueError:
            pass
        hint = " (check TURSO_AUTH_TOKEN)" if status in (401, 403) else ""
        raise sqlite3.OperationalError(f"Turso HTTP {status}: {detail}{hint}")
    return json.loads(raw)


# ---------------------------------------------------------------- value encoding
def _encode(value):
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, str):
        return {"type": "text", "value": value}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {"type": "blob", "base64": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, datetime.datetime):  # same as sqlite3's default adapters
        return {"type": "text", "value": value.isoformat(" ")}
    if isinstance(value, datetime.date):
        return {"type": "text", "value": value.isoformat()}
    raise sqlite3.InterfaceError(f"Error binding parameter: type '{type(value).__name__}' is not supported")


def _decode(value):
    kind = value.get("type")
    if kind == "null":
        return None
    if kind == "integer":
        return int(value["value"])
    if kind == "float":
        return float(value["value"])
    if kind == "text":
        return value["value"]
    if kind == "blob":
        data = value.get("base64", "")
        return base64.b64decode(data + "=" * (-len(data) % 4))
    raise sqlite3.InterfaceError(f"Unknown value type from Turso: {kind}")


def _error(err):
    message = err.get("message", "unknown error")
    code = (err.get("code") or "").upper()
    if "CONSTRAINT" in code or "constraint failed" in message.lower():
        return sqlite3.IntegrityError(message)
    return sqlite3.OperationalError(message)


def _first_word(sql):
    match = _FIRST_WORD.match(sql)
    return match.group(1).upper() if match else ""


# ---------------------------------------------------------------- DB-API objects
class TursoCursor:
    def __init__(self, connection):
        self._connection = connection
        self._rows = []
        self._pos = 0
        self.description = None
        self.rowcount = -1
        self.lastrowid = None

    def _load(self, result):
        cols = result.get("cols") or []
        keys = tuple(col.get("name") or "" for col in cols)
        index = {}
        for i, name in enumerate(keys):
            index.setdefault(name.lower(), i)
        self.description = tuple((name, None, None, None, None, None, None) for name in keys) or None
        self._rows = [Row(tuple(_decode(v) for v in row), keys, index) for row in result.get("rows") or []]
        self._pos = 0
        self.rowcount = result.get("affected_row_count", -1) if not cols else -1
        last = result.get("last_insert_rowid")
        self.lastrowid = int(last) if last not in (None, "") else None

    def execute(self, sql, params=()):
        self._load(self._connection._run(sql, params))
        return self

    def executemany(self, sql, seq_of_params):
        total = 0
        for params in seq_of_params:
            self.execute(sql, params)
            total += max(self.rowcount, 0)
        self.rowcount = total
        return self

    def executescript(self, script):
        self._connection.executescript(script)
        return self

    def fetchone(self):
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return row

    def fetchmany(self, size=1):
        rows = self._rows[self._pos:self._pos + size]
        self._pos += len(rows)
        return rows

    def fetchall(self):
        rows = self._rows[self._pos:]
        self._pos = len(self._rows)
        return rows

    def __iter__(self):
        return iter(self.fetchall())

    def close(self):
        self._rows = []


class TursoConnection:
    def __init__(self, url, auth_token="", setup_sql=(), timeout=15.0):
        self._base = _http_base(url)
        self._token = auth_token or ""
        self._setup = list(setup_sql)
        self._timeout = timeout
        self._baton = None      # open server-side stream (only while a transaction is open)
        self._stream_base = None
        self._in_tx = False
        self._closed = False

    @property
    def in_transaction(self):
        return self._in_tx

    def _pipeline(self, requests, close_stream):
        if self._closed:
            raise sqlite3.ProgrammingError("Cannot operate on a closed database.")
        new_stream = self._baton is None
        setup = [{"type": "execute", "stmt": {"sql": sql}} for sql in self._setup] if new_stream else []
        body = {"baton": self._baton,
                "requests": setup + requests + ([{"type": "close"}] if close_stream else [])}
        try:
            data = _post(self._stream_base or self._base, self._token, body, self._timeout)
        except BaseException:
            self._baton = self._stream_base = None  # the stream is unusable now
            self._in_tx = False
            raise
        if close_stream:
            self._baton = self._stream_base = None
        else:
            self._baton = data.get("baton")
            self._stream_base = data.get("base_url") or self._stream_base
        results = data.get("results") or []
        for result in results[:len(setup)]:
            if result.get("type") == "error":
                raise _error(result.get("error") or {})
        return results[len(setup):len(setup) + len(requests)]

    def _run(self, sql, params=()):
        word = _first_word(sql)
        statements = []
        implicit_begin = word in _DML and not self._in_tx
        if implicit_begin:
            statements.append({"type": "execute", "stmt": {"sql": "BEGIN"}})
        if word in ("BEGIN", "SAVEPOINT"):
            in_tx_after = True
        elif word in ("COMMIT", "END") or (word == "ROLLBACK" and not _ROLLBACK_TO.match(sql)):
            in_tx_after = False
        else:
            in_tx_after = self._in_tx or implicit_begin
        args = [_encode(p) for p in (params or ())]
        statements.append({"type": "execute", "stmt": {"sql": sql, "args": args, "want_rows": True}})

        results = self._pipeline(statements, close_stream=not in_tx_after)
        if implicit_begin and results and results[0].get("type") == "error":
            self._in_tx = False
            raise _error(results[0].get("error") or {})
        main = results[-1] if results else {"type": "error", "error": {"message": "empty response"}}
        if main.get("type") == "error":
            # A failed BEGIN opens nothing; any other failure leaves the transaction as it was.
            self._in_tx = self._in_tx if word == "BEGIN" else in_tx_after
            if word == "BEGIN" and not self._in_tx and self._baton:
                self._close_stream()
            raise _error(main.get("error") or {})
        self._in_tx = in_tx_after
        return main["response"]["result"]

    def _close_stream(self):
        if self._baton:
            try:
                self._pipeline([], close_stream=True)
            except Exception:
                self._baton = self._stream_base = None

    # sqlite3.Connection API -------------------------------------------------
    def cursor(self):
        return TursoCursor(self)

    def execute(self, sql, params=()):
        return self.cursor().execute(sql, params)

    def executemany(self, sql, seq_of_params):
        return self.cursor().executemany(sql, seq_of_params)

    def executescript(self, script):
        self.commit()  # like sqlite3: commit any pending transaction first
        results = self._pipeline([{"type": "sequence", "sql": script}], close_stream=True)
        if results and results[0].get("type") == "error":
            raise _error(results[0].get("error") or {})
        return self.cursor()

    def commit(self):
        if self._in_tx:
            try:
                self._run("COMMIT")
            except sqlite3.OperationalError as exc:
                if "no transaction is active" not in str(exc):
                    raise
                self._in_tx = False

    def rollback(self):
        if self._in_tx:
            try:
                self._run("ROLLBACK")
            except sqlite3.OperationalError as exc:
                if "no transaction is active" not in str(exc):
                    raise
            finally:
                self._in_tx = False
                self._close_stream()

    def close(self):
        if not self._closed:
            self._close_stream()  # closing the stream rolls back anything uncommitted
            self._in_tx = False
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        return False
