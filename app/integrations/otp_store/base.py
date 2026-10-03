from abc import ABC, abstractmethod

class OtpStore(ABC):
    """Abstract interface for OTP storage backends."""

    @abstractmethod
    def set(self, key: str, otp: str, ttl_seconds: int = 300) -> None:
        """Store an OTP associated with a unique key and expiration TTL."""
        pass

    @abstractmethod
    def verify_and_consume(self, key: str, candidate: str) -> bool:
        """Verify the candidate OTP against stored record and consume it if valid."""
        pass
