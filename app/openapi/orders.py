"""OpenAPI fragment: orders, invoices, sales (Part 2)."""
from app.openapi._common import (ADMIN, ANY, LOCATION, PAGINATION, USER, envelope, err, ok, op, p, paged, q,
                                 ref, sort)

_STATUSES = ["pending", "approved", "sold", "cancelled", "returned"]

SCHEMAS = {
    "Order": {"type": "object", "properties": {
        "order_id": {"type": "string"}, "user_id": {"type": "string"}, "user_name": {"type": "string"},
        "product_id": {"type": "string"}, "product_name": {"type": "string"}, "category": {"type": "string"},
        "quantity": {"type": "integer"}, "price": {"type": "number"},
        "total_amount": {"type": "number", "description": "server-computed price x quantity"},
        "status": {"type": "string", "enum": _STATUSES}, "message": {"type": "string"},
        "requires_prescription": {"type": "boolean"}, "prescription_url": {"type": "string", "nullable": True},
        "prescription_verified": {"type": "boolean"}, "doctor_name": {"type": "string"},
        "patient_name": {"type": "string"}, "cancel_reason": {"type": "string"},
        "image_url": {"type": "string", "nullable": True},
        "created_at": {"type": "string", "description": "ISO-8601 Z (legacy rows: date)"},
        "updated_at": {"type": "string", "format": "date-time", "nullable": True}}},
    "OrderInput": {"type": "object", "required": ["product_id", "quantity"], "properties": {
        "product_id": {"type": "string"}, "quantity": {"type": "integer", "minimum": 1},
        "message": {"type": "string"}, "doctor_name": {"type": "string"}, "patient_name": {"type": "string"},
        "prescription_url": {"type": "string", "format": "uri"},
        "prescription": {"type": "string", "format": "binary", "description": "multipart only"}}},
    "Sale": {"type": "object", "properties": {
        "sale_id": {"type": "string"}, "order_id": {"type": "string"},
        "order_status": {"type": "string", "nullable": True}, "product_id": {"type": "string"},
        "product_name": {"type": "string"}, "user_id": {"type": "string"}, "user_name": {"type": "string"},
        "batch_id": {"type": "string", "nullable": True}, "batch_no": {"type": "string", "nullable": True},
        "quantity": {"type": "integer"}, "price": {"type": "number"}, "total_amount": {"type": "number"},
        "gst_percent": {"type": "number", "nullable": True}, "remaining_stock": {"type": "integer", "nullable": True},
        "sold_by": {"type": "string", "nullable": True}, "image_url": {"type": "string", "nullable": True},
        "sold_at": {"type": "string"}}},
    "Invoice": {"type": "object", "properties": {
        "invoice_number": {"type": "string"}, "currency": {"type": "string"},
        "prices_include_gst": {"type": "boolean"}, "order": ref("Order"),
        "user": {"type": "object", "nullable": True}, "items": {"type": "array", "items": {"type": "object",
            "properties": {"batch_no": {"type": "string"}, "expiry_date": {"type": "string"},
                           "quantity": {"type": "integer"}, "unit_price": {"type": "number"},
                           "gst_percent": {"type": "number"}, "taxable_amount": {"type": "number"},
                           "gst_amount": {"type": "number"}, "line_total": {"type": "number"}}}},
        "subtotal": {"type": "number"}, "gst_total": {"type": "number"}, "grand_total": {"type": "number"},
        "issued_at": {"type": "string", "format": "date-time"},
        "generated_at": {"type": "string", "format": "date-time"}}},
}

_ORDER_FILTERS = [
    q("status", {"type": "string", "enum": _STATUSES}), q("product_id", {"type": "string"}),
    q("user_id", {"type": "string"}, "admin only"), q("from", {"type": "string", "format": "date"}),
    q("to", {"type": "string", "format": "date"}), q("updated_since", {"type": "string", "format": "date-time"}),
    sort(["created_at", "updated_at", "total_amount", "status"], "created_at"),
] + PAGINATION

_ORDER_OK = ok(envelope(ref("Order")))
_REASON_BODY = {"type": "object", "properties": {"reason": {"type": "string"}}}


def _action(summary, roles, codes, body=None, idempotent=False, extra=None):
    responses = {**ok(envelope(ref("Order") if extra is None else extra)), "404": err("NOT_FOUND"),
                 "409": err(*codes)}
    return {"post": op("Orders", summary, roles, responses, [p("order_id")], body=body, idempotent=idempotent)}


