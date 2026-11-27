"""Centralised R6-shaped error handling (never HTML, never exception text)."""
from werkzeug.exceptions import HTTPException

from app.utils.responses import STATUS_CODES, error_response


class ApiError(Exception):
    """Raise anywhere inside a request to return an R6 error."""

    status = 400
    code = None
    message = "Request failed"

    def __init__(self, message=None, status=None, code=None, fields=None, headers=None):
        super().__init__(message or self.message)
        self.message = message or self.message
        self.status = status or self.status
        self.code = code or self.code or STATUS_CODES.get(self.status, "INTERNAL_ERROR")
        self.fields = fields
        self.headers = headers


class ValidationError(ApiError):
    status = 400
    code = "VALIDATION_ERROR"
    message = "Validation failed"


class NotFoundError(ApiError):
    status = 404
    code = "NOT_FOUND"
    message = "Resource not found"


class ConflictError(ApiError):
    status = 409
    code = "CONFLICT"
    message = "Conflict"


class ForbiddenError(ApiError):
    status = 403
    code = "FORBIDDEN"
    message = "Access Forbidden"


HTTP_MESSAGES = {
    400: "Bad request",
    401: "Authentication required",
    403: "Access Forbidden",
    404: "Resource not found",
    405: "Method not allowed",
    409: "Conflict",
    413: "Payload too large",
    415: "Unsupported media type",
    422: "Unprocessable request",
    429: "Too many requests",
    500: "Internal server error",
}


def register_error_handlers(app):
    """Register JSON error handlers and flask-jwt-extended loaders."""

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return error_response(error.message, error.status, error.code, error.fields, error.headers)

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        status = error.code or 500
        headers = None
        if status == 405 and getattr(error, "valid_methods", None):
            headers = {"Allow": ", ".join(sorted(error.valid_methods))}
        message = HTTP_MESSAGES.get(status) or ("Internal server error" if status >= 500 else "Request failed")
        return error_response(message, status, STATUS_CODES.get(status), headers=headers)

    @app.errorhandler(Exception)
    def handle_generic_exception(error):
        app.logger.exception("Unhandled server exception")
        return error_response("Internal server error", 500, "INTERNAL_ERROR")

    _register_jwt_loaders()


def _register_jwt_loaders():
    from app.extensions import jwt

    @jwt.unauthorized_loader
    def _missing_token(reason):
        return error_response("Missing or malformed authorization token", 401, "UNAUTHORIZED")

    @jwt.invalid_token_loader
    def _invalid_token(reason):
        return error_response("Invalid token", 401, "TOKEN_INVALID")

    @jwt.expired_token_loader
    def _expired_token(jwt_header, jwt_payload):
        return error_response("Token has expired", 401, "TOKEN_EXPIRED")

    @jwt.revoked_token_loader
    def _revoked_token(jwt_header, jwt_payload):
        from flask import g

        # Account-level revocations answer exactly like login/refresh would for that account state,
        # so existing clients keep handling them with the codes they already know.
        reason = getattr(g, "jwt_revoked_reason", None)
        if reason == "blocked":
            return error_response("Account is blocked", 403, "ACCOUNT_BLOCKED")
        if reason == "disabled":
            return error_response("Account is disabled", 403, "ACCOUNT_BLOCKED")
        if reason == "deleted":
            return error_response("Account no longer exists", 401, "UNAUTHORIZED")
        return error_response("Token has been revoked", 401, "TOKEN_INVALID")

    @jwt.needs_fresh_token_loader
    def _needs_fresh(jwt_header, jwt_payload):
        return error_response("Fresh token required", 401, "UNAUTHORIZED")
