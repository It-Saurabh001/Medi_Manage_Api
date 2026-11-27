"""Fixed-window rate limiting for public, abuse-prone endpoints (e.g. POST /admins/register).

Backend follows OTP_STORE_PROVIDER: `dev` -> in-process memory (per worker), `prod` -> Redis
(shared across workers). Keys are `<bucket>:<client ip>`; the client IP honours ProxyFix
(TRUSTED_PROXY_COUNT).
"""
import threading
import time

from flask import current_app, request

from app.errors import ApiError


class MemoryRateLimiter:
    def __init__(self):
        self._windows = {}
        self._lock = threading.Lock()

    def hit(self, key, limit, window_seconds):
        """Count one hit. Returns (allowed, retry_after_seconds)."""
        now = time.time()
        with self._lock:
            start, count = self._windows.get(key, (now, 0))
            if now - start >= window_seconds:
                start, count = now, 0
            count += 1
            self._windows[key] = (start, count)
            return count <= limit, max(1, int(start + window_seconds - now))


class RedisRateLimiter:
    def __init__(self, redis_url):
        import redis

        if not redis_url:
            raise ValueError("REDIS_URL is required for RedisRateLimiter")
        self._client = redis.from_url(redis_url)

    def hit(self, key, limit, window_seconds):
        redis_key = f"ratelimit:{key}"
        pipe = self._client.pipeline()
        pipe.incr(redis_key)
        pipe.ttl(redis_key)
        count, ttl = pipe.execute()
        if ttl is None or int(ttl) < 0:  # first hit in this window (or a key left without expiry)
            self._client.expire(redis_key, window_seconds)
            ttl = window_seconds
        return int(count) <= limit, max(1, int(ttl))


def get_rate_limiter(config):
    if str(config.get("OTP_STORE_PROVIDER", "dev")).lower() == "prod":
        return RedisRateLimiter(config.get("REDIS_URL"))
    return MemoryRateLimiter()


def client_ip():
    """Best-known client IP.

    CLIENT_IP_HEADER (e.g. CF-Connecting-IP) is honoured only when the edge guard's origin lock
    (ORIGIN_AUTH_SECRET) is configured, so the header cannot be forged by clients hitting the origin
    directly. Otherwise request.remote_addr, which honours ProxyFix (TRUSTED_PROXY_COUNT).
    """
    cfg = current_app.config
    header = cfg.get("CLIENT_IP_HEADER")
    if header and cfg.get("ORIGIN_AUTH_SECRET"):
        value = (request.headers.get(header) or "").split(",")[0].strip()
        if value:
            return value
    return request.remote_addr or "unknown"


def _hash_identifier(value):
    """Rate-limit keys for emails/ids are hashed so Redis never holds raw PII."""
    import hashlib

    return hashlib.sha256(str(value).strip().lower().encode("utf-8")).hexdigest()[:32]


def hit_limit(bucket, limit, window_seconds, key=None):
    """Count one hit. Returns (allowed, retry_after). `key` defaults to the client IP."""
    if not limit or int(limit) <= 0:
        return True, 0
    limiter = current_app.extensions["rate_limiter"]
    subject = client_ip() if key is None else _hash_identifier(key)
    return limiter.hit(f"{bucket}:{subject}", int(limit), int(window_seconds))


def enforce_rate_limit(bucket, limit, window_seconds, key=None):
    """Raise 429 RATE_LIMITED (with Retry-After) once `limit` hits per window are exceeded.

    The limit applies per client IP, or per `key` (e.g. the target email) when one is given.
    """
    allowed, retry_after = hit_limit(bucket, limit, window_seconds, key=key)
    if not allowed:
        raise ApiError("Too many attempts; try again later", 429, "RATE_LIMITED",
                       headers={"Retry-After": str(retry_after)})


def enforce_auth_limits(bucket, account_key=None):
    """Standard auth-endpoint protection: per-IP limit, plus a per-account limit when the target is known."""
    cfg = current_app.config
    enforce_rate_limit(f"auth_ip:{bucket}", cfg.get("AUTH_IP_RATE_LIMIT", 30),
                       cfg.get("AUTH_IP_RATE_WINDOW_SECONDS", 600))
    if account_key:
        enforce_rate_limit(f"auth_acct:{bucket}", cfg.get("AUTH_ACCOUNT_RATE_LIMIT", 10),
                           cfg.get("AUTH_ACCOUNT_RATE_WINDOW_SECONDS", 900), key=account_key)
