from flask import jsonify

# Default R6 error code for each HTTP status
STATUS_CODES = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    426: "UPGRADE_REQUIRED",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
}


def _attach_headers(response, headers):
    if headers:
        for key, value in headers.items():
            response.headers[key] = value
    return response


def api_response(data=None, message="Success", status_code=200, headers=None, **kwargs):
    """Success envelope: {"status","message","data", **extra}. `data` key is always present."""
    payload = {"status": status_code, "message": message, "data": data}
    payload.update(kwargs)
    response = jsonify(payload)
    response.status_code = status_code
    return _attach_headers(response, headers)


def paginated_response(data, limit, offset, total, message="Success", headers=None):
    """R5 list envelope."""
    return api_response(
        data=list(data),
        message=message,
        status_code=200,
        headers=headers,
        pagination={"limit": limit, "offset": offset, "total": total},
    )


def error_response(message="An error occurred", status=400, code=None, fields=None, headers=None):
    """R6 error envelope: {"status","message","code"} (+ "fields" when given)."""
    payload = {
        "status": status,
        "message": message,
        "code": code or STATUS_CODES.get(status, "INTERNAL_ERROR" if status >= 500 else "VALIDATION_ERROR"),
    }
    if fields:
        payload["fields"] = fields
    response = jsonify(payload)
    response.status_code = status
    return _attach_headers(response, headers)
