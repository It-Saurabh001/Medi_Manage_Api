from functools import wraps

from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.utils.responses import error_response


def role_required(allowed_roles):
    """jwt_required + role check. Returns R6 403 FORBIDDEN for other roles."""
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            role = get_jwt().get("role")
            if role not in allowed_roles:
                return error_response("Access Forbidden", 403, "FORBIDDEN")
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def current_identity():
    """(identity, role) of the authenticated caller. Call only inside a JWT-protected view."""
    return get_jwt_identity(), get_jwt().get("role")


def is_admin():
    return get_jwt().get("role") == "admin"
