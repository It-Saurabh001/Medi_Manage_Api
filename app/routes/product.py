"""Product catalogue endpoints under API_PREFIX (Part 1 domain).

Replaces the legacy /admin/addProduct, /admin/user/getAllProducts, /admin/user/getSpecificProduct,
/admin/updateProduct and /admin/deleteProduct routes (hard delete removed: soft-deactivate only).
"""
from flask import request, url_for

from app.db import db_connection, get_db
from app.errors import ConflictError, ValidationError
from app.services import product_service as ps
from app.services.audit_service import write_audit
from app.utils.api_blueprint import ApiBlueprint
from app.utils.decorators import current_identity, role_required
from app.utils.pagination import parse_pagination
from app.utils.responses import api_response, paginated_response
from app.utils.uploads import IMAGE_MIME, upload_file
from app.utils.validators import Validator, request_payload

product_bp = ApiBlueprint("product", __name__)

ANY_ROLE = ["admin", "user"]
ADMIN = ["admin"]
PRODUCT_IMAGE_FOLDER = "MediAdminApp/Products"


def _read_conn():
    conn = get_db()
    return conn


def _list_filters(args, is_admin):
    v = Validator(args.to_dict())
    v.string("q", max_len=100)
    v.string("category", max_len=100)
    v.enum("schedule_type", ps.SCHEDULE_TYPES)
    v.boolean("requires_prescription")
    v.boolean("in_stock")
    v.iso_datetime("updated_since")
    if is_admin:
        v.boolean("is_active")
    filters = v.validate("Invalid query parameters")
    if not is_admin:
        filters["is_active"] = True  # users only ever see active products
    return {k: val for k, val in filters.items() if val not in ("", None) or k in ("is_active",)}


def _uploaded_image():
    file = request.files.get("image")
    if file is None or not file.filename:
        return None
    return upload_file(file, PRODUCT_IMAGE_FOLDER, field="image", allowed_mime=IMAGE_MIME)


@product_bp.get("/products")
@role_required(ANY_ROLE)
def list_products():
    _, role = current_identity()
    is_admin = role == "admin"
    filters = _list_filters(request.args, is_admin)
    limit, offset, sort, order = parse_pagination(request.args, ps.SORT_COLUMNS, default_sort="name")
    conn = _read_conn()
    try:
        rows, total = ps.list_products(conn, filters, limit, offset, sort, order)
    finally:
        conn.close()
    data = [ps.serialize_product(r, include_cost=is_admin) for r in rows]
    return paginated_response(data, limit, offset, total, "Products fetched successfully")


@product_bp.post("/products")
@role_required(ADMIN)
def create_product():
    payload = request_payload()
    v = ps.build_product_validator(payload)
    ps.apply_product_rules(v)
    cleaned = v.validate()
    actor_id, role = current_identity()

    with db_connection(immediate=True) as conn:
        ps.ensure_barcode_unique(conn, cleaned.get("barcode"))
    image_url = _uploaded_image()  # network call kept outside the write transaction
    if image_url:
        cleaned["image_url"] = image_url

    with db_connection(immediate=True) as conn:
        ps.ensure_barcode_unique(conn, cleaned.get("barcode"))
        product_id = ps.insert_product(conn, cleaned)
        write_audit(conn, actor_id, role, "product.create", "product", product_id, cleaned)
        product = ps.serialize_product(ps.fetch_product(conn, product_id), include_cost=True)

    location = url_for("product.get_product", product_id=product_id, _external=True)
    return api_response(product, "Product created", 201, headers={"Location": location})


@product_bp.get("/products/<product_id>")
@role_required(ANY_ROLE)
def get_product(product_id):
    _, role = current_identity()
    conn = _read_conn()
    try:
        row = ps.fetch_product(conn, product_id, active_only=role != "admin")
    finally:
        conn.close()
    return api_response(ps.serialize_product(row, include_cost=role == "admin"), "Product fetched successfully")


@product_bp.patch("/products/<product_id>")
@role_required(ADMIN)
def update_product(product_id):
    payload = request_payload()
    actor_id, role = current_identity()
    conn = _read_conn()
    try:
        current = dict(ps.fetch_product(conn, product_id))
    finally:
        conn.close()

    v = ps.build_product_validator(payload, partial=True)
    ps.apply_product_rules(v, current)
    cleaned = v.validate()
    has_image = bool(request.files.get("image") and request.files["image"].filename)
    if not cleaned and not has_image:
        raise ValidationError("No updatable fields supplied")

    with db_connection(immediate=True) as conn:
        ps.ensure_barcode_unique(conn, cleaned.get("barcode"), exclude_product_id=product_id)
    if has_image:
        cleaned["image_url"] = _uploaded_image()

    with db_connection(immediate=True) as conn:
        ps.fetch_product(conn, product_id)
        ps.ensure_barcode_unique(conn, cleaned.get("barcode"), exclude_product_id=product_id)
        ps.update_product_fields(conn, product_id, cleaned)
        changes = {k: {"from": current.get(ps.WRITABLE_COLUMNS[k]), "to": val} for k, val in cleaned.items()}
        write_audit(conn, actor_id, role, "product.update", "product", product_id, changes)
        product = ps.serialize_product(ps.fetch_product(conn, product_id), include_cost=True)
    return api_response(product, "Product updated")


@product_bp.get("/products/by-barcode/<barcode>")
@role_required(ANY_ROLE)
def get_product_by_barcode(barcode):
    _, role = current_identity()
    conn = _read_conn()
    try:
        row = ps.fetch_product_by_barcode(conn, barcode.strip(), active_only=role != "admin")
    finally:
        conn.close()
    return api_response(ps.serialize_product(row, include_cost=role == "admin"), "Product fetched successfully")


def _set_active(product_id, active):
    actor_id, role = current_identity()
    with db_connection(immediate=True) as conn:
        row = ps.fetch_product(conn, product_id)
        if bool(row["is_active"] if row["is_active"] is not None else 1) == active:
            raise ConflictError(f"Product is already {'active' if active else 'inactive'}")
        ps.set_product_active(conn, product_id, active)
        write_audit(conn, actor_id, role, "product.reactivate" if active else "product.deactivate",
                    "product", product_id, {"is_active": active})
        product = ps.serialize_product(ps.fetch_product(conn, product_id), include_cost=True)
    return api_response(product, "Product reactivated" if active else "Product deactivated")


@product_bp.post("/products/<product_id>/deactivate")
@role_required(ADMIN)
def deactivate_product(product_id):
    return _set_active(product_id, False)


@product_bp.post("/products/<product_id>/reactivate")
@role_required(ADMIN)
def reactivate_product(product_id):
    return _set_active(product_id, True)


@product_bp.get("/product-categories")
@role_required(ANY_ROLE)
def list_product_categories():
    _, role = current_identity()
    limit, offset, sort, order = parse_pagination(request.args, ("name", "product_count"), default_sort="name")
    conn = _read_conn()
    try:
        data, total = ps.list_categories(conn, role != "admin", limit, offset, sort, order)
    finally:
        conn.close()
    return paginated_response(data, limit, offset, total, "Categories fetched successfully")
