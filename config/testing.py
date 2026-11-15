import os
from config.base import BaseConfig

class TestingConfig(BaseConfig):
    DEBUG = False
    TESTING = True
    ENABLE_DOCS = True
    DB_BACKUP_ON_MIGRATE = False
    ADMIN_SIGNUP_CODE = ""
    ADMIN_SIGNUP_RATE_LIMIT = 1000  # tests lower it explicitly when checking 429

    SECRET_KEY = "test-secret-key-testing-only"
    JWT_SECRET_KEY = "test-jwt-secret-key-testing-only"
    DATABASE_NAME = os.getenv("TEST_DATABASE_NAME", "test_medical_shop.db")

    EMAIL_PROVIDER = "dev"
    OTP_STORE_PROVIDER = "dev"

    SMTP_HOST = "localhost"
    SMTP_PORT = 1025
    MAIL_DEFAULT_SENDER = "noreply@example.com"
