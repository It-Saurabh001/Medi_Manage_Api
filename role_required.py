from functools import wraps
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity, create_access_token
from flask import Flask,jsonify

def role_required(allowed_roles):
    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            role = claims.get("role")
            if role not in allowed_roles:
                return jsonify({"message": "Access Forbidden", "status": 403}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator


