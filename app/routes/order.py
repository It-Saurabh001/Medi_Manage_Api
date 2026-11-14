"""Orders and sales under API_PREFIX (Part 2 domain).

Replaces /user/createOrder, /admin/getAllOrders, /admin/user/getOrdersByUserId, /admin/user/orderById,
/admin/updateOrder, /admin/approveOrder, /admin/deleteOrder (hard delete removed) and the sell-history
routes formerly in admin.py (/admin/recordSell, /admin/getSellHistory, ...).
"""
from flask import request, url_for

from app.db import db_connection, get_db
from app.errors import NotFoundError, ValidationError
from app.services import order_service as osvc
from app.services import product_service
from app.services import stock_service
from app.services.audit_service import write_audit
from app.utils.api_blueprint import ApiBlueprint
from app.utils.decorators import current_identity, role_required
from app.utils.idempotency import idempotent
from app.utils.pagination import parse_pagination
from app.utils.responses import api_response, paginated_response
from app.utils.uploads import upload_file
from app.utils.validators import Validator, request_payload

order_bp = ApiBlueprint("order", __name__)

ANY_ROLE = ["admin", "user"]
ADMIN = ["admin"]
USER = ["user"]
PRESCRIPTION_MIME = ("image/jpeg", "image/png", "image/webp", "application/pdf")
PRESCRIPTION_FOLDER = "MediAdminApp/Prescriptions"


# ------------------------------------------------------------------ helpers
def _owner_scope():
    """(identity, role, owner_id): owner_id is the caller for users, None for admins."""
    identity, role = current_identity()
    return identity, role, (None if role == "admin" else identity)


def _order_json(conn, order_id):
    return osvc.serialize_order(osvc.fetch_order(conn, order_id))


def _order_list_filters(args, allow_user_filter):
    v = Validator(args.to_dict())
    v.enum("status", osvc.STATUSES)
    v.string("product_id", max_len=64)
    v.iso_date("from")
    v.iso_date("to")
    v.iso_datetime("updated_since")
    if allow_user_filter:
        v.string("user_id", max_len=64)
    filters = v.validate("Invalid query parameters")
    return {k: val for k, val in filters.items() if val not in ("", None)}


def _orders_page(filters):
    limit, offset, sort, order = parse_pagination(request.args, osvc.ORDER_SORT, default_sort="created_at",
                                                  default_order="desc")
    conn = get_db()
    try:
        rows, total = osvc.list_orders(conn, filters, limit, offset, sort, order)
    finally:
        conn.close()
    return paginated_response([osvc.serialize_order(r) for r in rows], limit, offset, total,
                              "Orders fetched successfully")


def _upload_prescription(field="prescription"):
    file = request.files.get(field)
    if file is None or not file.filename:
        return None
    # upload_file validates MIME allow-list, magic bytes and MAX_UPLOAD_MB; the client filename is never used.
    return upload_file(file, PRESCRIPTION_FOLDER, field=field, allowed_mime=PRESCRIPTION_MIME)


def _https_url(value):
    return isinstance(value, str) and value.lower().startswith(("https://", "http://")) and len(value) <= 1000


# ------------------------------------------------------------------ orders: read
@order_bp.get("/orders")
@role_required(ANY_ROLE)
def list_orders():
    _, role, owner = _owner_scope()
    filters = _order_list_filters(request.args, allow_user_filter=role == "admin")
    if owner is not None:
        filters["user_id"] = owner
    return _orders_page(filters)


@order_bp.get("/users/<user_id>/orders")
@role_required(ANY_ROLE)
def list_user_orders(user_id):
    _, _, owner = _owner_scope()
    if owner is not None and owner != user_id:
        raise NotFoundError("User not found")
    filters = _order_list_filters(request.args, allow_user_filter=False)
    filters["user_id"] = user_id
    return _orders_page(filters)


@order_bp.get("/orders/<order_id>")
@role_required(ANY_ROLE)
def get_order(order_id):
    _, _, owner = _owner_scope()
    conn = get_db()
    try:
        row = osvc.fetch_order(conn, order_id, owner_id=owner)
        data = osvc.serialize_order(row)
        data["sales"] = [osvc.serialize_sale(s) for s in osvc.sales_for_order(conn, order_id)]
    finally:
        conn.close()
    return api_response(data, "Order fetched successfully")


@order_bp.get("/orders/<order_id>/invoice")
@role_required(ANY_ROLE)
def get_invoice(order_id):
    _, _, owner = _owner_scope()
    conn = get_db()
    try:
        invoice = osvc.build_invoice(conn, osvc.fetch_order(conn, order_id, owner_id=owner))
    finally:
        conn.close()
    return api_response(invoice, "Invoice generated")


