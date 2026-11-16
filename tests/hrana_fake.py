"""Minimal in-process Hrana-over-HTTP server (`POST /v2/pipeline`) backed by a local SQLite file.

Lets the whole test suite run through app/turso_http.py without a Turso account:
    TEST_DB_BACKEND=turso-fake pytest
Each stream (baton) is one sqlite3 connection in autocommit mode, like a libSQL server stream.
"""
import base64
import json
import sqlite3
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = "test-token"


def _decode(value):
    kind = value["type"]
    if kind == "null":
        return None
    if kind == "integer":
        return int(value["value"])
    if kind == "float":
        return float(value["value"])
    if kind == "text":
        return value["value"]
    if kind == "blob":
        return base64.b64decode(value["base64"])
    raise ValueError(kind)


def _encode(value):
    if value is None:
        return {"type": "null"}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, bytes):
        return {"type": "blob", "base64": base64.b64encode(value).decode()}
    return {"type": "text", "value": str(value)}


class FakeHranaServer:
    def __init__(self, db_path):
        self.db_path = db_path
        self.streams = {}
        self.lock = threading.Lock()
        self.requests = 0
        server = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *args):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                if self.path != "/v2/pipeline":
                    return self._send(404, {"error": "not found"})
                if self.headers.get("Authorization") != f"Bearer {TOKEN}":
                    return self._send(401, {"error": "Unauthorized"})
                status, payload = server.pipeline(json.loads(body))
                self._send(status, payload)

            def _send(self, status, payload):
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def _open(self):
        conn = sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False, timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def pipeline(self, body):
        self.requests += 1
        baton = body.get("baton")
        with self.lock:
            conn = self.streams.pop(baton, None) if baton else self._open()
        if conn is None:
            return 400, {"error": "invalid baton"}
        results, closed = [], False
        for req in body.get("requests", []):
            kind = req["type"]
            if kind == "close":
                conn.close()
                closed = True
                results.append({"type": "ok", "response": {"type": "close"}})
            elif kind == "execute":
                stmt = req["stmt"]
                try:
                    cur = conn.execute(stmt["sql"], [_decode(a) for a in stmt.get("args", [])])
                    cols = [{"name": d[0], "decltype": None} for d in (cur.description or [])]
                    rows = [[_encode(v) for v in row] for row in cur.fetchall()]
                    results.append({"type": "ok", "response": {"type": "execute", "result": {
                        "cols": cols, "rows": rows, "affected_row_count": max(cur.rowcount, 0),
                        "last_insert_rowid": str(cur.lastrowid) if cur.lastrowid is not None else None}}})
                except sqlite3.Error as exc:
                    code = "SQLITE_CONSTRAINT" if isinstance(exc, sqlite3.IntegrityError) else "SQLITE_ERROR"
                    results.append({"type": "error", "error": {"message": f"SQLite error: {exc}", "code": code}})
            elif kind == "sequence":
                try:
                    conn.executescript(req["sql"])
                    results.append({"type": "ok", "response": {"type": "sequence"}})
                except sqlite3.Error as exc:
                    results.append({"type": "error", "error": {"message": str(exc), "code": "SQLITE_ERROR"}})
            else:
                results.append({"type": "error", "error": {"message": f"unsupported {kind}"}})
        new_baton = None
        if not closed:
            new_baton = uuid.uuid4().hex
            with self.lock:
                self.streams[new_baton] = conn
        return 200, {"baton": new_baton, "base_url": None, "results": results}

    def close_streams(self):
        with self.lock:
            for conn in self.streams.values():
                conn.close()
            self.streams.clear()

    def open_streams(self):
        with self.lock:
            return len(self.streams)

    def shutdown(self):
        self.close_streams()
        self.httpd.shutdown()
        self.httpd.server_close()
