import time
from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from app.services.auth_service import (
    authenticate,
    get_user_by_id,
    request_password_reset,
    reset_password_with_otp,
)
from app.services.email_service import generate_otp, send_otp_email
from app.services.otp_service import otp_store, user_otp_store

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/admin/refreshToken", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    try:
        admin_id = get_jwt_identity()
        claims = get_jwt()
        role = claims.get("role")
        new_access_token = create_access_token(identity=admin_id, additional_claims={"role": role})
        new_refresh_token = create_refresh_token(identity=admin_id, additional_claims={"role": role})

        return jsonify({
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "role": role,
            "status": 200,
            "message": "Token refreshed successfully"
        }), 200
    except Exception as error:
        return jsonify({"message": str(error), "status": 401}), 401

@auth_bp.route("/admin/login", methods=["POST"])
def login_Admin():
    try:
        email = request.form["email"]
        password = request.form["password"]
        auth_result = authenticate(email=email, password=password, user_type="admin")

        if not auth_result:
            return jsonify({"status": 401, "message": "Invalid email or password"}), 401

        admin_id, role = auth_result
        otp = generate_otp()
        expiry = time.time() + 300
        otp_store[admin_id] = {"otp": otp, "expiry": expiry}

        send_otp_email(to_email=email, otp=otp)

        return jsonify({"status": 200, "admin_id": admin_id, "role": role, "message": "OTP sent to your email"}), 200
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400

@auth_bp.route("/admin/verifyOtp", methods=["POST"])
def verify_admin_otp():
    try:
        admin_id = request.form["admin_id"]
        otp = request.form["otp"]
        if admin_id not in otp_store:
            return jsonify({"status": 400, "message": "No OTP request found "}), 400
        stored_otp = otp_store[admin_id]["otp"]
        expiry = otp_store[admin_id]["expiry"]

        if time.time() > expiry:
            del otp_store[admin_id]
            return jsonify({"status": 400, "message": "OTP expired"}), 400

        if str(otp) == str(stored_otp):
            _, role = get_user_by_id(admin_id, "admin")
            access_token = create_access_token(identity=admin_id, additional_claims={"role": role})
            refresh_token = create_refresh_token(identity=admin_id, additional_claims={"role": role})

            del otp_store[admin_id]
            return jsonify({
                "status": 200,
                "message": "OTP verified successfully",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "role": role
            }), 200
        else:
            return jsonify({"status": 400, "message": "Invalid OTP"}), 400
    except Exception as error:
        return jsonify({"status": 400, "message": str(error)}), 400

@auth_bp.route("/admin/requestAdminPasswordReset", methods=["POST"])
def request_admin_password_reset():
    try:
        email = request.form["email"]
        res = request_password_reset(email, "admin")
        code = res.get("status", 200) if isinstance(res, dict) else 200
        return jsonify(res), code
    except Exception as error:
        return jsonify({"status": 400, "admin_id": None, "message": str(error)}), 400

@auth_bp.route("/admin/resetAdminPasswordWithOtp", methods=["POST"])
def reset_admin_password_with_otp():
    try:
        admin_id = request.form["admin_id"]
        otp = request.form["otp"]
        new_password = request.form["new_password"]
        res = reset_password_with_otp(admin_id, otp, new_password, "admin")
        code = res.get("status", 200) if isinstance(res, dict) else 200
        return jsonify(res), code
    except Exception as error:
        return jsonify({"status": 400, "message": str(error)}), 400

@auth_bp.route("/user/login", methods=["POST"])
def login_user():
    try:
        email = request.form["email"]
        password = request.form["password"]
        auth_result = authenticate(email=email, password=password, user_type="user")
        if not auth_result:
            return jsonify({"user_id": None, "message": "Invalid email or password", "status": 401}), 401

        user_id, role = auth_result
        otp = generate_otp()
        expiry = time.time() + 300
        user_otp_store[user_id] = {"otp": otp, "expiry": expiry}
        send_otp_email(to_email=email, otp=otp)
        return jsonify({"user_id": user_id, "role": role, "message": f"OTP {otp} sent to your email", "status": 200}), 200
    except Exception as error:
        return jsonify({"user_id": None, "message": str(error), "status": 400}), 400

@auth_bp.route("/user/verifyUserOtp", methods=["POST"])
def verify_user_otp():
    try:
        user_id = request.form["user_id"]
        otp = request.form["otp"]
        if user_id not in user_otp_store:
            return jsonify({"status": 400, "message": "No OTP request found"}), 400
        stored_otp = user_otp_store[user_id]["otp"]
        expiry = user_otp_store[user_id]["expiry"]

        if time.time() > expiry:
            del user_otp_store[user_id]
            return jsonify({"status": 400, "message": "OTP expired"}), 400

        if str(otp) == str(stored_otp):
            _, role = get_user_by_id(user_id, "user")
            access_token = create_access_token(identity=user_id, additional_claims={"role": role})
            refresh_token = create_refresh_token(identity=user_id, additional_claims={"role": role})
            del user_otp_store[user_id]
            return jsonify({
                "status": 200,
                "message": "OTP Verified Successfully",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "role": role
            }), 200
        else:
            return jsonify({
                "status": 400,
                "message": "Invalid OTP",
                "access_token": None,
                "refresh_token": None,
                "role": "user"
            }), 400
    except Exception as error:
        return jsonify({
            "status": 400,
            "message": str(error),
            "access_token": None,
            "refresh_token": None,
            "role": "user"
        }), 400

@auth_bp.route("/user/requestUserPasswordReset", methods=["POST"])
def request_user_password_reset():
    try:
        email = request.form["email"]
        res = request_password_reset(email, "user")
        code = res.get("status", 200) if isinstance(res, dict) else 200
        return jsonify(res), code
    except Exception as error:
        return jsonify({"status": 400, "message": str(error)}), 400

@auth_bp.route("/user/resetUserPasswordWithOtp", methods=["POST"])
def reset_user_password_with_otp():
    try:
        user_id = request.form["user_id"]
        otp = request.form["otp"]
        new_password = request.form["new_password"]
        res = reset_password_with_otp(user_id, otp, new_password, "user")
        code = res.get("status", 200) if isinstance(res, dict) else 200
        return jsonify(res), code
    except Exception as error:
        return jsonify({"status": 400, "message": str(error)}), 400
