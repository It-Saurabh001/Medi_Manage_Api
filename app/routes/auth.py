"""Authentication endpoints under API_PREFIX (Part 3).

Replaces /admin/login, /admin/verifyOtp, /admin/refreshToken, /admin/requestAdminPasswordReset,
/admin/resetAdminPasswordWithOtp, /user/login, /user/verifyUserOtp, /user/requestUserPasswordReset
and /user/resetUserPasswordWithOtp.
"""
from flask import current_app
from flask_jwt_extended import decode_token, get_jwt, get_jwt_identity, jwt_required

from app.db import db_connection, get_db
from app.errors import ApiError, ValidationError
from app.services import account_service as acc
from app.services import auth_service as auth
from app.services.audit_service import write_audit
from app.services.token_blocklist import revoke_token
from app.utils.api_blueprint import ApiBlueprint
from app.utils.decorators import role_required
from app.utils.responses import api_response
from app.utils.validators import Validator, request_payload

auth_bp = ApiBlueprint("auth", __name__)

RESET_MESSAGE = "If an account exists for this email, a reset code has been sent."


def _credentials_validator(payload):
    v = Validator(payload)
    v.string("email", required=True, max_len=200)
    v.string("password", required=True, max_len=128)
    v.enum("account_type", auth.ACCOUNT_TYPES, default="user")
    return v


@auth_bp.post("/auth/login")
def login():
    cleaned = _credentials_validator(request_payload()).validate()
    account_type = cleaned["account_type"]
    conn = get_db()
    try:
        row = auth.authenticate(conn, account_type, cleaned["email"], cleaned["password"])
    finally:
        conn.close()
    if row is None:
        raise ApiError("Invalid email or password", 401, "UNAUTHORIZED")
    auth.ensure_email_verified(row)
    auth.ensure_account_active(account_type, row)
    account_id = auth.account_id_of(account_type, row)
    if not auth.issue_otp("login", account_type, account_id, row["email"]):
        raise ApiError("Could not send the verification code; try again", 502, "INTERNAL_ERROR")
    return api_response({
        "account_id": account_id,
        "account_type": account_type,
        "otp_required": True,
        "otp_expires_in": auth.otp_ttl(),
    }, "Verification code sent to your email")


def _email_otp_validator(payload, with_otp):
    v = Validator(payload)
    v.string("email", required=True, max_len=200)
    if with_otp:
        v.string("otp", required=True, min_len=6, max_len=6)
    v.enum("account_type", auth.ACCOUNT_TYPES, default="admin")
    return v.validate()


def _verify_email_otp(payload):
    """Signup email verification: {email, otp, account_type} -> is_email_verified=1."""
    cleaned = _email_otp_validator(payload, with_otp=True)
    account_type = cleaned["account_type"]
    with db_connection() as conn:
        row = auth.find_account_by_email(conn, account_type, cleaned["email"])
    if row is None:
        raise ValidationError("Invalid verification code", fields={"otp": "incorrect"})
    account_id = auth.account_id_of(account_type, row)
    auth.check_otp("verify", account_type, account_id, cleaned["otp"])
    with db_connection(immediate=True) as conn:
        auth.mark_email_verified(conn, account_type, account_id)
        write_audit(conn, account_id, account_type, "auth.email_verified", account_type, account_id, {})
    return api_response({"account_id": account_id, "account_type": account_type, "email_verified": True},
                        "Email verified. You can now log in.")


@auth_bp.post("/auth/resend-otp")
def resend_otp():
    cleaned = _email_otp_validator(request_payload(), with_otp=False)
    account_type = cleaned["account_type"]
    with db_connection() as conn:
        row = auth.find_account_by_email(conn, account_type, cleaned["email"])
    generic = "If this account exists and is not verified, a new code has been sent."
    if row is None or acc.email_is_verified(row):
        return api_response({"otp_expires_in": auth.otp_ttl("verify")}, generic)
    account_id = auth.account_id_of(account_type, row)
    auth.enforce_resend_cooldown("verify", account_type, account_id)
    auth.send_verification_otp(account_type, account_id, row["email"])
    return api_response({"otp_expires_in": auth.otp_ttl("verify"),
                         "resend_cooldown": auth.RESEND_COOLDOWN_SECONDS}, generic)


