import os
from config.base import BaseConfig, _env_bool

class ProductionConfig(BaseConfig):
    DEBUG = False
    TESTING = False
    ENABLE_DOCS = _env_bool("ENABLE_DOCS", False)
    PREFERRED_URL_SCHEME = "https"

    EMAIL_PROVIDER = "prod"
    OTP_STORE_PROVIDER = "prod"

    SMTP_HOST = os.getenv("SMTP_HOST")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587")) if os.getenv("SMTP_PORT") else None
    SMTP_USER = os.getenv("SMTP_USER")
    SMTP_PASS = os.getenv("SMTP_PASS")
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER")

    REDIS_URL = os.getenv("REDIS_URL")

    @classmethod
    def validate(cls):
        # Refresh values from environment at validation time
        cls.SECRET_KEY = os.getenv("SECRET_KEY", cls.SECRET_KEY)
        cls.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", cls.JWT_SECRET_KEY)
        cls.CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", cls.CLOUDINARY_CLOUD_NAME)
        cls.CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", cls.CLOUDINARY_API_KEY)
        cls.CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", cls.CLOUDINARY_API_SECRET)
        cls.SMTP_HOST = os.getenv("SMTP_HOST", cls.SMTP_HOST)
        cls.SMTP_PORT = int(os.getenv("SMTP_PORT")) if os.getenv("SMTP_PORT") else cls.SMTP_PORT
        cls.SMTP_USER = os.getenv("SMTP_USER", cls.SMTP_USER)
        cls.SMTP_PASS = os.getenv("SMTP_PASS", cls.SMTP_PASS)
        cls.SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
        cls.MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", cls.MAIL_DEFAULT_SENDER)
        cls.REDIS_URL = os.getenv("REDIS_URL", cls.REDIS_URL)

        missing = []
        required_vars = [
            ("SECRET_KEY", cls.SECRET_KEY),
            ("JWT_SECRET_KEY", cls.JWT_SECRET_KEY),
            ("CLOUDINARY_CLOUD_NAME", cls.CLOUDINARY_CLOUD_NAME),
            ("CLOUDINARY_API_KEY", cls.CLOUDINARY_API_KEY),
            ("CLOUDINARY_API_SECRET", cls.CLOUDINARY_API_SECRET),
            ("SMTP_HOST", cls.SMTP_HOST),
            ("SMTP_PORT", cls.SMTP_PORT),
            ("SMTP_USER", cls.SMTP_USER),
            ("SMTP_PASS", cls.SMTP_PASS),
            ("MAIL_DEFAULT_SENDER", cls.MAIL_DEFAULT_SENDER),
            ("REDIS_URL", cls.REDIS_URL),
        ]
        for name, value in required_vars:
            if not value:
                missing.append(name)

        # Check for dev provider override attempts
        env_email_provider = os.getenv("EMAIL_PROVIDER", "prod")
        env_otp_provider = os.getenv("OTP_STORE_PROVIDER", "prod")
        if env_email_provider != "prod":
            missing.append(f"EMAIL_PROVIDER (cannot be '{env_email_provider}' in production; must be 'prod')")
        if env_otp_provider != "prod":
            missing.append(f"OTP_STORE_PROVIDER (cannot be '{env_otp_provider}' in production; must be 'prod')")

        if missing:
            raise ValueError(
                f"Production configuration validation failed. Missing or invalid required variables: {', '.join(missing)}"
            )
