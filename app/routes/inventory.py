"""Batches, stock movements and inventory alerts under API_PREFIX (admin only, Part 1 domain)."""
import uuid

from flask import current_app, request, url_for

from app.db import db_connection, get_db
from app.errors import ConflictError, NotFoundError, ValidationError
from app.services import inventory_service as inv
from app.services import product_service as ps
from app.services import stock_service
from app.services.audit_service import write_audit
from app.utils.api_blueprint import ApiBlueprint
from app.utils.decorators import current_identity, role_required
from app.utils.idempotency import idempotent
from app.utils.pagination import parse_pagination
from app.utils.responses import api_response, paginated_response
from app.utils.timeutil import utc_today
from app.utils.validators import Validator, parse_iso_date, parse_iso_datetime_z, request_payload

inventory_bp = ApiBlueprint("inventory", __name__)
ADMIN = ["admin"]


# ------------------------------------------------------------------ helpers
def _batch_validator(data, partial=False, require_quantity=False):
    v = Validator(data, partial=partial)
    v.string("batch_no", required=True, min_len=1, max_len=64)
    v.iso_date("expiry_date", required=True)
    v.iso_date("mfg_date")
    v.iso_date("received_date")
    v.number("purchase_price", min_value=0)
    v.number("mrp", min_value=0)
    v.string("supplier_id", max_len=64)
    v.string("supplier_name", max_len=200)
    if require_quantity:
        v.integer("quantity", required=True, min_value=1)
    elif not partial:
        v.integer("quantity", default=0, min_value=0)
    return v


def _check_dates(v, current=None):
    merged = dict(current or {})
    merged.update(v.cleaned)
    mfg, expiry, received = merged.get("mfg_date"), merged.get("expiry_date"), merged.get("received_date")
    if mfg and mfg > utc_today():
        v.error("mfg_date", "cannot be in the future")
    if mfg and expiry and expiry <= mfg:
        v.error("expiry_date", "must be after mfg_date")
    if received and received > utc_today():
        v.error("received_date", "cannot be in the future")
    return v


def _resolve_supplier(conn, cleaned):
    supplier_id = cleaned.get("supplier_id")
    if supplier_id:
        supplier = inv.fetch_supplier(conn, supplier_id)
        if not cleaned.get("supplier_name"):
            cleaned["supplier_name"] = supplier["name"]
    elif "supplier_id" in cleaned:
        cleaned["supplier_id"] = None


def _batch_json(conn, batch_id):
    return inv.serialize_batch(inv.fetch_batch(conn, batch_id))


def _batch_location(batch_id):
    return url_for("inventory.get_batch", batch_id=batch_id, _external=True)


# ------------------------------------------------------------------ batches
@inventory_bp.get("/products/<product_id>/batches")
@role_required(ADMIN)
def list_product_batches(product_id):
    v = Validator(request.args.to_dict())
    v.boolean("include_expired", default=True)
    v.boolean("in_stock")
    filters = v.validate("Invalid query parameters")
    limit, offset, sort, order = parse_pagination(request.args, inv.BATCH_SORT, default_sort="expiry_date")
    conn = get_db()
    try:
        ps.fetch_product(conn, product_id)
        rows, total = inv.list_batches(conn, product_id, filters, limit, offset, sort, order)
    finally:
        conn.close()
    return paginated_response([inv.serialize_batch(r) for r in rows], limit, offset, total,
                              "Batches fetched successfully")


@inventory_bp.post("/products/<product_id>/batches")
@role_required(ADMIN)
def create_batch(product_id):
    v = _check_dates(_batch_validator(request_payload()))
    cleaned = v.validate()
    if cleaned["expiry_date"] < utc_today() and cleaned.get("quantity", 0) > 0:
        raise stock_service.BatchExpired("Cannot add stock to an already expired batch",
                                         fields={"expiry_date": "is in the past"})
    actor_id, role = current_identity()
    with db_connection(immediate=True) as conn:
        product = ps.fetch_product(conn, product_id)
        cleaned.setdefault("purchase_price", ps._num(product["purchase_price"]) or 0.0)
        cleaned.setdefault("mrp", ps._num(product["mrp"]) or 0.0)
        _resolve_supplier(conn, cleaned)
        batch_id = inv.insert_batch(conn, product_id, cleaned)
        movement = None
        if cleaned.get("quantity", 0) > 0:
            movement = stock_service.apply_stock_change(
                conn, product_id, batch_id, cleaned["quantity"], "PURCHASE", batch_id, actor_id)
        write_audit(conn, actor_id, role, "batch.create", "batch", batch_id,
                    {"product_id": product_id, **cleaned})
        batch = _batch_json(conn, batch_id)
    return api_response({"batch": batch, "movement": movement}, "Batch created", 201,
                        headers={"Location": _batch_location(batch_id)})


