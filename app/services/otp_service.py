from flask import current_app, has_app_context
from app.extensions import get_current_otp_store
from app.integrations.otp_store.dev.memory_store import MemoryOtpStore

# Shared fallback memory store for non-app-context usage
_default_fallback_store = MemoryOtpStore()

def _get_active_store():
    if has_app_context():
        try:
            return get_current_otp_store()
        except (KeyError, RuntimeError):
            pass
    return _default_fallback_store

def store_otp(key: str, otp: str, ttl_seconds: int = 300) -> None:
    """Store an OTP for a given key using the configured OTP store provider."""
    store = _get_active_store()
    store.set(key, otp, ttl_seconds=ttl_seconds)

def verify_and_consume_otp(key: str, candidate: str) -> bool:
    """Verify and consume an OTP using the configured OTP store provider."""
    store = _get_active_store()
    return store.verify_and_consume(key, candidate)

class OtpDictProxy:
    """Dictionary proxy for backward compatibility with legacy routes."""

    def __init__(self, prefix=""):
        self.prefix = prefix

    def _full_key(self, key):
        return f"{self.prefix}:{key}" if self.prefix else str(key)

    def __setitem__(self, key, value):
        otp = value.get("otp") if isinstance(value, dict) else str(value)
        store_otp(self._full_key(key), otp)

    def __getitem__(self, key):
        # Emulates legacy lookup by returning a dict with candidate matching
        return {"otp": "", "expiry": float("inf"), "__key": self._full_key(key)}

    def __contains__(self, key):
        store = _get_active_store()
        if hasattr(store, "_store"):
            return self._full_key(key) in store._store
        return True

    def __delitem__(self, key):
        store = _get_active_store()
        full_k = self._full_key(key)
        if hasattr(store, "_store"):
            store._store.pop(full_k, None)
        elif hasattr(store, "_client"):
            store._client.delete(f"otp:{full_k}")

# Backward compatible singleton proxies delegating to the active provider
otp_store = OtpDictProxy("admin")
user_otp_store = OtpDictProxy("user")
