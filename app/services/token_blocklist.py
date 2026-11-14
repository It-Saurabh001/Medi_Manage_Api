"""JWT revocation list: Redis in production (OTP_STORE_PROVIDER == 'prod'), in-memory otherwise."""
import threading
import time

from flask import current_app

from app.extensions import jwt


class MemoryTokenBlocklist:
    def __init__(self):
        self._items = {}
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


class RedisTokenBlocklist:
    def __init__(self, redis_url):
        import redis

        self._client = redis.from_url(redis_url)

    def add(self, jti, ttl_seconds):
        self._client.setex(f"jwt_blocklist:{jti}", max(1, int(ttl_seconds)), "1")

    def contains(self, jti):
        return bool(self._client.exists(f"jwt_blocklist:{jti}"))


def init_token_blocklist(app):
    """Create the app's blocklist and register flask-jwt-extended's `token_in_blocklist_loader`."""
    if str(app.config.get("OTP_STORE_PROVIDER", "dev")).lower() == "prod":
        app.extensions["token_blocklist"] = RedisTokenBlocklist(app.config.get("REDIS_URL"))
    else:
        app.extensions["token_blocklist"] = MemoryTokenBlocklist()

    @jwt.token_in_blocklist_loader
    def _is_revoked(jwt_header, jwt_payload):
        return current_app.extensions["token_blocklist"].contains(jwt_payload.get("jti"))


def revoke_token(payload):
    """Revoke a decoded JWT payload until its natural expiry."""
    exp = payload.get("exp") or (time.time() + 3600)
    current_app.extensions["token_blocklist"].add(payload["jti"], exp - time.time())
