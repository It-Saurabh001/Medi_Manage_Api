import jwt
import datetime
from functools import wraps
from flask import request, jsonify

SECRET_KEY = "your_secret_key"

def generate_jwt(user_id, email):
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.datetime.utcnow()+ datetime.timedelta(hours=2)
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    return token

def decode_jwt(token):
    try: 
        payload = jwt.decode(token,SECRET_KEY,algorithms="HS256")
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    

def jwt_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]
        if not token:
            return jsonify({"message": "Token is missing!", "status": 401}), 401
        data = decode_jwt(token)
        if not data:
            return jsonify({"message": "Token is invalid! or expired", "status": 401}), 401
        return f(*args, **kwargs)
    return decorated