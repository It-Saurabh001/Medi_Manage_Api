"""Thin accessors for the configured OtpStore (legacy OtpDictProxy removed in Part 3)."""
from flask import current_app


def get_store():
    return current_app.extensions["otp_store"]


def store_otp(key: str, otp: str, ttl_seconds: int) -> None:
    get_store().set(key, otp, ttl_seconds=ttl_seconds)


def verify_and_consume_otp(key: str, candidate: str) -> bool:
    return get_store().verify_and_consume(key, candidate)