# ------------------------------------------------------------------ orders: create / edit
@order_bp.post("/orders")
@role_required(USER)
@idempotent
def create_order():
    payload = request_payload()
    v = Validator(payload)
    v.string("product_id", required=True, max_len=64)
    v.integer("quantity", required=True, min_value=1, max_value=1000)
    v.string("message", default="", max_len=1000)
    v.string("doctor_name", default="", max_len=200)
    v.string("patient_name", default="", max_len=200)
    v.string("prescription_url", default="", max_len=1000)
    cleaned = v.validate()
    if cleaned["prescription_url"] and not _https_url(cleaned["prescription_url"]):
        raise ValidationError(fields={"prescription_url": "must be an http(s) URL"})
    identity, role = current_identity()  # client-supplied user_id is ignored

    conn = get_db()
    try:
        user = osvc.fetch_customer(conn, identity)
        osvc.ensure_customer_can_order(user)
        product = product_service.fetch_product(conn, cleaned["product_id"])
    finally:
        conn.close()
    pjson = product_service.serialize_product(product)
    if not pjson["is_active"]:
        raise osvc.ConflictError("Product is not available", fields={"product_id": "inactive product"})
    rx_required = pjson["requires_prescription"] or pjson["schedule_type"] in product_service.RX_SCHEDULES
    has_file = bool(request.files.get("prescription") and request.files["prescription"].filename)
    if rx_required:
        missing = {}
        if not cleaned["prescription_url"] and not has_file:
            missing["prescription_url"] = "required for this product (or upload 'prescription')"
        if not cleaned["doctor_name"]:
            missing["doctor_name"] = "required for this product"
        if missing:
            raise osvc.PrescriptionRequired(fields=missing)
    if cleaned["quantity"] > pjson["sellable_stock"]:
        raise stock_service.OutOfStock(f"Only {pjson['sellable_stock']} unit(s) available",
                                       fields={"quantity": f"available: {pjson['sellable_stock']}"})
    if has_file:
        cleaned["prescription_url"] = _upload_prescription()

    with db_connection(immediate=True) as conn:
        user = osvc.fetch_customer(conn, identity)
        osvc.ensure_customer_can_order(user)
        product = product_service.fetch_product(conn, cleaned["product_id"])
        order_id = osvc.insert_order(conn, user, product, cleaned["quantity"], cleaned)
        write_audit(conn, identity, role, "order.create", "order", order_id,
                    {"product_id": cleaned["product_id"], "quantity": cleaned["quantity"]})
        data = _order_json(conn, order_id)
    location = url_for("order.get_order", order_id=order_id, _external=True)
    return api_response(data, "Order placed", 201, headers={"Location": location})


@order_bp.patch("/orders/<order_id>")
@role_required(ANY_ROLE)
def update_order(order_id):
    payload = request_payload()
    identity, role, owner = _owner_scope()
    v = Validator(payload, partial=True)
    v.string("patient_name", max_len=200)
    v.string("doctor_name", max_len=200)
    for field in osvc.SERVER_COMPUTED:
        v.reject(field, "cannot be changed by clients")
    cleaned = v.validate()
    if not cleaned:
        raise ValidationError("No updatable fields supplied")
    with db_connection(immediate=True) as conn:
        row = osvc.fetch_order(conn, order_id, owner_id=owner)
        if osvc.order_status(row) != "pending":
            raise osvc.InvalidTransition("Order can only be edited while pending")
        osvc.set_order_fields(conn, order_id, **cleaned)
        write_audit(conn, identity, role, "order.update", "order", order_id,
                    {k: {"from": row[k], "to": val} for k, val in cleaned.items()})
        data = _order_json(conn, order_id)
    return api_response(data, "Order updated")


@order_bp.post("/orders/<order_id>/prescription")
@role_required(ANY_ROLE)
def upload_prescription(order_id):
    identity, role, owner = _owner_scope()
    if not request.mimetype == "multipart/form-data":
        raise osvc.ApiError("Use multipart/form-data with a 'prescription' file", 415, "UNSUPPORTED_MEDIA_TYPE")
    v = Validator(request.form.to_dict(), partial=True)
    v.string("doctor_name", max_len=200)
    v.string("patient_name", max_len=200)
    cleaned = v.validate()
    conn = get_db()
    try:
        row = osvc.fetch_order(conn, order_id, owner_id=owner)
    finally:
        conn.close()
    if osvc.order_status(row) not in ("pending", "approved"):
        raise osvc.InvalidTransition("Prescription can only be attached before the sale")
    url = _upload_prescription()
    if url is None:
        raise ValidationError(fields={"prescription": "file is required"})
    with db_connection(immediate=True) as conn:
        row = osvc.fetch_order(conn, order_id, owner_id=owner)
        if osvc.order_status(row) not in ("pending", "approved"):
            raise osvc.InvalidTransition("Prescription can only be attached before the sale")
        osvc.set_order_fields(conn, order_id, prescription_url=url, prescription_verified=0, **cleaned)
        write_audit(conn, identity, role, "order.prescription_upload", "order", order_id, {"prescription_url": url})
        data = _order_json(conn, order_id)
    return api_response(data, "Prescription uploaded")


# ------------------------------------------------------------------ orders: status actions
def _reason(default):
    v = Validator(request_payload())
    v.string("reason", default=default, max_len=255)
    return v.validate()["reason"] or default