@inventory_bp.get("/batches/<batch_id>")
@role_required(ADMIN)
def get_batch(batch_id):
    conn = get_db()
    try:
        batch = _batch_json(conn, batch_id)
    finally:
        conn.close()
    return api_response(batch, "Batch fetched successfully")


@inventory_bp.patch("/batches/<batch_id>")
@role_required(ADMIN)
def update_batch(batch_id):
    payload = request_payload()
    actor_id, role = current_identity()
    v = _batch_validator(payload, partial=True)
    v.reject("quantity", "quantity changes must use stock/adjust, stock/purchase or write-off")
    v.reject("is_legacy_placeholder", "cleared automatically when expiry_date is corrected")
    v.reject("product_id", "cannot be changed")

    with db_connection(immediate=True) as conn:
        current = dict(inv.fetch_batch(conn, batch_id))
        _check_dates(v, current)
        cleaned = v.validate()
        if not cleaned:
            raise ValidationError("No updatable fields supplied")
        if "batch_no" in cleaned and cleaned["batch_no"] != current["batch_no"]:
            if inv.fetch_batch_by_no(conn, current["Product_id"], cleaned["batch_no"]) is not None:
                raise ConflictError("Batch number already exists for this product", fields={"batch_no": "already exists"})
        _resolve_supplier(conn, cleaned)
        clear_legacy = bool(current["is_legacy_placeholder"]) and \
            cleaned.get("expiry_date", current["expiry_date"]) != inv.LEGACY_EXPIRY
        inv.update_batch_fields(conn, batch_id, cleaned, clear_legacy_flag=clear_legacy)
        changes = {k: {"from": current.get(k), "to": val} for k, val in cleaned.items()}
        write_audit(conn, actor_id, role, "batch.update", "batch", batch_id, changes)
        batch = _batch_json(conn, batch_id)
    return api_response(batch, "Batch updated")


@inventory_bp.post("/batches/<batch_id>/write-off")
@role_required(ADMIN)
def write_off_batch(batch_id):
    v = Validator(request_payload())
    v.string("note", default="", max_len=255)
    cleaned = v.validate()
    actor_id, role = current_identity()
    with db_connection(immediate=True) as conn:
        batch = inv.fetch_batch(conn, batch_id)
        qty = int(batch["quantity"] or 0)
        if qty <= 0:
            raise ConflictError("Batch has no stock to write off")
        reference = "WOFF_" + uuid.uuid4().hex[:10]
        movement = stock_service.apply_stock_change(
            conn, batch["Product_id"], batch_id, -qty, "EXPIRED_WRITEOFF", reference, actor_id)
        write_audit(conn, actor_id, role, "batch.write_off", "batch", batch_id,
                    {"quantity": qty, "reference_id": reference, "note": cleaned["note"],
                     "expiry_date": batch["expiry_date"]})
        result = {"batch": _batch_json(conn, batch_id), "movement": movement}
    return api_response(result, "Batch written off")


# ------------------------------------------------------------------ stock actions
@inventory_bp.post("/products/<product_id>/stock/purchase")
@role_required(ADMIN)
@idempotent
def purchase_stock(product_id):
    v = _check_dates(_batch_validator(request_payload(), require_quantity=True))
    v.string("invoice_no", max_len=64)
    cleaned = v.validate()
    if cleaned["expiry_date"] < utc_today():
        raise stock_service.BatchExpired("Cannot purchase an already expired batch",
                                         fields={"expiry_date": "is in the past"})
    actor_id, role = current_identity()
    quantity = cleaned.pop("quantity")
    invoice_no = cleaned.pop("invoice_no", None)

    with db_connection(immediate=True) as conn:
        product = ps.fetch_product(conn, product_id)
        existing = inv.fetch_batch_by_no(conn, product_id, cleaned["batch_no"])
        if existing is not None:
            if existing["expiry_date"] != cleaned["expiry_date"]:
                raise ConflictError("Existing batch has a different expiry_date",
                                    fields={"expiry_date": f"batch {cleaned['batch_no']} expires {existing['expiry_date']}"})
            batch_id, created = existing["Batch_id"], False
        else:
            cleaned.setdefault("purchase_price", ps._num(product["purchase_price"]) or 0.0)
            cleaned.setdefault("mrp", ps._num(product["mrp"]) or 0.0)
            _resolve_supplier(conn, cleaned)
            batch_id, created = inv.insert_batch(conn, product_id, cleaned), True
        reference = invoice_no or batch_id
        movement = stock_service.apply_stock_change(
            conn, product_id, batch_id, quantity, "PURCHASE", reference, actor_id)
        write_audit(conn, actor_id, role, "stock.purchase", "product", product_id,
                    {"batch_id": batch_id, "batch_created": created, "quantity": quantity,
                     "invoice_no": invoice_no, **cleaned})
        result = {
            "batch": _batch_json(conn, batch_id),
            "movement": movement,
            "batch_created": created,
            "product_stock": movement["product_stock"],
        }
    return api_response(result, "Stock purchased", 201, headers={"Location": _batch_location(batch_id)})