PATHS = {
    "/orders": {
        "get": op("Orders", "List orders (users: own only)", ANY,
                  {**ok(paged(ref("Order"))), "400": err("VALIDATION_ERROR")}, _ORDER_FILTERS),
        "post": op("Orders", "Place an order (stock is reserved only at sale)", USER,
                   {**ok(envelope(ref("Order")), "Created", "201", LOCATION),
                    "400": err("VALIDATION_ERROR", "PRESCRIPTION_REQUIRED"),
                    "403": err("ACCOUNT_BLOCKED", "ACCOUNT_NOT_APPROVED", "FORBIDDEN"), "404": err("NOT_FOUND"),
                    "409": err("OUT_OF_STOCK", "CONFLICT"), "413": err("PAYLOAD_TOO_LARGE"),
                    "415": err("UNSUPPORTED_MEDIA_TYPE")},
                   body=ref("OrderInput"), idempotent=True),
    },
    "/users/{user_id}/orders": {
        "get": op("Orders", "List a user's orders (users: own id only)", ANY,
                  {**ok(paged(ref("Order"))), "404": err("NOT_FOUND")},
                  [p("user_id")] + [x for x in _ORDER_FILTERS if x.get("name") != "user_id"]),
    },
    "/orders/{order_id}": {
        "get": op("Orders", "Get an order with its sales lines", ANY, {**_ORDER_OK, "404": err("NOT_FOUND")},
                  [p("order_id")]),
        "patch": op("Orders", "Edit patient_name / doctor_name while pending", ANY,
                    {**_ORDER_OK, "400": err("VALIDATION_ERROR"), "404": err("NOT_FOUND"),
                     "409": err("INVALID_TRANSITION")}, [p("order_id")],
                    body={"type": "object", "properties": {"patient_name": {"type": "string"},
                                                           "doctor_name": {"type": "string"}}}),
    },
    "/orders/{order_id}/invoice": {
        "get": op("Orders", "Invoice (sold/returned orders)", ANY,
                  {**ok(envelope(ref("Invoice"))), "404": err("NOT_FOUND"), "409": err("INVALID_TRANSITION")},
                  [p("order_id")]),
    },
    "/orders/{order_id}/prescription": {
        "post": op("Orders", "Upload prescription (jpeg/png/webp/pdf; size from MAX_UPLOAD_MB)", ANY,
                   {**_ORDER_OK, "400": err("VALIDATION_ERROR"), "404": err("NOT_FOUND"),
                    "409": err("INVALID_TRANSITION"), "413": err("PAYLOAD_TOO_LARGE"),
                    "415": err("UNSUPPORTED_MEDIA_TYPE")}, [p("order_id")],
                   body={"type": "object", "required": ["prescription"], "properties": {
                       "prescription": {"type": "string", "format": "binary"}, "doctor_name": {"type": "string"},
                       "patient_name": {"type": "string"}}}, multipart_only=True),
    },
    "/orders/{order_id}/approve": _action("Approve a pending order", ADMIN, ("INVALID_TRANSITION",)),
    "/orders/{order_id}/reject": _action("Reject (cancel) a pending/approved order", ADMIN, ("INVALID_TRANSITION",),
                                         body=_REASON_BODY),
    "/orders/{order_id}/cancel": _action("Cancel (users: own pending orders only); restocks if deducted", ANY,
                                         ("INVALID_TRANSITION",),
                                         body={"type": "object", "properties": {"cancel_reason": {"type": "string"}}}),
    "/orders/{order_id}/verify-prescription": _action(
        "Mark the prescription verified (or not)", ADMIN, ("INVALID_TRANSITION",),
        body={"type": "object", "properties": {"verified": {"type": "boolean", "default": True}}}),
    "/orders/{order_id}/sell": _action(
        "Sell an approved order: FEFO deduction, one sale row per batch, single transaction", ADMIN,
        ("ALREADY_SOLD", "INVALID_TRANSITION", "PRESCRIPTION_NOT_VERIFIED", "OUT_OF_STOCK"), idempotent=True),
    "/orders/{order_id}/return": _action(
        "Return a sold order; restocks each batch (expired batches reported in not_restocked)", ADMIN,
        ("INVALID_TRANSITION",), body=_REASON_BODY),
    "/sales": {
        "get": op("Sales", "Sales ledger (one row per order batch)", ADMIN,
                  {**ok(paged(ref("Sale"))), "400": err("VALIDATION_ERROR")},
                  [q("from", {"type": "string", "format": "date"}), q("to", {"type": "string", "format": "date"}),
                   q("product_id", {"type": "string"}), q("user_id", {"type": "string"}),
                   q("order_id", {"type": "string"}), q("batch_id", {"type": "string"}),
                   q("updated_since", {"type": "string", "format": "date-time"}),
                   sort(["sold_at", "total_amount", "quantity"], "sold_at")] + PAGINATION),
    },
}
