from flask import Blueprint, jsonify, request, render_template
from app.utils.decorators import role_required
from app.services.add_ops import createUser
from app.services.read_ops import getSpecificUser

user_bp = Blueprint("user", __name__)

@user_bp.route("/", methods=["GET"])
def hello_world():
    return "Hello World", 200

@user_bp.route("/dox", methods=["GET"])
def dox():
    return render_template("dox.html"), 200

@user_bp.route("/user/create", methods=["POST"])
def create_user():
    try:
        name = request.form.get("name")
        password = request.form.get("password")
        phoneNumber = request.form.get("phoneNumber")
        email = request.form.get("email")
        pincode = request.form.get("pincode")
        address = request.form.get("address")

        if not name or not password:
            return jsonify({"message": "Name and Password are mandatory", "status": 400}), 400

        if not email and not phoneNumber:
            return jsonify({"message": "Please provide either Email or Phone Number", "status": 400}), 400

        role = "user"
        if request.headers.get("Admin") == "admin":
            role = "admin"

        res = createUser(
            name=name,
            password=password,
            phoneNumber=phoneNumber,
            email=email,
            pincode=pincode,
            address=address,
            role=role
        )
        code = res.get("status", 201) if isinstance(res, dict) else 201
        return jsonify(res), code
    except Exception as e:
        return jsonify({"message": str(e), "status": 400}), 400

@user_bp.route("/admin/user/getSpecificUser", methods=["POST"])
@role_required(["admin", "user"])
def get_specific_user():
    try:
        userId = request.form["user_id"]
        user = getSpecificUser(userId=userId)
        if user is None:
            return jsonify({"user": None, "message": "User not found", "status": 404}), 404
        return jsonify({"user": user, "message": "User fetched Successfully", "status": 200}), 200
    except Exception as error:
        return jsonify({"user": None, "message": str(error), "status": 400}), 400
