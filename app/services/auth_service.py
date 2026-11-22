"""Authentication: password check, purpose-bound OTPs, token issuing (Part 3 domain).

OTP keys: `login:{account_type}:{id}` and `reset:{account_type}:{id}`; TTL from
config `OTP_EXPIRY_SECONDS`; max MAX_OTP_ATTEMPTS verifications, then the OTP is invalidated.
OTPs are never returned in any response or logged.
"""
import hashlib
import hmac
import secrets
import sqlite3

from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token
from werkzeug.security import check_password_hash

from app.errors import ApiError, ValidationError
from app.services.email_service import send_otp_email

ACCOUNT_TYPES = ("user", "admin")
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
MAX_OTP_ATTEMPTS = 5
PURPOSES = ("login", "reset", "verify")
RESEND_COOLDOWN_SECONDS = 60

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


def otp_ttl(purpose=None):
    if purpose == "verify":
        return int(current_app.config.get("EMAIL_VERIFY_OTP_EXPIRY_SECONDS", 600))
    return int(current_app.config.get("OTP_EXPIRY_SECONDS", 300))


def _hash_otp(otp):
    """Only an HMAC-SHA256 of the OTP is stored; the plain code exists only in the email."""
    secret = str(current_app.config.get("SECRET_KEY") or "").encode()
    return hmac.new(secret, str(otp).strip().encode(), hashlib.sha256).hexdigest()


def otp_key(purpose, account_type, account_id):
    return f"{purpose}:{account_type}:{account_id}"


def generate_otp():
    return f"{secrets.randbelow(10 ** 6):06d}"


def issue_otp(purpose, account_type, account_id, email):
    """Store a fresh OTP and email it. Returns True if the email was handed to the provider."""
    otp = generate_otp()
    _store().set(otp_key(purpose, account_type, account_id), _hash_otp(otp), ttl_seconds=otp_ttl(purpose))
    try:
        sent = send_otp_email(to_email=email, otp=otp, purpose=purpose)
        if not sent:
            current_app.logger.error("OTP email not accepted by provider (purpose=%s)", purpose)
        return sent
    except Exception:
        current_app.logger.exception("OTP email delivery failed (purpose=%s)", purpose)
        return False


def check_otp(purpose, account_type, account_id, candidate):
    """Verify and consume an OTP; raises 400/429 on failure. Invalidated after MAX_OTP_ATTEMPTS."""
    store, key = _store(), otp_key(purpose, account_type, account_id)
    if not store.exists(key):
        raise ValidationError("Verification code expired or not requested",
                              fields={"otp": "request a new code"})
    attempts = store.increment_attempts(key, ttl_seconds=otp_ttl(purpose))
    if attempts > MAX_OTP_ATTEMPTS:
        store.invalidate(key)
        raise ApiError("Too many incorrect attempts; request a new code", 429, "RATE_LIMITED")
    if store.verify_and_consume(key, _hash_otp(candidate)):
        return
    if attempts >= MAX_OTP_ATTEMPTS:
        store.invalidate(key)
        raise ApiError("Too many incorrect attempts; request a new code", 429, "RATE_LIMITED")
    raise ValidationError("Invalid verification code",
                          fields={"otp": f"incorrect; {MAX_OTP_ATTEMPTS - attempts} attempt(s) left"})


def enforce_resend_cooldown(purpose, account_type, account_id):
    """429 if a code was sent less than RESEND_COOLDOWN_SECONDS ago; otherwise start a new cooldown."""
    key = "cooldown:" + otp_key(purpose, account_type, account_id)
    if _store().exists(key):
        raise ApiError(f"Please wait {RESEND_COOLDOWN_SECONDS} seconds before requesting a new code", 429,
                       "RATE_LIMITED", headers={"Retry-After": str(RESEND_COOLDOWN_SECONDS)})
    _store().set(key, "1", ttl_seconds=RESEND_COOLDOWN_SECONDS)


def clear_resend_cooldown(purpose, account_type, account_id):
    _store().invalidate("cooldown:" + otp_key(purpose, account_type, account_id))


def send_verification_otp(account_type, account_id, email):
    """Email a signup verification code; raises 502 EMAIL_DELIVERY_FAILED instead of failing silently."""
    if not issue_otp("verify", account_type, account_id, email):
        raise ApiError("Could not send the verification email; please try again shortly", 502,
                       "EMAIL_DELIVERY_FAILED")


def mark_email_verified(conn, account_type, account_id):
    table, id_col = _TABLES[account_type]
    conn.execute(f"UPDATE {table} SET is_email_verified = 1 WHERE {id_col} = ?", (account_id,))


def ensure_email_verified(row):
    if "is_email_verified" in row.keys() and row["is_email_verified"] is not None             and not _truthy(row["is_email_verified"]):
        raise ApiError("Email is not verified. Enter the code sent to your email.", 403, "EMAIL_NOT_VERIFIED")


# ------------------------------------------------------------------ Google Sign-In
def verify_google_id_token(raw_token):
    """Verified Google ID-token claims {sub, email, name}; any failure -> 401 (details never exposed)."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    client_id = current_app.config.get("GOOGLE_CLIENT_ID")
    if not client_id:
        current_app.logger.error("Google sign-in requested but GOOGLE_CLIENT_ID is not configured")
        raise ApiError("Google sign-in is not available", 503, "INTERNAL_ERROR")
    try:
        claims = google_id_token.verify_oauth2_token(raw_token, google_requests.Request(), client_id)
    except Exception as exc:
        current_app.logger.warning("Google ID token rejected (%s)", type(exc).__name__)
        raise ApiError("Invalid Google sign-in token", 401, "UNAUTHORIZED")
    if claims.get("iss") not in GOOGLE_ISSUERS or not claims.get("sub") or not claims.get("email"):
        raise ApiError("Invalid Google sign-in token", 401, "UNAUTHORIZED")
    if claims.get("email_verified") is not True:
        raise ApiError("Google account email is not verified", 401, "UNAUTHORIZED")
    return {"sub": str(claims["sub"]), "email": str(claims["email"]).lower(), "name": claims.get("name") or ""}


def find_account_by_google_sub(conn, account_type, sub):
    table, _ = _TABLES[account_type]
    return conn.execute(f"SELECT * FROM {table} WHERE google_sub = ?", (sub,)).fetchone()


def link_google(conn, account_type, account_id, sub):
    """Attach a Google identity to an account that has none yet. 409 GOOGLE_ACCOUNT_MISMATCH otherwise."""
    table, id_col = _TABLES[account_type]
    try:
        cur = conn.execute(
            f"""UPDATE {table} SET google_sub = ?,
                   auth_provider = CASE WHEN COALESCE(password, '') = '' THEN 'google' ELSE 'password+google' END,
                   is_email_verified = 1
               WHERE {id_col} = ? AND google_sub IS NULL""", (sub, account_id))
    except sqlite3.IntegrityError:
        cur = None
    if cur is None or cur.rowcount == 0:
        raise ApiError("This account is linked to a different Google account", 409, "GOOGLE_ACCOUNT_MISMATCH")


def google_linked(row):
    return "google_sub" in row.keys() and bool(row["google_sub"])


def reject_google_email_change(v, row):
    """Validator rule: a Google-linked account keeps the email Google verified."""
    new_email = v.cleaned.get("email")
    if new_email and google_linked(row) and new_email.lower() != (row["email"] or "").lower():
        v.error("email", "cannot be changed on a Google-linked account")


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