@order_bp.post("/orders/<order_id>/approve")
@role_required(ADMIN)
def approve_order(order_id):
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        row = osvc.fetch_order(conn, order_id)
        target = osvc.require_transition(row, "approve")
        osvc.set_order_fields(conn, order_id, status=target, isApproved=1)
        write_audit(conn, identity, role, "order.approve", "order", order_id, {"from": osvc.order_status(row)})
        data = _order_json(conn, order_id)
    return api_response(data, "Order approved")


def _cancel(order_id, action, reason):
    identity, role, owner = _owner_scope()
    with db_connection(immediate=True) as conn:
        row = osvc.fetch_order(conn, order_id, owner_id=owner)
        current = osvc.order_status(row)
        if owner is not None and current not in osvc.USER_CANCELLABLE:
            raise osvc.InvalidTransition(f"Only pending orders can be cancelled (order is {current})")
        target = osvc.require_transition(row, action)
        restocked = osvc.restock_deducted(conn, order_id, identity)
        osvc.set_order_fields(conn, order_id, status=target, isApproved=0, cancel_reason=reason)
        write_audit(conn, identity, role, f"order.{action}", "order", order_id,
                    {"from": current, "reason": reason, "restocked": restocked})
        data = _order_json(conn, order_id)
    data["restocked"] = restocked
    return data


@order_bp.post("/orders/<order_id>/cancel")
@role_required(ANY_ROLE)
def cancel_order(order_id):
    v = Validator(request_payload())
    v.string("cancel_reason", default="", max_len=255)
    v.string("reason", default="", max_len=255)
    cleaned = v.validate()
    reason = cleaned["cancel_reason"] or cleaned["reason"] or "Cancelled"
    return api_response(_cancel(order_id, "cancel", reason), "Order cancelled")


@order_bp.post("/orders/<order_id>/reject")
@role_required(ADMIN)
def reject_order(order_id):
    reason = _reason("Rejected by pharmacy")
    return api_response(_cancel(order_id, "reject", f"Rejected: {reason}"), "Order rejected")


@order_bp.post("/orders/<order_id>/verify-prescription")
@role_required(ADMIN)
def verify_prescription(order_id):
    v = Validator(request_payload())
    v.boolean("verified", default=True)
    verified = v.validate()["verified"]
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        row = osvc.fetch_order(conn, order_id)
        if osvc.order_status(row) not in ("pending", "approved"):
            raise osvc.InvalidTransition("Prescription can only be verified before the sale")
        if verified and not row["prescription_url"]:
            raise osvc.PrescriptionRequired("No prescription attached to this order")
        osvc.set_order_fields(conn, order_id, prescription_verified=1 if verified else 0)
        write_audit(conn, identity, role, "order.verify_prescription", "order", order_id, {"verified": verified})
        data = _order_json(conn, order_id)
    return api_response(data, "Prescription verified" if verified else "Prescription marked unverified")


@order_bp.post("/orders/<order_id>/sell")
@role_required(ADMIN)
@idempotent
def sell_order(order_id):
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:  # single transaction: any failure rolls everything back
        row = osvc.fetch_order(conn, order_id)
        sales = osvc.sell_order(conn, row, identity)
        sale_json = [osvc.serialize_sale(s) for s in sales]
        write_audit(conn, identity, role, "order.sell", "order", order_id,
                    {"allocations": [{"batch_id": s["batch_id"], "qty": s["quantity"]} for s in sale_json]})
        data = _order_json(conn, order_id)
    data["sales"] = sale_json
    return api_response(data, "Order sold")


@order_bp.post("/orders/<order_id>/return")
@role_required(ADMIN)
def return_order(order_id):
    reason = _reason("Returned")
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        row = osvc.fetch_order(conn, order_id)
        restocked, not_restocked = osvc.return_order(conn, row, identity)
        osvc.set_order_fields(conn, order_id, status="returned", cancel_reason=reason)
        write_audit(conn, identity, role, "order.return", "order", order_id,
                    {"reason": reason, "restocked": restocked, "not_restocked": not_restocked})
        data = _order_json(conn, order_id)
    data["restocked"] = restocked
    data["not_restocked"] = not_restocked
    return api_response(data, "Order returned")


# ------------------------------------------------------------------ sales
@order_bp.get("/sales")
@role_required(ADMIN)
def list_sales():
    v = Validator(request.args.to_dict())
    v.iso_date("from")
    v.iso_date("to")
    v.iso_datetime("updated_since")
    for key in ("product_id", "user_id", "order_id", "batch_id"):
        v.string(key, max_len=64)
    filters = {k: val for k, val in v.validate("Invalid query parameters").items() if val not in ("", None)}
    limit, offset, sort, order = parse_pagination(request.args, osvc.SALE_SORT, default_sort="sold_at",
                                                  default_order="desc")
    conn = get_db()
    try:
        rows, total = osvc.list_sales(conn, filters, limit, offset, sort, order)
    finally:
        conn.close()
    return paginated_response([osvc.serialize_sale(r) for r in rows], limit, offset, total,
                              "Sales fetched successfully")
