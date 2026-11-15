"""Authentication: password check, purpose-bound OTPs, token issuing (Part 3 domain).

OTP keys: `login:{account_type}:{id}` and `reset:{account_type}:{id}`; TTL from
config `OTP_EXPIRY_SECONDS`; max MAX_OTP_ATTEMPTS verifications, then the OTP is invalidated.
OTPs are never returned in any response or logged.
"""
import secrets

from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from werkzeug.security import check_password_hash

from app.errors import ApiError, ValidationError
from app.services.email_service import send_otp_email

ACCOUNT_TYPES = ("user", "admin")
MAX_OTP_ATTEMPTS = 5
PURPOSES = ("login", "reset")

_TABLES = {
    "user": ("Users", "user_id"),
    "admin": ("Admin", "admin_id"),
}


def _truthy(value):
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


# ------------------------------------------------------------------ accounts
def find_account_by_email(conn, account_type, email):
    table, _ = _TABLES[account_type]
    return conn.execute(f"SELECT * FROM {table} WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()


def fetch_account(conn, account_type, account_id):
    table, id_col = _TABLES[account_type]
    return conn.execute(f"SELECT * FROM {table} WHERE {id_col} = ?", (account_id,)).fetchone()


def account_id_of(account_type, row):
    return row[_TABLES[account_type][1]]


def resolve_role(account_type, row):
    """Effective role from the DB row, or None if the account is deleted/disabled.

    Users-table rows are always role `user` (a legacy `role='admin'` there came from the
    removed `Admin:` header escalation and is not honoured).
    """
    stored = (row["role"] or "").strip().lower()
    if account_type == "admin":
        return "admin" if stored in ("", "admin") else None
    return None if stored in ("deleted", "disabled") else "user"


def ensure_account_active(account_type, row):
    """Raise for deleted/disabled (401), blocked (403 ACCOUNT_BLOCKED) or unapproved users/admins (403)."""
    role = resolve_role(account_type, row)
    if role is None:
        if account_type == "admin" and (row["role"] or "").lower() == "disabled":
            raise ApiError("Account is disabled", 403, "ACCOUNT_BLOCKED")
        raise ApiError("Account no longer exists", 401, "UNAUTHORIZED")
    if account_type == "admin" and "is_approved" in row.keys() and row["is_approved"] is not None             and not _truthy(row["is_approved"]):
        raise ApiError("Account is not approved yet", 403, "ACCOUNT_NOT_APPROVED")
    if account_type == "user":
        if _truthy(row["block"]):
            raise ApiError("Account is blocked", 403, "ACCOUNT_BLOCKED")
        if not _truthy(row["isApproved"]):
            raise ApiError("Account is not approved yet", 403, "ACCOUNT_NOT_APPROVED")
    return role


def authenticate(conn, account_type, email, password):
    """Row on valid credentials, else None (same answer for unknown email and bad password)."""
    row = find_account_by_email(conn, account_type, email)
    if row is None or not row["password"]:
        return None
    try:
        ok = check_password_hash(row["password"], password)
    except (ValueError, TypeError):
        ok = False
    return row if ok else None


def verify_password(row, password):
    try:
        return bool(row["password"]) and check_password_hash(row["password"], password)
    except (ValueError, TypeError):
        return False


# ------------------------------------------------------------------ OTP
def _store():
    return current_app.extensions["otp_store"]


def otp_ttl():
    return int(current_app.config.get("OTP_EXPIRY_SECONDS", 300))


def otp_key(purpose, account_type, account_id):
    return f"{purpose}:{account_type}:{account_id}"


def generate_otp():
    return f"{secrets.randbelow(10 ** 6):06d}"


def issue_otp(purpose, account_type, account_id, email):
    """Store a fresh OTP and email it. Returns True if the email was handed to the provider."""
    otp = generate_otp()
    _store().set(otp_key(purpose, account_type, account_id), otp, ttl_seconds=otp_ttl())
    try:
        return send_otp_email(to_email=email, otp=otp, purpose=purpose)
    except Exception:
        current_app.logger.exception("OTP email delivery failed (purpose=%s)", purpose)
        return False


def check_otp(purpose, account_type, account_id, candidate):
    """Verify and consume an OTP; raises 400/429 on failure. Invalidated after MAX_OTP_ATTEMPTS."""
    store, key = _store(), otp_key(purpose, account_type, account_id)
    if not store.exists(key):
        raise ValidationError("Verification code expired or not requested",
                              fields={"otp": "request a new code"})
    attempts = store.increment_attempts(key, ttl_seconds=otp_ttl())
    if attempts > MAX_OTP_ATTEMPTS:
        store.invalidate(key)
        raise ApiError("Too many incorrect attempts; request a new code", 429, "RATE_LIMITED")
    if store.verify_and_consume(key, str(candidate).strip()):
        return
    if attempts >= MAX_OTP_ATTEMPTS:
        store.invalidate(key)
        raise ApiError("Too many incorrect attempts; request a new code", 429, "RATE_LIMITED")
    raise ValidationError("Invalid verification code",
                          fields={"otp": f"incorrect; {MAX_OTP_ATTEMPTS - attempts} attempt(s) left"})


# ------------------------------------------------------------------ tokens
def issue_tokens(account_type, account_id, role):
    claims = {"role": role, "account_type": account_type}
    expires = current_app.config.get("JWT_ACCESS_TOKEN_EXPIRES")
    return {
        "access_token": create_access_token(identity=account_id, additional_claims=claims),
        "refresh_token": create_refresh_token(identity=account_id, additional_claims=claims),
        "token_type": "Bearer",
        "expires_in": int(expires.total_seconds()) if expires else 3600,
        "role": role,
        "account_type": account_type,
        "account_id": account_id,
    }


def account_type_from_claims(claims):
    account_type = claims.get("account_type")
    if account_type in ACCOUNT_TYPES:
        return account_type
    return "admin" if claims.get("role") == "admin" else "user"
