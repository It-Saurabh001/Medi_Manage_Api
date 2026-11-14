import redis

from app.integrations.otp_store.base import OtpStore


class RedisOtpStore(OtpStore):
    """Production Redis-backed OTP store with TTL, attempt counter and atomic verification."""

    # Atomic compare-and-delete (also clears the attempt counter on success)
    _VERIFY_AND_CONSUME_LUA = """
    local val = redis.call('GET', KEYS[1])
    if val and val == ARGV[1] then
        redis.call('DEL', KEYS[1], KEYS[2])
        return 1
    end
    return 0
    """

    def __init__(self, redis_url: str):
        if not redis_url:
            raise ValueError("REDIS_URL is required for RedisOtpStore")
        self._client = redis.from_url(redis_url)
        self._script = self._client.register_script(self._VERIFY_AND_CONSUME_LUA)

    @staticmethod
    def _keys(key):
        return f"otp:{key}", f"otp_attempts:{key}"

    def set(self, key: str, otp: str, ttl_seconds: int = 300) -> None:
        otp_key, attempts_key = self._keys(key)
        pipe = self._client.pipeline()
        pipe.setex(otp_key, ttl_seconds, str(otp))
        pipe.delete(attempts_key)
        pipe.execute()

    def verify_and_consume(self, key: str, candidate: str) -> bool:
        return bool(self._script(keys=list(self._keys(key)), args=[str(candidate)]))

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(self._keys(key)[0]))

    def increment_attempts(self, key: str, ttl_seconds: int = 300) -> int:
        attempts_key = self._keys(key)[1]
        pipe = self._client.pipeline()
        pipe.incr(attempts_key)
        pipe.expire(attempts_key, ttl_seconds)
        count, _ = pipe.execute()
        return int(count)

    def invalidate(self, key: str) -> None:
        self._client.delete(*self._keys(key))
