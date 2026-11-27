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
    # Hosted libSQL (Turso). When TURSO_DATABASE_URL is set it is used instead of the local file.
    TURSO_DATABASE_URL = (os.getenv("TURSO_DATABASE_URL") or "").strip()
    TURSO_AUTH_TOKEN = (os.getenv("TURSO_AUTH_TOKEN") or "").strip()
    TURSO_TIMEOUT_SECONDS = _env_int("TURSO_TIMEOUT_SECONDS", 15)
    # Take a `<db>.bak-<timestamp>` copy before a migration changes an existing DB file
    DB_BACKUP_ON_MIGRATE = _env_bool("DB_BACKUP_ON_MIGRATE", True)

    CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
    CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
    CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

    OTP_EXPIRY_SECONDS = _env_int("OTP_EXPIRY_SECONDS", 300)
    EMAIL_VERIFY_OTP_EXPIRY_SECONDS = _env_int("EMAIL_VERIFY_OTP_EXPIRY_SECONDS", 600)
    # Fail closed: an unset FLASK_ENV means production (see config/__init__.py and wsgi.py)
    FLASK_ENV = (os.getenv("FLASK_ENV") or "production").strip().lower()
    EMAIL_PROVIDER = (os.getenv("EMAIL_PROVIDER") or "dev").strip().lower()
    EMAIL_BACKEND = (os.getenv("EMAIL_BACKEND") or "smtp").strip().lower()
    EMAIL_API_PROVIDER = (os.getenv("EMAIL_API_PROVIDER") or "brevo").strip().lower()
    EMAIL_API_KEY = (os.getenv("EMAIL_API_KEY") or "").strip() or None

    # --- Google Sign-In (POST /auth/google); Web OAuth client ID used as the ID-token audience ---
    GOOGLE_CLIENT_ID = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    GOOGLE_LOGIN_RATE_LIMIT = _env_int("GOOGLE_LOGIN_RATE_LIMIT", 30)
    GOOGLE_LOGIN_RATE_WINDOW_SECONDS = _env_int("GOOGLE_LOGIN_RATE_WINDOW_SECONDS", 600)

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

    # When false, POST /admins/register answers 404 (admins are then created by the owner or bootstrap only).
    ADMIN_SIGNUP_ENABLED = _env_bool("ADMIN_SIGNUP_ENABLED", True)
    # Opt-in: creating, approving, disabling and deleting other admins is reserved for the owner admin.
    # Off by default so existing multi-admin setups keep working; recommended once the app supports it.
    ADMIN_MANAGEMENT_OWNER_ONLY = _env_bool("ADMIN_MANAGEMENT_OWNER_ONLY", False)

    # --- Auth abuse protection (fixed windows; 0 disables a limit) ---
    # Per client IP, per auth endpoint (login, verify-otp, resend-otp, password-reset/*)
    AUTH_IP_RATE_LIMIT = _env_int("AUTH_IP_RATE_LIMIT", 30)
    AUTH_IP_RATE_WINDOW_SECONDS = _env_int("AUTH_IP_RATE_WINDOW_SECONDS", 600)
    # Per target email/account, per auth endpoint (stops distributed guessing against one account)
    AUTH_ACCOUNT_RATE_LIMIT = _env_int("AUTH_ACCOUNT_RATE_LIMIT", 10)
    AUTH_ACCOUNT_RATE_WINDOW_SECONDS = _env_int("AUTH_ACCOUNT_RATE_WINDOW_SECONDS", 900)
    # OTP verification attempts per account and purpose; NOT reset when a new code is issued
    OTP_VERIFY_BUDGET = _env_int("OTP_VERIFY_BUDGET", 10)
    OTP_VERIFY_BUDGET_WINDOW_SECONDS = _env_int("OTP_VERIFY_BUDGET_WINDOW_SECONDS", 3600)
    # Public customer signup (POST /users), per client IP
    SIGNUP_RATE_LIMIT = _env_int("SIGNUP_RATE_LIMIT", 10)
    SIGNUP_RATE_WINDOW_SECONDS = _env_int("SIGNUP_RATE_WINDOW_SECONDS", 3600)
    # Opt-in (needs the app's signup flow to show the verify-OTP screen for customers):
    # customers must verify their email (OTP) before they can log in.
    REQUIRE_USER_EMAIL_VERIFICATION = _env_bool("REQUIRE_USER_EMAIL_VERIFICATION", False)

    # --- Prescriptions (medical data) ---
    # Opt-in: store uploads as private Cloudinary assets; prescription_url then becomes a short-lived
    # signed download URL (the app must not cache it). Strongly recommended once the app handles it.
    PRESCRIPTION_PRIVATE_STORAGE = _env_bool("PRESCRIPTION_PRIVATE_STORAGE", False)
    PRESCRIPTION_URL_TTL_SECONDS = _env_int("PRESCRIPTION_URL_TTL_SECONDS", 900)
    # Hosts a client-supplied prescription_url may point at (subdomains allowed). Empty = any host
    # (legacy behaviour). Recommended: res.cloudinary.com
    ALLOWED_PRESCRIPTION_URL_HOSTS = tuple(
        h.strip().lower() for h in os.getenv("ALLOWED_PRESCRIPTION_URL_HOSTS", "").split(",") if h.strip()
    )

    # --- Edge guard (Cloudflare-style request filtering inside the app; see README "Security") ---
    EDGE_GUARD_ENABLED = _env_bool("EDGE_GUARD_ENABLED", True)
    # Header holding the real client IP set by a trusted edge, e.g. CF-Connecting-IP behind Cloudflare.
    # Only safe together with ORIGIN_AUTH_SECRET (otherwise clients can forge it).
    CLIENT_IP_HEADER = (os.getenv("CLIENT_IP_HEADER") or "").strip()
    # Origin lock: when set, every request (except /health) must carry this secret header, which a
    # Cloudflare Transform Rule adds. Direct hits on the origin URL are rejected.
    ORIGIN_AUTH_HEADER = (os.getenv("ORIGIN_AUTH_HEADER") or "X-Origin-Auth").strip()
    ORIGIN_AUTH_SECRET = (os.getenv("ORIGIN_AUTH_SECRET") or "").strip()
    # IP access rules (comma-separated IPs or CIDRs). An allowlist, when set, admits only those IPs.
    IP_BLOCKLIST = os.getenv("IP_BLOCKLIST", "")
    IP_ALLOWLIST = os.getenv("IP_ALLOWLIST", "")
    # Global per-IP rate limit across the whole API (requests per window)
    GLOBAL_RATE_LIMIT = _env_int("GLOBAL_RATE_LIMIT", 300)
    GLOBAL_RATE_WINDOW_SECONDS = _env_int("GLOBAL_RATE_WINDOW_SECONDS", 60)
    BLOCK_SCANNER_USER_AGENTS = _env_bool("BLOCK_SCANNER_USER_AGENTS", True)
    BLOCK_EMPTY_USER_AGENT = _env_bool("BLOCK_EMPTY_USER_AGENT", False)
    MAX_URL_LENGTH = _env_int("MAX_URL_LENGTH", 2048)

    # --- Domain ---
    IDEMPOTENCY_TTL_HOURS = _env_int("IDEMPOTENCY_TTL_HOURS", 24)
    NEAR_EXPIRY_DAYS = _env_int("NEAR_EXPIRY_DAYS", 90)