@auth_bp.post("/auth/verify-otp")
def verify_otp():
    payload = request_payload()
    if "email" in payload and "account_id" not in payload:
        return _verify_email_otp(payload)
    v = Validator(payload)
    v.string("account_id", required=True, max_len=64)
    v.string("otp", required=True, min_len=6, max_len=6)
    v.enum("account_type", auth.ACCOUNT_TYPES, default="user")
    cleaned = v.validate()
    account_type, account_id = cleaned["account_type"], cleaned["account_id"]
    auth.check_otp("login", account_type, account_id, cleaned["otp"])
    with db_connection() as conn:
        row = auth.fetch_account(conn, account_type, account_id)
        if row is None:
            raise ApiError("Account no longer exists", 401, "UNAUTHORIZED")
        role = auth.ensure_account_active(account_type, row)
        write_audit(conn, account_id, role, "auth.login", account_type, account_id, {})
    return api_response(auth.issue_tokens(account_type, account_id, role), "Login successful")


@auth_bp.post("/auth/refresh")
@jwt_required(refresh=True)
def refresh():
    claims = get_jwt()
    account_id = get_jwt_identity()
    account_type = auth.account_type_from_claims(claims)
    conn = get_db()
    try:
        row = auth.fetch_account(conn, account_type, account_id)
    finally:
        conn.close()
    if row is None:
        raise ApiError("Account no longer exists", 401, "UNAUTHORIZED")
    role = auth.ensure_account_active(account_type, row)  # role + block status re-read from DB
    revoke_token(claims)  # rotation: the presented refresh token cannot be used again
    return api_response(auth.issue_tokens(account_type, account_id, role), "Token refreshed")


@auth_bp.post("/auth/logout")
@role_required(["admin", "user"])
def logout():
    claims = get_jwt()
    v = Validator(request_payload())
    v.string("refresh_token", max_len=4096)
    refresh_token = v.validate().get("refresh_token")
    revoked = ["access"]
    if refresh_token:
        try:
            payload = decode_token(refresh_token, allow_expired=True)
        except Exception:
            raise ValidationError(fields={"refresh_token": "invalid token"})
        if payload.get("type") != "refresh" or payload.get("sub") != claims.get("sub"):
            raise ValidationError(fields={"refresh_token": "not a refresh token for this account"})
        revoke_token(payload)
        revoked.append("refresh")
    revoke_token(claims)
    return api_response({"revoked": revoked}, "Logged out")


@auth_bp.post("/auth/password-reset/request")
def password_reset_request():
    v = Validator(request_payload())
    v.string("email", required=True, max_len=200)
    v.enum("account_type", auth.ACCOUNT_TYPES, default="user")
    cleaned = v.validate()
    conn = get_db()
    try:
        row = auth.find_account_by_email(conn, cleaned["account_type"], cleaned["email"])
    finally:
        conn.close()
    if row is None:
        current_app.logger.warning("password-reset: no %s account found for requested email", cleaned["account_type"])
    elif auth.resolve_role(cleaned["account_type"], row) is None:
        current_app.logger.warning("password-reset: %s account is deleted/disabled", cleaned["account_type"])
    else:
        sent = auth.issue_otp("reset", cleaned["account_type"], auth.account_id_of(cleaned["account_type"], row), row["email"])
        current_app.logger.warning("password-reset: account found, email handed to provider=%s", sent)
    # Identical response whether or not the account exists (no user enumeration).
    return api_response({"otp_expires_in": auth.otp_ttl()}, RESET_MESSAGE)


@auth_bp.post("/auth/password-reset/confirm")
def password_reset_confirm():
    payload = request_payload()
    v = Validator(payload)
    v.string("email", required=True, max_len=200)
    v.string("otp", required=True, min_len=6, max_len=6)
    v.enum("account_type", auth.ACCOUNT_TYPES, default="user")
    acc.add_password_rule(v, "new_password", required=True)
    cleaned = v.validate()
    account_type = cleaned["account_type"]
    conn = get_db()
    try:
        row = auth.find_account_by_email(conn, account_type, cleaned["email"])
    finally:
        conn.close()
    if row is None or auth.resolve_role(account_type, row) is None:
        raise ValidationError("Verification code expired or not requested", fields={"otp": "request a new code"})
    account_id = auth.account_id_of(account_type, row)
    auth.check_otp("reset", account_type, account_id, cleaned["otp"])
    with db_connection(immediate=True) as conn:
        if account_type == "admin":
            acc.update_admin(conn, account_id, {"password": cleaned["new_password"]})
        else:
            acc.update_user(conn, account_id, {"password": cleaned["new_password"]})
        write_audit(conn, account_id, account_type, "auth.password_reset", account_type, account_id, {})
    return api_response(None, "Password has been reset. Please log in.")
