import os
from config.base import BaseConfig

class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TESTING = False

    # Fallback JWT key allowed ONLY in development
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-fallback-secret-key-123")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-fallback-secret-key-456")

    EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "dev")
    OTP_STORE_PROVIDER = os.getenv("OTP_STORE_PROVIDER", "dev")

    SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "noreply@example.com")
