import os
from config.base import BaseConfig

class TestingConfig(BaseConfig):
    FLASK_ENV = "testing"
    DEBUG = False
    TESTING = True
    ENABLE_DOCS = True
    DB_BACKUP_ON_MIGRATE = False
    ADMIN_SIGNUP_CODE = ""
    ADMIN_SIGNUP_RATE_LIMIT = 1000  # tests lower it explicitly when checking 429
    # Limits stay active (code paths run) but high; security tests lower them explicitly.
    AUTH_IP_RATE_LIMIT = 1000
    AUTH_ACCOUNT_RATE_LIMIT = 1000
    SIGNUP_RATE_LIMIT = 1000
    GLOBAL_RATE_LIMIT = 0
    # Opt-in switches stay at their (off) defaults; tests/test_security_hardening.py turns each one on.

    SECRET_KEY = "test-secret-key-testing-only"
    JWT_SECRET_KEY = "test-jwt-secret-key-testing-only"
    DATABASE_NAME = os.getenv("TEST_DATABASE_NAME", "test_medical_shop.db")
    # Tests must never reach a real hosted database
    TURSO_DATABASE_URL = ""
    TURSO_AUTH_TOKEN = ""

    EMAIL_PROVIDER = "dev"
    OTP_STORE_PROVIDER = "dev"

    SMTP_HOST = "localhost"
    SMTP_PORT = 1025
    MAIL_DEFAULT_SENDER = "noreply@example.com"
