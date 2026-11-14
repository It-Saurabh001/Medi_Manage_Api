"""`@idempotent` for POST routes, driven by the `Idempotency-Key` request header.

- Header absent: the view runs normally.
- First request: a placeholder row is reserved (concurrent duplicates get 409 CONFLICT),
  the view runs, and its response (status < 500) is stored.
- Retry with the same key + user + endpoint within IDEMPOTENCY_TTL_HOURS: the stored response
  is replayed with header `Idempotent-Replayed: true`.
- Exceptions / 5xx release the key so the client can retry.
- Rows older than the TTL are purged on access (cache table, not business data).

Place it *below* the auth decorator: `@role_required([...])` then `@idempotent`.
"""
from functools import wraps

from flask import current_app, make_response, request
from flask_jwt_extended import get_jwt_identity

from app.db import get_db
from app.errors import ConflictError, ValidationError
from app.utils.timeutil import utc_iso_before, utc_now_iso

HEADER = "Idempotency-Key"


def _identity():
    try:
        identity = get_jwt_identity()
    except Exception:
        identity = None
    return str(identity) if identity is not None else "anonymous"


def _reserve(key, user_id, endpoint):
    """Purge expired rows, then return the stored row or reserve a placeholder (returns None)."""
    ttl_hours = current_app.config.get("IDEMPOTENCY_TTL_HOURS", 24)
    conn = get_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM Idempotency_Keys WHERE created_at < ?", (utc_iso_before(ttl_hours),))
        row = conn.execute(
            """SELECT response_json, status_code, location FROM Idempotency_Keys
               WHERE key = ? AND user_id = ? AND endpoint = ?""",
            (key, user_id, endpoint),
        ).fetchone()
        if row is None:
            conn.execute(
                """INSERT INTO Idempotency_Keys(key, user_id, endpoint, response_json, status_code, location, created_at)
                   VALUES (?, ?, ?, NULL, 0, '', ?)""",
                (key, user_id, endpoint, utc_now_iso()),
            )
        conn.commit()
        return dict(row) if row is not None else None
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _store(key, user_id, endpoint, response):
    conn = get_db()
    try:
        with conn:
            conn.execute(
                """UPDATE Idempotency_Keys SET response_json = ?, status_code = ?, location = ?
                   WHERE key = ? AND user_id = ? AND endpoint = ?""",
                (response.get_data(as_text=True), response.status_code,
                 response.headers.get("Location", ""), key, user_id, endpoint),
            )
    finally:
        conn.close()


def _release(key, user_id, endpoint):
    conn = get_db()
    try:
        with conn:
            conn.execute(
                "DELETE FROM Idempotency_Keys WHERE key = ? AND user_id = ? AND endpoint = ? AND status_code = 0",
                (key, user_id, endpoint),
            )
    finally:
        conn.close()


def idempotent(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        raw_key = request.headers.get(HEADER)
        if raw_key is None:
            return view(*args, **kwargs)
        key = raw_key.strip()
        if not key or len(key) > 255:
            raise ValidationError(fields={HEADER: "must be 1-255 characters"})

        user_id = _identity()
        endpoint = f"{request.method} {request.path.rstrip('/')}"
        stored = _reserve(key, user_id, endpoint)
        if stored is not None:
            if not stored["status_code"]:
                raise ConflictError("A request with this Idempotency-Key is still being processed")
            response = current_app.response_class(
                stored["response_json"], status=stored["status_code"], mimetype="application/json"
            )
            if stored["location"]:
                response.headers["Location"] = stored["location"]
            response.headers["Idempotent-Replayed"] = "true"
            return response

        try:
            response = make_response(view(*args, **kwargs))
        except BaseException:
            _release(key, user_id, endpoint)
            raise
        if response.status_code >= 500:
            _release(key, user_id, endpoint)
        else:
            _store(key, user_id, endpoint, response)
        return response

    return wrapper
