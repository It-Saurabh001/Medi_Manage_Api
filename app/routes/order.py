from flask import Blueprint, jsonify, request
from app.utils.decorators import role_required
from app.services.add_ops import createOrder
from app.services.read_ops import getAllOrders, getUserOrders, getOrderById
from app.services.update_ops import update_Order, approve_Order
from app.services.delete_ops import delete_Order

order_bp = Blueprint("order", __name__)

@order_bp.route("/user/createOrder", methods=["POST"])
@role_required(["admin", "user"])
def create_order():
    try:
        user_id = request.form["user_id"]
        Product_id = request.form["Product_id"]
        quantity = int(request.form["quantity"])
        message = request.form.get("message", "")

        res = createOrder(user_id=user_id, Product_id=Product_id, quantity=quantity, message=message)
        code = res.get("status", 201) if isinstance(res, dict) else 201
        return jsonify(res), code
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400

@order_bp.route("/admin/getAllOrders", methods=["GET"])
@role_required(["admin"])
def get_all_orders():
    try:
        orders = getAllOrders()
        return jsonify({"orders": orders, "message": "Orders fetched Successfully", "status": 200}), 200
    except Exception as error:
        return jsonify({"orders": [], "message": str(error), "status": 400}), 400

@order_bp.route("/admin/user/getOrdersByUserId", methods=["POST"])
@role_required(["admin", "user"])
def get_user_orders():
    try:
        user_id = request.form["user_id"]
        order = getUserOrders(user_id=user_id)
        return jsonify({"order": order, "message": "Order fetched Successfully", "status": 200}), 200
    except Exception as error:
        return jsonify({"order": [], "message": str(error), "status": 400}), 400

@order_bp.route("/admin/user/orderById", methods=["POST"])
@role_required(["admin", "user"])
def get_order_by_id():
    try:
        Order_id = request.form["Order_id"]
        order = getOrderById(Order_id=Order_id)
        if order is None:
            return jsonify({"order": None, "message": "Order not found", "status": 404}), 404
        return jsonify({"order": order, "message": "Order fetched Successfully", "status": 200}), 200
    except Exception as error:
        return jsonify({"order": [], "message": str(error), "status": 400}), 400

@order_bp.route("/admin/updateOrder", methods=["PATCH"])
@role_required(["admin"])
def update_order():
    try:
        Order_id = request.form["Order_id"]
        updateOrder = {}
        for key, value in request.form.items():
            if key != "Order_id":
                updateOrder[key] = value
        res = update_Order(Order_id=Order_id, updateOrder=updateOrder)
        code = res.get("status", 200) if isinstance(res, dict) else 200
        return jsonify(res), code
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400

@order_bp.route("/admin/approveOrder", methods=["PATCH"])
@role_required(["admin"])
def approve_order():
    try:
        Order_id = request.form["Order_id"]
        isApproved = request.form["isApproved"]
        if isApproved == "true":
            isApproved = 1
        elif isApproved == "false":
            isApproved = 0
        res = approve_Order(Order_id=Order_id, isApproved=isApproved)
        code = res.get("status", 200) if isinstance(res, dict) else 200
        return jsonify(res), code
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400

@order_bp.route("/admin/deleteOrder", methods=["POST"])
@role_required(["admin"])
def delete_order():
    try:
        Order_id = request.form["Order_id"]
        res = delete_Order(Order_id)
        code = res.get("status", 200) if isinstance(res, dict) else 200
        return jsonify(res), code
    except Exception as error:
        return jsonify({"message": str(error), "status": 400}), 400
