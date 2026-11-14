from abc import ABC, abstractmethod


class OtpStore(ABC):
    """Abstract interface for OTP storage backends.

    Keys are purpose-bound by the caller, e.g. `login:user:<id>` / `reset:admin:<id>`.
    """

    @abstractmethod
    def set(self, key: str, otp: str, ttl_seconds: int = 300) -> None:
        """Store an OTP for `key` with a TTL; resets the failed-attempt counter."""

    @abstractmethod
    def verify_and_consume(self, key: str, candidate: str) -> bool:
        """Atomically compare and, on match, delete the OTP (single use)."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """True if an unexpired OTP is stored for `key`."""

    @abstractmethod
    def increment_attempts(self, key: str, ttl_seconds: int = 300) -> int:
        """Increment and return the verification-attempt counter for `key`."""

    @abstractmethod
    def invalidate(self, key: str) -> None:
        """Delete the OTP and its attempt counter."""
