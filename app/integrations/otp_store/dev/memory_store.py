import hmac
import threading
import time

from app.integrations.otp_store.base import OtpStore


class MemoryOtpStore(OtpStore):
    """Thread-safe in-memory OTP store for development and testing (per process)."""

    def __init__(self):
        self._store = {}
        self._attempts = {}
        self._lock = threading.Lock()

    def _live(self, key):
        record = self._store.get(key)
        if record and time.time() > record["expiry"]:
            self._store.pop(key, None)
            self._attempts.pop(key, None)
            return None
        return record

    def set(self, key: str, otp: str, ttl_seconds: int = 300) -> None:
        with self._lock:
            self._store[key] = {"otp": str(otp), "expiry": time.time() + ttl_seconds}
            self._attempts.pop(key, None)

    def verify_and_consume(self, key: str, candidate: str) -> bool:
        with self._lock:
            record = self._live(key)
            if not record:
                return False
            if hmac.compare_digest(str(record["otp"]), str(candidate)):
                self._store.pop(key, None)
                self._attempts.pop(key, None)
                return True
            return False

    def exists(self, key: str) -> bool:
        with self._lock:
            return self._live(key) is not None

    def increment_attempts(self, key: str, ttl_seconds: int = 300) -> int:
        with self._lock:
            self._attempts[key] = self._attempts.get(key, 0) + 1
            return self._attempts[key]

    def invalidate(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
            self._attempts.pop(key, None)
