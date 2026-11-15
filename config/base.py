import os
from datetime import timedelta


def _env_bool(name, default):
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name, default):
    value = os.getenv(name)
    return int(value) if value not in (None, "") else default


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    DATABASE_NAME = os.getenv("DATABASE_NAME", "My_Medical_Shope.db")
    # Take a `<db>.bak-<timestamp>` copy before a migration changes an existing DB file
    DB_BACKUP_ON_MIGRATE = _env_bool("DB_BACKUP_ON_MIGRATE", True)

    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

    OTP_EXPIRY_SECONDS = _env_int("OTP_EXPIRY_SECONDS", 300)

    # --- API / client contract ---
    API_PREFIX = os.getenv("API_PREFIX", "/api/v1")
    ENABLE_DOCS = _env_bool("ENABLE_DOCS", False)
    MIN_APP_VERSION = os.getenv("MIN_APP_VERSION", "")  # '' = check disabled
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "")  # '' = CORS disabled
    TRUSTED_PROXY_COUNT = _env_int("TRUSTED_PROXY_COUNT", 0)

    # --- Uploads ---
    MAX_UPLOAD_MB = _env_int("MAX_UPLOAD_MB", 5)
    # Whole-request cap (multipart overhead + form fields on top of one file)
    MAX_CONTENT_LENGTH = _env_int("MAX_CONTENT_LENGTH", (MAX_UPLOAD_MB + 1) * 1024 * 1024)
    ALLOWED_UPLOAD_MIME = tuple(
        m.strip().lower()
        for m in os.getenv(
            "ALLOWED_UPLOAD_MIME", "image/jpeg,image/png,image/webp,application/pdf"
        ).split(",")
        if m.strip()
    )

    # --- Admin signup (POST /admins/register) ---
    # When set, signup must send a matching `signup_code`. Strongly recommended in production.
    ADMIN_SIGNUP_CODE = os.getenv("ADMIN_SIGNUP_CODE", "")
    # Per-client-IP fixed window; 0 disables the limit.
    ADMIN_SIGNUP_RATE_LIMIT = _env_int("ADMIN_SIGNUP_RATE_LIMIT", 10)
    ADMIN_SIGNUP_RATE_WINDOW_SECONDS = _env_int("ADMIN_SIGNUP_RATE_WINDOW_SECONDS", 3600)

    # --- Domain ---
    IDEMPOTENCY_TTL_HOURS = _env_int("IDEMPOTENCY_TTL_HOURS", 24)
    NEAR_EXPIRY_DAYS = _env_int("NEAR_EXPIRY_DAYS", 90)
