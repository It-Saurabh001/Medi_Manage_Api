"""OpenAPI fragment: authentication (Part 3). Keys are relative to API_PREFIX."""
from app.openapi._examples import ACCESS_TOKEN, REFRESH_TOKEN, envelope, error, operation, ref

TAG = "Auth"
ACCOUNT_TYPE = {"type": "string", "enum": ["user", "admin"], "default": "user"}
TOKENS_EXAMPLE = {
    "access_token": ACCESS_TOKEN, "refresh_token": REFRESH_TOKEN, "token_type": "Bearer", "expires_in": 3600,
    "role": "user", "account_type": "user", "account_id": "UID_06ade2a9b763",
}
OTP_INVALID = error(400, "VALIDATION_ERROR", "Invalid verification code", {"otp": "incorrect; 4 attempt(s) left"})
OTP_EXPIRED = error(400, "VALIDATION_ERROR", "Verification code expired or not requested",
                    {"otp": "request a new code"})
OTP_LOCKED = error(429, "RATE_LIMITED", "Too many incorrect attempts; request a new code")
BLOCKED = error(403, "ACCOUNT_BLOCKED", "Account is blocked")
NOT_APPROVED = error(403, "ACCOUNT_NOT_APPROVED", "Account is not approved yet")
REVOKED = error(401, "TOKEN_INVALID", "Token has been revoked")

SCHEMAS = {
    "LoginInput": {"type": "object", "required": ["email", "password"], "properties": {
        "email": {"type": "string", "maxLength": 200}, "password": {"type": "string", "maxLength": 128},
        "account_type": ACCOUNT_TYPE}},
    "LoginChallenge": {"type": "object", "properties": {
        "account_id": {"type": "string"}, "account_type": ACCOUNT_TYPE, "otp_required": {"type": "boolean"},
        "otp_expires_in": {"type": "integer", "description": "seconds"}}},
    "VerifyOtpInput": {"type": "object", "required": ["account_id", "otp"], "properties": {
        "account_id": {"type": "string"}, "otp": {"type": "string", "minLength": 6, "maxLength": 6},
        "account_type": ACCOUNT_TYPE}},
    "Tokens": {"type": "object", "properties": {
        "access_token": {"type": "string"}, "refresh_token": {"type": "string"},
        "token_type": {"type": "string", "enum": ["Bearer"]}, "expires_in": {"type": "integer"},
        "role": {"type": "string", "enum": ["user", "admin"]}, "account_type": ACCOUNT_TYPE,
        "account_id": {"type": "string"}}},
    "LogoutInput": {"type": "object", "properties": {
        "refresh_token": {"type": "string", "description": "optional; also revokes this refresh token"}}},
    "ResetRequestInput": {"type": "object", "required": ["email"], "properties": {
        "email": {"type": "string"}, "account_type": ACCOUNT_TYPE}},
    "ResetConfirmInput": {"type": "object", "required": ["email", "otp", "new_password"], "properties": {
        "email": {"type": "string"}, "otp": {"type": "string", "minLength": 6, "maxLength": 6},
        "new_password": {"type": "string", "minLength": 8, "maxLength": 128}, "account_type": ACCOUNT_TYPE}},
}

