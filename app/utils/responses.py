from flask import jsonify

def api_response(data=None, message="Success", status_code=200, **kwargs):
    """Standardized success and general response builder."""
    payload = {
        "status": status_code,
        "message": message,
    }
    if data is not None:
        if isinstance(data, dict):
            payload.update(data)
        else:
            payload["data"] = data

    payload.update(kwargs)
    return jsonify(payload), status_code

def error_response(message="An error occurred", status_code=400, errors=None):
    """Standardized error response builder."""
    payload = {
        "status": status_code,
        "message": message,
    }
    if errors is not None:
        payload["errors"] = errors
    return jsonify(payload), status_code