@inventory_bp.post("/products/<product_id>/stock/adjust")
@role_required(ADMIN)
def adjust_stock(product_id):
    v = Validator(request_payload())
    v.string("batch_id", required=True, max_len=64)
    v.integer("change_qty", required=True)
    v.string("reason", required=True, min_len=3, max_len=255)
    cleaned = v.validate()
    if cleaned["change_qty"] == 0:
        raise ValidationError(fields={"change_qty": "must be non-zero"})
    actor_id, role = current_identity()
    with db_connection(immediate=True) as conn:
        ps.fetch_product(conn, product_id)
        batch = inv.fetch_batch(conn, cleaned["batch_id"])
        if batch["Product_id"] != product_id:
            raise NotFoundError("Batch not found for this product", fields={"batch_id": "not a batch of this product"})
        reference = "ADJ_" + uuid.uuid4().hex[:10]
        movement = stock_service.apply_stock_change(
            conn, product_id, cleaned["batch_id"], cleaned["change_qty"], "ADJUSTMENT", reference, actor_id)
        write_audit(conn, actor_id, role, "stock.adjust", "product", product_id,
                    {"batch_id": cleaned["batch_id"], "change_qty": cleaned["change_qty"],
                     "reason": cleaned["reason"], "reference_id": reference})
        result = {"batch": _batch_json(conn, cleaned["batch_id"]), "movement": movement,
                  "product_stock": movement["product_stock"]}
    return api_response(result, "Stock adjusted")


@inventory_bp.get("/stock-movements")
@role_required(ADMIN)
def list_stock_movements():
    args = request.args.to_dict()
    v = Validator(args)
    v.string("product_id", max_len=64)
    v.string("batch_id", max_len=64)
    v.string("performed_by", max_len=64)
    v.enum("reason", stock_service.REASONS)
    filters = v.validate("Invalid query parameters")
    errors = {}
    for key, suffix in (("from", "T00:00:00Z"), ("to", "T23:59:59Z")):
        raw = args.get(key)
        if raw:
            try:
                filters[key] = parse_iso_date(raw) + suffix if len(raw.strip()) == 10 else parse_iso_datetime_z(raw)
            except ValueError as exc:
                errors[key] = str(exc)
    if errors:
        raise ValidationError("Invalid query parameters", fields=errors)
    limit, offset, sort, order = parse_pagination(request.args, inv.MOVEMENT_SORT, default_sort="created_at",
                                                  default_order="desc")
    conn = get_db()
    try:
        rows, total = inv.list_movements(conn, filters, limit, offset, sort, order)
    finally:
        conn.close()
    return paginated_response([inv.serialize_movement(r) for r in rows], limit, offset, total,
                              "Stock movements fetched successfully")


# ------------------------------------------------------------------ alerts
def _batch_alert_response(fetch, message, **kwargs):
    limit, offset, sort, order = parse_pagination(request.args, inv.ALERT_BATCH_SORT, default_sort="expiry_date")
    conn = get_db()
    try:
        rows, total = fetch(conn, limit=limit, offset=offset, sort=sort, order=order, **kwargs)
    finally:
        conn.close()
    return paginated_response([inv.serialize_batch(r) for r in rows], limit, offset, total, message)


def _product_alert_response(fetch, message):
    limit, offset, sort, order = parse_pagination(request.args, inv.ALERT_PRODUCT_SORT, default_sort="stock")
    conn = get_db()
    try:
        rows, total = fetch(conn, limit, offset, sort, order)
    finally:
        conn.close()
    return paginated_response([ps.serialize_product(r, include_cost=True) for r in rows], limit, offset, total,
                              message)


@inventory_bp.get("/inventory/near-expiry")
@role_required(ADMIN)
def near_expiry():
    v = Validator(request.args.to_dict())
    v.integer("days", default=current_app.config.get("NEAR_EXPIRY_DAYS", 90), min_value=1, max_value=3650)
    days = v.validate("Invalid query parameters")["days"]
    return _batch_alert_response(inv.near_expiry_batches, "Near-expiry batches fetched successfully", days=days)


@inventory_bp.get("/inventory/expired")
@role_required(ADMIN)
def expired():
    return _batch_alert_response(inv.expired_batches, "Expired batches fetched successfully")


@inventory_bp.get("/inventory/low-stock")
@role_required(ADMIN)
def low_stock():
    return _product_alert_response(inv.low_stock_products, "Low-stock products fetched successfully")


@inventory_bp.get("/inventory/out-of-stock")
@role_required(ADMIN)
def out_of_stock():
    return _product_alert_response(inv.out_of_stock_products, "Out-of-stock products fetched successfully")
