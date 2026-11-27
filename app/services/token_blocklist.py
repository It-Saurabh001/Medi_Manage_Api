"""JWT revocation: Redis in production (OTP_STORE_PROVIDER == 'prod'), in-memory otherwise.

Two mechanisms, both checked by flask-jwt-extended's `token_in_blocklist_loader` on every request:
- per token (`jti`): logout and refresh-token rotation;
- per account (`revoke_account_tokens`): every token issued before a moment is rejected. Used when an
  account is blocked, deleted or disabled, and when its password or email changes, so stolen or stale
  tokens (including 30-day refresh tokens) stop working immediately instead of at their expiry.
"""
import threading
import time

from flask import current_app, g

from app.extensions import jwt


def _account_key(account_type, account_id):
    return f"{account_type}:{account_id}"


class MemoryTokenBlocklist:
    def __init__(self):
        self._items = {}
        self._accounts = {}
        self._lock = threading.Lock()

    def add(self, jti, ttl_seconds):
        with self._lock:
            self._items[jti] = time.time() + max(1, int(ttl_seconds))

    def contains(self, jti):
        with self._lock:
            expiry = self._items.get(jti)
            if expiry is None:
                return False
            if time.time() > expiry:
                self._items.pop(jti, None)
                return False
            return True

    def revoke_account(self, account_key, revoked_at, ttl_seconds, reason):
        with self._lock:
            self._accounts[account_key] = (_encode(revoked_at, reason), time.time() + max(1, int(ttl_seconds)))

    def account_revoked_at(self, account_key):
        """(revoked_at, reason) or None."""
        with self._lock:
            record = self._accounts.get(account_key)
            if record is None:
                return None
            if time.time() > record[1]:
                self._accounts.pop(account_key, None)
                return None
            return _decode(record[0])


class RedisTokenBlocklist:
    def __init__(self, redis_url):
        import redis

        self._client = redis.from_url(redis_url)

    def add(self, jti, ttl_seconds):
        self._client.setex(f"jwt_blocklist:{jti}", max(1, int(ttl_seconds)), "1")

    def contains(self, jti):
        return bool(self._client.exists(f"jwt_blocklist:{jti}"))

    def revoke_account(self, account_key, revoked_at, ttl_seconds, reason):
        self._client.setex(f"jwt_account_revoked:{account_key}", max(1, int(ttl_seconds)),
                           _encode(revoked_at, reason))

    def account_revoked_at(self, account_key):
        return _decode(self._client.get(f"jwt_account_revoked:{account_key}"))

    def check(self, jti, account_key):
        """One round trip for both lookups (hot path: every authenticated request)."""
        blocked, record = self._client.mget(f"jwt_blocklist:{jti}", f"jwt_account_revoked:{account_key}")
        return blocked is not None, _decode(record)


def _encode(revoked_at, reason):
    return f"{revoked_at!r}|{reason}"


def _decode(value):
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    stamp, _, reason = str(value).partition("|")
    try:
        return float(stamp), (reason or "revoked")
    except ValueError:
        return None


def _issued_at(payload):
    """Sub-second issue time (`ts` claim from issue_tokens); falls back to the standard `iat`."""
    value = payload.get("ts", payload.get("iat"))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _payload_account_key(payload):
    from app.services.auth_service import account_type_from_claims

    return _account_key(account_type_from_claims(payload), payload.get("sub"))


def is_token_revoked(payload):
    """True if the token is revoked. The account-level reason is left in `g.jwt_revoked_reason` so the
    error handler can answer with the same code the app already handles (e.g. ACCOUNT_BLOCKED)."""
    store = current_app.extensions["token_blocklist"]
    jti, account_key = payload.get("jti"), _payload_account_key(payload)
    if hasattr(store, "check"):
        blocked, record = store.check(jti, account_key)
    else:
        blocked, record = store.contains(jti), store.account_revoked_at(account_key)
    g.jwt_revoked_reason = None
    if blocked:
        return True
    if record is None:
        return False
    revoked_at, reason = record
    issued = _issued_at(payload)
    if issued is None or issued <= revoked_at:
        g.jwt_revoked_reason = reason
        return True
    return False


def init_token_blocklist(app):
    """Create the app's blocklist and register flask-jwt-extended's `token_in_blocklist_loader`."""
    if str(app.config.get("OTP_STORE_PROVIDER", "dev")).lower() == "prod":
        app.extensions["token_blocklist"] = RedisTokenBlocklist(app.config.get("REDIS_URL"))
    else:
        app.extensions["token_blocklist"] = MemoryTokenBlocklist()

    @jwt.token_in_blocklist_loader
    def _is_revoked(jwt_header, jwt_payload):
        return is_token_revoked(jwt_payload)


def revoke_token(payload):
    """Revoke a decoded JWT payload until its natural expiry."""
    exp = payload.get("exp") or (time.time() + 3600)
    current_app.extensions["token_blocklist"].add(payload["jti"], exp - time.time())


REVOCATION_REASONS = ("blocked", "disabled", "deleted", "credentials")


def revoke_account_tokens(account_type, account_id, reason="credentials"):
    """Reject every token issued to this account up to now (kept for the refresh-token lifetime).

    reason picks the error the client then gets (see app/errors.py): blocked/disabled -> 403
    ACCOUNT_BLOCKED, deleted -> 401 UNAUTHORIZED, credentials -> 401 TOKEN_INVALID.
    """
    if reason not in REVOCATION_REASONS:
        raise ValueError(reason)
    refresh = current_app.config.get("JWT_REFRESH_TOKEN_EXPIRES")
    ttl = int(refresh.total_seconds()) if refresh else 30 * 24 * 3600
    current_app.extensions["token_blocklist"].revoke_account(_account_key(account_type, account_id), time.time(),
                                                            ttl, reason)
