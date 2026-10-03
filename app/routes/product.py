import cloudinary.uploader
from flask import Blueprint, jsonify, request
from app.utils.decorators import role_required
from app.services.add_ops import addProduct
from app.services.read_ops import getAllProducts, getspecificproduct
from app.services.update_ops import update_product
from app.services.delete_ops import delete_Product

product_bp = Blueprint("product", __name__)

@product_bp.route("/admin/addProduct", methods=["POST"])
@role_required(["admin"])
def add_product():
    try:
        name = request.form["name"]
        price = float(request.form["price"])
        category = request.form["category"]
        stock = int(request.form["stock"])

        image_url = None
        if "image" in request.files:
            file = request.files["image"]
            if file.filename != "":
                upload_result = cloudinary.uploader.upload(file)
                image_url = upload_result.get("secure_url")

        response = addProduct(name=name, price=price, category=category, stock=stock, image_url=image_url)
        return response
    except Exception as error:
        return jsonify({"message": str(error), "status": 400})

@product_bp.route("/admin/user/getAllProducts", methods=["GET"])
@role_required(["admin", "user"])
def get_all_products():
    try:
        products = getAllProducts()
        return jsonify({"products": products, "message": "Products fetched Successfully", "status": 200})
    except Exception as error:
        return jsonify({"products": [], "message": str(error), "status": 400})

@product_bp.route("/admin/user/getSpecificProduct", methods=["POST"])
@role_required(["admin", "user"])
def get_specific_product():
    try:
        Product_id = request.form["Product_id"]
        product = getspecificproduct(Product_id=Product_id)
        return jsonify({"product": product, "message": "Product fetched Successfully", "status": 200})
    except Exception as error:
        return jsonify({"product": [], "message": str(error), "status": 400})

@product_bp.route("/admin/updateProduct", methods=["PATCH"])
@role_required(["admin"])
def update__product():
    try:
        Product_id = request.form["Product_id"]
        updateProduct = {}
        for key, value in request.form.items():
            if key != "Product_id":
                updateProduct[key] = value

        if "image" in request.files:
            file = request.files["image"]
            if file.filename != "":
                upload_result = cloudinary.uploader.upload(file, folder="MediAdminApp/Products")
                updateProduct["image_url"] = upload_result.get("secure_url")

        response = update_product(Product_id=Product_id, updateProduct=updateProduct)
        return response
    except Exception as error:
        return jsonify({"message": str(error), "status": 400})

@product_bp.route("/admin/deleteProduct", methods=["POST"])
@role_required(["admin"])
def delete_product():
    try:
        Product_id = request.form["Product_id"]
        response = delete_Product(Product_id)
        return response
    except Exception as error:
        return jsonify({"message": str(error), "status": 400})
