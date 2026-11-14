"""OpenAPI fragment: dashboard, reports, audit logs (Part 2)."""
from app.openapi._common import ADMIN, PAGINATION, envelope, err, ok, op, paged, q, sort

_RANGE = [q("from", {"type": "string", "format": "date"}, "default: today - 30 days"),
          q("to", {"type": "string", "format": "date"}, "default: today")]

SCHEMAS = {
    "DashboardSummary": {"type": "object", "properties": {
        "date": {"type": "string", "format": "date"}, "products": {"type": "integer"},
        "low_stock": {"type": "integer"}, "out_of_stock": {"type": "integer"},
        "near_expiry_batches": {"type": "integer"}, "expired_batches": {"type": "integer"},
        "pending_orders": {"type": "integer"}, "approved_orders": {"type": "integer"},
        "today_sales_total": {"type": "number", "description": "net of returned orders"},
        "today_sales_count": {"type": "integer"}, "near_expiry_days": {"type": "integer"}}},
    "SalesReportRow": {"type": "object", "properties": {
        "day": {"type": "string", "format": "date", "description": "group_by=day"},
        "product_id": {"type": "string", "description": "group_by=product"},
        "product_name": {"type": "string", "description": "group_by=product"},
        "quantity": {"type": "integer"}, "revenue": {"type": "number"}, "orders": {"type": "integer"}}},
    "TopProduct": {"type": "object", "properties": {
        "product_id": {"type": "string"}, "product_name": {"type": "string"},
        "quantity": {"type": "integer"}, "revenue": {"type": "number"}}},
    "AuditLog": {"type": "object", "properties": {
        "audit_id": {"type": "string"}, "actor_id": {"type": "string", "nullable": True},
        "actor_role": {"type": "string", "nullable": True}, "action": {"type": "string"},
        "entity": {"type": "string"}, "entity_id": {"type": "string", "nullable": True},
        "details": {"type": "object"}, "created_at": {"type": "string", "format": "date-time"}}},
}

PATHS = {
    "/dashboard/summary": {
        "get": op("Reports", "Dashboard counters", ADMIN,
                  ok(envelope({"$ref": "#/components/schemas/DashboardSummary"}))),
    },
    "/reports/sales": {
        "get": op("Reports", "Sales grouped by day or product (net of returns)", ADMIN,
                  {**ok(paged({"$ref": "#/components/schemas/SalesReportRow"}, extra={"summary": {"type": "object"}})),
                   "400": err("VALIDATION_ERROR")},
                  _RANGE + [q("group_by", {"type": "string", "enum": ["day", "product"], "default": "day"}),
                            sort(["key", "quantity", "revenue"], "key")] + PAGINATION),
    },
    "/reports/top-products": {
        "get": op("Reports", "Best-selling products", ADMIN,
                  {**ok(paged({"$ref": "#/components/schemas/TopProduct"})), "400": err("VALIDATION_ERROR")},
                  _RANGE + [sort(["quantity", "revenue"], "quantity")] + PAGINATION),
    },
    "/audit-logs": {
        "get": op("Audit", "Audit trail", ADMIN,
                  {**ok(paged({"$ref": "#/components/schemas/AuditLog"})), "400": err("VALIDATION_ERROR")},
                  [q("entity", {"type": "string"}), q("entity_id", {"type": "string"}),
                   q("actor_id", {"type": "string"}), q("action", {"type": "string"}),
                   q("from", {"type": "string"}, "date or date-time"), q("to", {"type": "string"}, "date or date-time"),
                   sort(["created_at"], "created_at")] + PAGINATION),
    },
}
