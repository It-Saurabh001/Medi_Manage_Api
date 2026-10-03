from flask import has_app_context
from app.extensions import get_current_otp_store
from app.integrations.otp_store.factory import get_otp_store

_default_fallback_store = None

def _get_active_store():
    global _default_fallback_store
    if has_app_context():
        try:
            return get_current_otp_store()
        except (KeyError, RuntimeError):
            pass
    if _default_fallback_store is None:
        _default_fallback_store = get_otp_store({"OTP_STORE_PROVIDER": "dev", "DEBUG": True})
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
        ttl = int(value.get("expiry", 0) - value.get("__time", 0)) if isinstance(value, dict) and "__time" in value else 300
        store_otp(self._full_key(key), otp, ttl_seconds=ttl)

    def __getitem__(self, key):
        store = _get_active_store()
        full_k = self._full_key(key)
        if hasattr(store, "_store") and full_k in store._store:
            return store._store[full_k]
        elif hasattr(store, "_client"):
            val = store._client.get(f"otp:{full_k}")
            if val:
                return {
                    "otp": val.decode("utf-8") if isinstance(val, bytes) else str(val),
                    "expiry": float("inf")
                }
        return {"otp": "", "expiry": 0}

    def __contains__(self, key):
        store = _get_active_store()
        full_k = self._full_key(key)
        if hasattr(store, "_store"):
            return full_k in store._store
        elif hasattr(store, "_client"):
            return bool(store._client.exists(f"otp:{full_k}"))
        return False

    def __delitem__(self, key):
        store = _get_active_store()
        full_k = self._full_key(key)
        if hasattr(store, "_store"):
            store._store.pop(full_k, None)
        elif hasattr(store, "_client"):
            store._client.delete(f"otp:{full_k}")

otp_store = OtpDictProxy("admin")
user_otp_store = OtpDictProxy("user")
