import cloudinary.uploader
from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt
from app.utils.decorators import role_required
from app.services.add_ops import createAdmin, record_Sell
from app.services.read_ops import (
    getAllAdmins,
    getAllUsers,
    getSellHistory,
    getUserSellHistory,
    getProductSellHistory,
)
from app.services.update_ops import (
    update_approve_user,
    update_user_details,
    update_admin_details,
)
from app.services.delete_ops import (
    delete_User,
    delete_Admin,
    delete_SellHistory,
)

admin_bp = Blueprint("admin", __name__)

ALLOWED_USER_EDITABLE_FIELDS = {"name", "address", "phone_number", "pin_code", "password", "image_url"}

@admin_bp.route("/admin/create", methods=["POST"])
@role_required(["admin"])
def create_admin():
    try:
        email = request.form["email"]
        name = request.form["name"]
        password = request.form["password"]
        phoneNumber = request.form["phoneNumber"]
        role = "admin"

        image_url = request.form.get("image_url")
        if "image" in request.files:
            file = request.files["image"]
            if file.filename != "":
                upload_result = cloudinary.uploader.upload(file, folder="MediAdminApp/Admins")
                image_url = upload_result.get("secure_url")

        res = createAdmin(email=email, name=name, password=password, phoneNumber=phoneNumber, role=role, image_url=image_url)
        code = res.get("status", 201) if isinstance(res, dict) else 201
        return jsonify(res), code
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400

@admin_bp.route("/admin/getAllAdmins", methods=["GET"])
@role_required(["admin"])
def get_All_Admins():
    try:
        admins = getAllAdmins()
        return jsonify({"admins": admins, "message": "Admins fetched Successfully", "status": 200}), 200
    except Exception as error:
        return jsonify({"admins": [], "message": str(error), "status": 400}), 400

@admin_bp.route("/admin/getAllUsers", methods=["GET"])
@role_required(["admin"])
def get_All_Users():
    try:
        users = getAllUsers()
        return jsonify({"users": users, "message": "Users fetched Successfully", "status": 200}), 200
    except Exception as error:
        return jsonify({"users": [], "message": str(error), "status": 400}), 400

@admin_bp.route("/admin/approveUser", methods=["PATCH"])
@role_required(["admin"])
def approve_User():
    try:
        userId = request.form["user_id"]
        approve = request.form["isApproved"]
        res = update_approve_user(userId=userId, approve=approve)
        code = res.get("status", 200) if isinstance(res, dict) else 200
        return jsonify(res), code
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400

@admin_bp.route("/admin/updateUser", methods=["PATCH"])
@role_required(["admin", "user"])
def update_user():
    try:
        user_id = request.form["user_id"]
        claims = get_jwt()
        caller_role = claims.get("role", "user")

        updateUser = {}
        for key, value in request.form.items():
            if key == "user_id":
                continue
            # Non-admins cannot elevate privilege (block, isApproved, role, date_of_account_creation)
            if caller_role != "admin" and key not in ALLOWED_USER_EDITABLE_FIELDS:
                continue
            updateUser[key] = value

        if "image" in request.files:
            file = request.files["image"]
            if file.filename != "":
                upload_result = cloudinary.uploader.upload(file, folder="MediAdminApp/Users")
                updateUser["image_url"] = upload_result.get("secure_url")

        update_user_details(user_id, updateUser)
        return jsonify({"message": "User Updated Successfully", "status": 200}), 200
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400

@admin_bp.route("/admin/update", methods=["PATCH"])
@role_required(["admin"])
def update_admin():
    try:
        admin_id = request.form["admin_id"]
        updateAdmin = {}
        for key, value in request.form.items():
            if key != "admin_id":
                updateAdmin[key] = value

        if "image" in request.files:
            file = request.files["image"]
            if file.filename != "":
                upload_result = cloudinary.uploader.upload(file, folder="MediAdminApp/Admins")
                updateAdmin["image_url"] = upload_result.get("secure_url")

        update_admin_details(admin_id, updateAdmin)
        return jsonify({"message": "Admin Updated Successfully", "status": 200}), 200
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400

@admin_bp.route("/admin/deleteUser", methods=["POST"])
@role_required(["admin"])
def delete_user():
    try:
        user_id = request.form["user_id"]
        res = delete_User(user_id)
        code = res.get("status", 200) if isinstance(res, dict) else 200
        return jsonify(res), code
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400

@admin_bp.route("/admin/delete", methods=["POST"])
@role_required(["admin"])
def delete_admin():
    try:
        admin_id = request.form["admin_id"]
        res = delete_Admin(admin_id)
        code = res.get("status", 200) if isinstance(res, dict) else 200
        return jsonify(res), code
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400

@admin_bp.route("/admin/recordSell", methods=["POST"])
@role_required(["admin"])
def record_sell():
    try:
        Order_id = request.form.get("Order_id")
        res = record_Sell(Order_id=Order_id)
        code = res.get("status", 201) if isinstance(res, dict) else 201
        return jsonify(res), code
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400

@admin_bp.route("/admin/getSellHistory", methods=["GET"])
@role_required(["admin"])
def get_sell_history():
    try:
        sell_history = getSellHistory()
        return jsonify({"sell_history": sell_history, "message": "Sell History fetched Successfully", "status": 200}), 200
    except Exception as error:
        return jsonify({"sell_history": [], "message": str(error), "status": 400}), 400

@admin_bp.route("/admin/user/getSellHistoryByUserId", methods=["POST"])
@role_required(["admin", "user"])
def get_user_sell_history():
    try:
        user_id = request.form["user_id"]
        sell_history = getUserSellHistory(user_id=user_id)
        return jsonify({"sell_history": sell_history, "message": "Sell History fetched Successfully", "status": 200}), 200
    except Exception as error:
        return jsonify({"sell_history": [], "message": str(error), "status": 400}), 400

@admin_bp.route("/admin/getproductsellhistory", methods=["POST"])
@role_required(["admin", "user"])
def get_product_sell_history():
    try:
        Product_id = request.form["Product_id"]
        response = getProductSellHistory(Product_id=Product_id)
        return jsonify({"sell_history": response, "message": "Sell History fetched Successfully", "status": 200}), 200
    except Exception as error:
        return jsonify({"sell_history": [], "message": str(error), "status": 400}), 400

@admin_bp.route("/admin/deleteSellHistory", methods=["POST"])
@role_required(["admin"])
def delete_sell_history():
    try:
        Sell_id = request.form["Sell_id"]
        res = delete_SellHistory(Sell_id)
        code = res.get("status", 200) if isinstance(res, dict) else 200
        return jsonify(res), code
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400
