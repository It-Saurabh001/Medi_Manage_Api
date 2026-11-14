"""OpenAPI fragment: suppliers (Part 2)."""
from app.openapi._common import ADMIN, LOCATION, PAGINATION, envelope, err, ok, op, p, paged, q, ref, sort

SCHEMAS = {
    "Supplier": {"type": "object", "properties": {
        "supplier_id": {"type": "string"}, "name": {"type": "string"}, "contact_phone": {"type": "string"},
        "email": {"type": "string"}, "gst_number": {"type": "string"}, "address": {"type": "string"},
        "is_active": {"type": "boolean"}, "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"}}},
    "SupplierInput": {"type": "object", "required": ["name"], "properties": {
        "name": {"type": "string", "maxLength": 200}, "contact_phone": {"type": "string"},
        "email": {"type": "string", "format": "email"}, "gst_number": {"type": "string", "description": "15-char GSTIN"},
        "address": {"type": "string"}}},
}

PATHS = {
    "/suppliers": {
        "get": op("Suppliers", "List suppliers", ADMIN, {**ok(paged(ref("Supplier"))), "400": err("VALIDATION_ERROR")},
                  [q("q", {"type": "string"}), q("is_active", {"type": "boolean"}),
                   sort(["name", "created_at", "updated_at"], "name")] + PAGINATION),
        "post": op("Suppliers", "Create supplier", ADMIN,
                   {**ok(envelope(ref("Supplier")), "Created", "201", LOCATION), "400": err("VALIDATION_ERROR"),
                    "409": err("CONFLICT")}, body=ref("SupplierInput")),
    },
    "/suppliers/{supplier_id}": {
        "get": op("Suppliers", "Get supplier", ADMIN, {**ok(envelope(ref("Supplier"))), "404": err("NOT_FOUND")},
                  [p("supplier_id")]),
        "patch": op("Suppliers", "Partially update supplier", ADMIN,
                    {**ok(envelope(ref("Supplier"))), "400": err("VALIDATION_ERROR"), "404": err("NOT_FOUND"),
                     "409": err("CONFLICT")}, [p("supplier_id")], body=ref("SupplierInput")),
    },
    "/suppliers/{supplier_id}/deactivate": {
        "post": op("Suppliers", "Soft-deactivate supplier", ADMIN,
                   {**ok(envelope(ref("Supplier"))), "404": err("NOT_FOUND"), "409": err("CONFLICT")},
                   [p("supplier_id")]),
    },
}
