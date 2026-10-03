import redis
from app.integrations.otp_store.base import OtpStore

class RedisOtpStore(OtpStore):
    """Production Redis-backed OTP store with TTL and atomic verification."""

    # Lua script for atomic get-and-delete if value matches
    _VERIFY_AND_CONSUME_LUA = """
    local key = KEYS[1]
    local candidate = ARGV[1]
    local val = redis.call('GET', key)
    if val == candidate then
        redis.call('DEL', key)
        return 1
    else
        return 0
    end
    """

    def __init__(self, redis_url: str):
        if not redis_url:
            raise ValueError("REDIS_URL is required for RedisOtpStore")
        self._client = redis.from_url(redis_url)
        self._script = self._client.register_script(self._VERIFY_AND_CONSUME_LUA)

    def set(self, key: str, otp: str, ttl_seconds: int = 300) -> None:
        redis_key = f"otp:{key}"
        self._client.setex(redis_key, ttl_seconds, str(otp))

    def verify_and_consume(self, key: str, candidate: str) -> bool:
        redis_key = f"otp:{key}"
        result = self._script(keys=[redis_key], args=[str(candidate)])
        return bool(result)