PATHS = {
    "/auth/login": {"post": operation(
        TAG, "Check credentials and email a 6-digit login OTP (never returned)", [], 200,
        envelope(ref("LoginChallenge")),
        {"status": 200, "message": "Verification code sent to your email",
         "data": {"account_id": "UID_06ade2a9b763", "account_type": "user", "otp_required": True, "otp_expires_in": 300}},
        [error(400, "VALIDATION_ERROR", "Validation failed", {"email": "is required"}),
         error(401, "UNAUTHORIZED", "Invalid email or password"), BLOCKED, NOT_APPROVED],
        body=ref("LoginInput"), body_example={"email": "priya@example.com", "password": "Priya#2026", "account_type": "user"},
        multipart=True, public=True)},
    "/auth/verify-otp": {"post": operation(
        TAG, "Verify the login OTP and issue access + refresh tokens", [], 200, envelope(ref("Tokens")),
        {"status": 200, "message": "Login successful", "data": TOKENS_EXAMPLE},
        [OTP_INVALID, OTP_EXPIRED, OTP_LOCKED, BLOCKED, NOT_APPROVED],
        body=ref("VerifyOtpInput"), body_example={"account_id": "UID_06ade2a9b763", "otp": "672170", "account_type": "user"},
        multipart=True, public=True,
        notes="Max 5 attempts per OTP, then it is invalidated (429 RATE_LIMITED). A reset OTP cannot be used here.")},
    "/auth/refresh": {"post": operation(
        TAG, "Rotate tokens using the refresh token (Authorization: Bearer <refresh_token>)", ["admin", "user"], 200,
        envelope(ref("Tokens")), {"status": 200, "message": "Token refreshed", "data": TOKENS_EXAMPLE},
        [REVOKED, error(401, "TOKEN_EXPIRED", "Token has expired"), BLOCKED, NOT_APPROVED],
        notes="Role and block/approval status are re-read from the DB; the presented refresh token is revoked.")},
    "/auth/logout": {"post": operation(
        TAG, "Revoke the access token (and the refresh token if supplied)", ["admin", "user"], 200,
        envelope({"type": "object", "properties": {"revoked": {"type": "array", "items": {"type": "string"}}}}),
        {"status": 200, "message": "Logged out", "data": {"revoked": ["access", "refresh"]}},
        [error(400, "VALIDATION_ERROR", "Validation failed", {"refresh_token": "invalid token"}), REVOKED,
         error(401, "UNAUTHORIZED", "Missing or malformed authorization token")],
        body=ref("LogoutInput"), body_example={"refresh_token": REFRESH_TOKEN}, multipart=True)},
    "/auth/password-reset/request": {"post": operation(
        TAG, "Email a password-reset OTP (same response whether or not the account exists)", [], 200,
        envelope({"type": "object", "properties": {"otp_expires_in": {"type": "integer"}}}),
        {"status": 200, "message": "If an account exists for this email, a reset code has been sent.",
         "data": {"otp_expires_in": 300}},
        [error(400, "VALIDATION_ERROR", "Validation failed", {"email": "is required"})],
        body=ref("ResetRequestInput"), body_example={"email": "priya@example.com", "account_type": "user"},
        multipart=True, public=True)},
    "/auth/resend-otp": {"post": operation(
        TAG, "Re-send the signup email-verification OTP (60 s cooldown)", [], 200,
        envelope({"type": "object", "properties": {"otp_expires_in": {"type": "integer"}}}),
        {"status": 200, "message": "If this account exists and is not verified, a new code has been sent.",
         "data": {"otp_expires_in": 600}},
        [error(400, "VALIDATION_ERROR", "Validation failed", {"email": "is required"}),
         error(429, "RATE_LIMITED", "Please wait 60 seconds before requesting a new code"),
         error(502, "EMAIL_DELIVERY_FAILED", "Could not send the verification email")],
        body=ref("ResetRequestInput"), body_example={"email": "priya@example.com", "account_type": "admin"},
        multipart=True, public=True,
        notes="Verify with POST /auth/verify-otp {email, otp, account_type}; success sets is_email_verified.")},
    "/auth/password-reset/confirm": {"post": operation(
        TAG, "Set a new password with the reset OTP", [], 200, envelope({"nullable": True}),
        {"status": 200, "message": "Password has been reset. Please log in.", "data": None},
        [error(400, "VALIDATION_ERROR", "Validation failed", {"new_password": "must be at least 8 characters"}),
         OTP_EXPIRED, OTP_LOCKED],
        body=ref("ResetConfirmInput"),
        body_example={"email": "priya@example.com", "otp": "144651", "new_password": "Priya#2026", "account_type": "user"},
        multipart=True, public=True)},
}
