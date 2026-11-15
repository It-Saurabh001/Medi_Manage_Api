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


def enforce_rate_limit(bucket, limit, window_seconds):
    """Raise 429 RATE_LIMITED (with Retry-After) once `limit` hits per window are exceeded for this client."""
    if not limit or limit <= 0:
        return
    limiter = current_app.extensions["rate_limiter"]
    allowed, retry_after = limiter.hit(f"{bucket}:{request.remote_addr or 'unknown'}", int(limit), int(window_seconds))
    if not allowed:
        raise ApiError("Too many attempts; try again later", 429, "RATE_LIMITED",
                       headers={"Retry-After": str(retry_after)})
