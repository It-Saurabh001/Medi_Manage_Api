import time
import threading
from app.integrations.otp_store.base import OtpStore

class MemoryOtpStore(OtpStore):
    """Thread-safe in-memory OTP store for development and testing."""

    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()

    def set(self, key: str, otp: str, ttl_seconds: int = 300) -> None:
        expiry = time.time() + ttl_seconds
        with self._lock:
            self._store[key] = {
                "otp": str(otp),
                "expiry": expiry
            }

    def verify_and_consume(self, key: str, candidate: str) -> bool:
        with self._lock:
            record = self._store.get(key)
            if not record:
                return False

            if time.time() > record["expiry"]:
                del self._store[key]
                return False

            if str(record["otp"]) == str(candidate):
                del self._store[key]
                return True

            return False
