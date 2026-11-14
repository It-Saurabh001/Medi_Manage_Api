"""Supplier endpoints under API_PREFIX (admin only, Part 2 domain)."""
from flask import request, url_for

from app.db import db_connection, get_db
from app.errors import ConflictError, ValidationError
from app.services import supplier_service as svc
from app.services.audit_service import write_audit
from app.utils.api_blueprint import ApiBlueprint
from app.utils.decorators import current_identity, role_required
from app.utils.pagination import parse_pagination
from app.utils.responses import api_response, paginated_response
from app.utils.validators import Validator, request_payload

supplier_bp = ApiBlueprint("supplier", __name__)
ADMIN = ["admin"]


@supplier_bp.get("/suppliers")
@role_required(ADMIN)
def list_suppliers():
    v = Validator(request.args.to_dict())
    v.string("q", max_len=100)
    v.boolean("is_active")
    filters = {k: val for k, val in v.validate("Invalid query parameters").items() if val != ""}
    limit, offset, sort, order = parse_pagination(request.args, svc.SORT_COLUMNS, default_sort="name")
    conn = get_db()
    try:
        rows, total = svc.list_suppliers(conn, filters, limit, offset, sort, order)
    finally:
        conn.close()
    return paginated_response([svc.serialize_supplier(r) for r in rows], limit, offset, total,
                              "Suppliers fetched successfully")


@supplier_bp.post("/suppliers")
@role_required(ADMIN)
def create_supplier():
    cleaned = svc.build_validator(request_payload()).validate()
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        svc.ensure_gst_unique(conn, cleaned.get("gst_number"))
        supplier_id = svc.insert(conn, cleaned)
        write_audit(conn, identity, role, "supplier.create", "supplier", supplier_id, cleaned)
        data = svc.serialize_supplier(svc.fetch(conn, supplier_id))
    location = url_for("supplier.get_supplier", supplier_id=supplier_id, _external=True)
    return api_response(data, "Supplier created", 201, headers={"Location": location})


@supplier_bp.get("/suppliers/<supplier_id>")
@role_required(ADMIN)
def get_supplier(supplier_id):
    conn = get_db()
    try:
        data = svc.serialize_supplier(svc.fetch(conn, supplier_id))
    finally:
        conn.close()
    return api_response(data, "Supplier fetched successfully")


@supplier_bp.patch("/suppliers/<supplier_id>")
@role_required(ADMIN)
def update_supplier(supplier_id):
    cleaned = svc.build_validator(request_payload(), partial=True).validate()
    if not cleaned:
        raise ValidationError("No updatable fields supplied")
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        current = svc.fetch(conn, supplier_id)
        svc.ensure_gst_unique(conn, cleaned.get("gst_number"), exclude_id=supplier_id)
        svc.update(conn, supplier_id, cleaned)
        write_audit(conn, identity, role, "supplier.update", "supplier", supplier_id,
                    {k: {"from": current[k], "to": val} for k, val in cleaned.items()})
        data = svc.serialize_supplier(svc.fetch(conn, supplier_id))
    return api_response(data, "Supplier updated")


@supplier_bp.post("/suppliers/<supplier_id>/deactivate")
@role_required(ADMIN)
def deactivate_supplier(supplier_id):
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        row = svc.fetch(conn, supplier_id)
        if not row["is_active"]:
            raise ConflictError("Supplier is already inactive")
        svc.set_active(conn, supplier_id, False)
        write_audit(conn, identity, role, "supplier.deactivate", "supplier", supplier_id, {"is_active": False})
        data = svc.serialize_supplier(svc.fetch(conn, supplier_id))
    return api_response(data, "Supplier deactivated")
