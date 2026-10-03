import os
from config.base import BaseConfig

class TestingConfig(BaseConfig):
    DEBUG = False
    TESTING = True

    SECRET_KEY = "test-secret-key-testing-only"
    JWT_SECRET_KEY = "test-jwt-secret-key-testing-only"
    DATABASE_NAME = ":memory:"

    EMAIL_PROVIDER = "dev"
    OTP_STORE_PROVIDER = "dev"

    SMTP_HOST = "localhost"
    SMTP_PORT = 1025
    MAIL_DEFAULT_SENDER = "noreply@example.com"
