"""OpenAPI 3 fragment for the Part 1 inventory domain (products, batches, stock, alerts).

`PATHS` keys are relative to API_PREFIX (Part 3 prepends it / sets `servers`).
`SCHEMAS` holds the component schemas referenced via `#/components/schemas/...`.
"""

_BEARER = [{"bearerAuth": []}]
_ANY = "Roles: admin, user"
_ADMIN = "Roles: admin"


def _ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def _err(*codes):
    return {"description": "Error (R6 shape). Codes: " + ", ".join(codes), "content": {"application/json": {"schema": _ref("Error")}}}


def _ok(schema, description="OK", status="200", headers=None):
    resp = {"description": description, "content": {"application/json": {"schema": schema}}}
    if headers:
        resp["headers"] = headers
    return {status: resp}


def _envelope(data_schema):
    return {"type": "object", "properties": {"status": {"type": "integer"}, "message": {"type": "string"}, "data": data_schema}}


def _paged(item):
    return {"type": "object", "properties": {
        "status": {"type": "integer"}, "message": {"type": "string"},
        "data": {"type": "array", "items": item}, "pagination": _ref("Pagination")}}


_LOCATION = {"Location": {"schema": {"type": "string", "format": "uri"}, "description": "URL of the created resource"}}
_AUTH_ERRORS = {"401": _err("UNAUTHORIZED", "TOKEN_EXPIRED", "TOKEN_INVALID"), "403": _err("FORBIDDEN")}


def _q(name, schema, description=""):
    return {"name": name, "in": "query", "required": False, "schema": schema, "description": description}


def _p(name):
    return {"name": name, "in": "path", "required": True, "schema": {"type": "string"}}


_PAGINATION_PARAMS = [
    _q("limit", {"type": "integer", "default": 20, "maximum": 100}),
    _q("offset", {"type": "integer", "default": 0}),
    _q("order", {"type": "string", "enum": ["asc", "desc"]}),
]


def _sort(values, default):
    return _q("sort", {"type": "string", "enum": list(values), "default": default})


def _op(tag, summary, roles, responses, params=None, body=None, idempotent=False):
    op = {"tags": [tag], "summary": summary, "description": roles, "security": _BEARER,
          "parameters": list(params or []), "responses": {**responses, **_AUTH_ERRORS}}
    if idempotent:
        op["parameters"].append({"name": "Idempotency-Key", "in": "header", "required": False,
                                 "schema": {"type": "string", "maxLength": 255},
                                 "description": "Retries with the same key replay the first response"})
    if body:
        op["requestBody"] = {"required": True, "content": {
            "application/json": {"schema": body}, "multipart/form-data": {"schema": body}}}
    return op


SCHEMAS = {
    "Error": {"type": "object", "required": ["status", "message", "code"], "properties": {
        "status": {"type": "integer"}, "message": {"type": "string"}, "code": {"type": "string"},
        "fields": {"type": "object", "additionalProperties": {"type": "string"}}}},
    "Pagination": {"type": "object", "properties": {
        "limit": {"type": "integer"}, "offset": {"type": "integer"}, "total": {"type": "integer"}}},
    "Product": {"type": "object", "properties": {
        "product_id": {"type": "string"}, "name": {"type": "string"}, "generic_name": {"type": "string"},
        "brand_name": {"type": "string"}, "manufacturer": {"type": "string"}, "category": {"type": "string"},
        "dosage_form": {"type": "string", "enum": ["Tablet", "Capsule", "Syrup", "Injection", "Ointment", "Drops", "Other"]},
        "strength": {"type": "string"}, "pack_size": {"type": "string"}, "unit": {"type": "string"},
        "hsn_code": {"type": "string"}, "gst_percent": {"type": "number"}, "price": {"type": "number"},
        "mrp": {"type": "number"}, "purchase_price": {"type": "number", "nullable": True, "description": "null for users"},
        "schedule_type": {"type": "string", "enum": ["OTC", "H", "H1", "X", "NARCOTIC"]},
        "requires_prescription": {"type": "boolean"}, "storage_conditions": {"type": "string"},
        "reorder_level": {"type": "integer"}, "barcode": {"type": "string"},
        "image_url": {"type": "string", "nullable": True}, "stock": {"type": "integer"},
        "sellable_stock": {"type": "integer", "description": "non-expired quantity"},
        "in_stock": {"type": "boolean"}, "is_active": {"type": "boolean"},
        "created_at": {"type": "string", "format": "date-time", "nullable": True},
        "updated_at": {"type": "string", "format": "date-time", "nullable": True}}},
    "ProductInput": {"type": "object", "required": ["name", "price"], "properties": {
        "name": {"type": "string", "maxLength": 200}, "generic_name": {"type": "string"},
        "brand_name": {"type": "string"}, "manufacturer": {"type": "string"}, "category": {"type": "string"},
        "dosage_form": {"type": "string"}, "strength": {"type": "string"}, "pack_size": {"type": "string"},
        "unit": {"type": "string"}, "hsn_code": {"type": "string", "pattern": "^[0-9]{4,8}$"},
        "gst_percent": {"type": "number", "minimum": 0, "maximum": 28}, "price": {"type": "number", "minimum": 0},
        "mrp": {"type": "number", "minimum": 0}, "purchase_price": {"type": "number", "minimum": 0},
        "schedule_type": {"type": "string"}, "requires_prescription": {"type": "boolean",
            "description": "forced true for H/H1/X/NARCOTIC"},
        "storage_conditions": {"type": "string"}, "reorder_level": {"type": "integer", "minimum": 0},
        "barcode": {"type": "string"}, "image": {"type": "string", "format": "binary",
            "description": "multipart only; jpeg/png/webp"}}},
    "Batch": {"type": "object", "properties": {
        "batch_id": {"type": "string"}, "product_id": {"type": "string"},
        "product_name": {"type": "string", "nullable": True}, "batch_no": {"type": "string"},
        "mfg_date": {"type": "string", "format": "date", "nullable": True},
        "expiry_date": {"type": "string", "format": "date"}, "quantity": {"type": "integer"},
        "purchase_price": {"type": "number"}, "mrp": {"type": "number"},
        "supplier_id": {"type": "string", "nullable": True}, "supplier_name": {"type": "string"},
        "received_date": {"type": "string", "format": "date", "nullable": True},
        "is_legacy_placeholder": {"type": "boolean"}, "is_expired": {"type": "boolean"},
        "days_to_expiry": {"type": "integer", "nullable": True},
        "created_at": {"type": "string", "format": "date-time", "nullable": True},
        "updated_at": {"type": "string", "format": "date-time", "nullable": True}}},
    "BatchInput": {"type": "object", "required": ["batch_no", "expiry_date"], "properties": {
        "batch_no": {"type": "string"}, "expiry_date": {"type": "string", "format": "date"},
        "mfg_date": {"type": "string", "format": "date"}, "received_date": {"type": "string", "format": "date"},
        "quantity": {"type": "integer", "minimum": 0}, "purchase_price": {"type": "number"},
        "mrp": {"type": "number"}, "supplier_id": {"type": "string"}, "supplier_name": {"type": "string"}}},
    "PurchaseInput": {"allOf": [{"$ref": "#/components/schemas/BatchInput"}, {"type": "object",
        "required": ["quantity"], "properties": {"quantity": {"type": "integer", "minimum": 1},
                                                  "invoice_no": {"type": "string"}}}]},
    "AdjustInput": {"type": "object", "required": ["batch_id", "change_qty", "reason"], "properties": {
        "batch_id": {"type": "string"}, "change_qty": {"type": "integer", "description": "non-zero, signed"},
        "reason": {"type": "string", "minLength": 3}}},
    "Movement": {"type": "object", "properties": {
        "movement_id": {"type": "string"}, "product_id": {"type": "string"},
        "product_name": {"type": "string", "nullable": True}, "batch_id": {"type": "string", "nullable": True},
        "batch_no": {"type": "string", "nullable": True}, "change_qty": {"type": "integer"},
        "reason": {"type": "string", "enum": ["PURCHASE", "SALE", "ADJUSTMENT", "EXPIRED_WRITEOFF", "RETURN", "CANCEL_RESTOCK"]},
        "reference_id": {"type": "string"}, "performed_by": {"type": "string"},
        "created_at": {"type": "string", "format": "date-time"}}},
    "StockResult": {"type": "object", "properties": {
        "batch": {"$ref": "#/components/schemas/Batch"}, "movement": {"$ref": "#/components/schemas/Movement"},
        "product_stock": {"type": "integer"}, "batch_created": {"type": "boolean"}}},
    "Category": {"type": "object", "properties": {"name": {"type": "string"}, "product_count": {"type": "integer"}}},
}

_PRODUCT_FILTERS = [
    _q("q", {"type": "string"}, "matches name, generic_name, brand_name, barcode"),
    _q("category", {"type": "string"}),
    _q("schedule_type", {"type": "string", "enum": ["OTC", "H", "H1", "X", "NARCOTIC"]}),
    _q("requires_prescription", {"type": "boolean"}),
    _q("is_active", {"type": "boolean"}, "admin only; users always get active products"),
    _q("in_stock", {"type": "boolean"}),
    _q("updated_since", {"type": "string", "format": "date-time"}),
    _sort(["name", "price", "mrp", "stock", "created_at", "updated_at"], "name"),
] + _PAGINATION_PARAMS

_V = "400"
PATHS = {
    "/products": {
        "get": _op("Products", "List products", _ANY,
                   {**_ok(_paged(_ref("Product"))), _V: _err("VALIDATION_ERROR")}, _PRODUCT_FILTERS),
        "post": _op("Products", "Create product (stock starts at 0)", _ADMIN,
                    {**_ok(_envelope(_ref("Product")), "Created", "201", _LOCATION),
                     _V: _err("VALIDATION_ERROR"), "409": _err("CONFLICT"),
                     "413": _err("PAYLOAD_TOO_LARGE"), "415": _err("UNSUPPORTED_MEDIA_TYPE")},
                    body=_ref("ProductInput")),
    },
    "/products/{product_id}": {
        "get": _op("Products", "Get product (users: active only)", _ANY,
                   {**_ok(_envelope(_ref("Product"))), "404": _err("NOT_FOUND")}, [_p("product_id")]),
        "patch": _op("Products", "Partially update product", _ADMIN,
                     {**_ok(_envelope(_ref("Product"))), _V: _err("VALIDATION_ERROR"), "404": _err("NOT_FOUND"),
                      "409": _err("CONFLICT"), "415": _err("UNSUPPORTED_MEDIA_TYPE")},
                     [_p("product_id")], body=_ref("ProductInput")),
    },
    "/products/by-barcode/{barcode}": {
        "get": _op("Products", "Look up product by barcode", _ANY,
                   {**_ok(_envelope(_ref("Product"))), "404": _err("NOT_FOUND")}, [_p("barcode")]),
    },
    "/products/{product_id}/deactivate": {
        "post": _op("Products", "Soft-deactivate product", _ADMIN,
                    {**_ok(_envelope(_ref("Product"))), "404": _err("NOT_FOUND"), "409": _err("CONFLICT")},
                    [_p("product_id")]),
    },
    "/products/{product_id}/reactivate": {
        "post": _op("Products", "Reactivate product", _ADMIN,
                    {**_ok(_envelope(_ref("Product"))), "404": _err("NOT_FOUND"), "409": _err("CONFLICT")},
                    [_p("product_id")]),
    },
    "/product-categories": {
        "get": _op("Products", "List categories with product counts", _ANY,
                   {**_ok(_paged(_ref("Category"))), _V: _err("VALIDATION_ERROR")},
                   [_sort(["name", "product_count"], "name")] + _PAGINATION_PARAMS),
    },
    "/products/{product_id}/batches": {
        "get": _op("Batches", "List batches of a product", _ADMIN,
                   {**_ok(_paged(_ref("Batch"))), _V: _err("VALIDATION_ERROR"), "404": _err("NOT_FOUND")},
                   [_p("product_id"), _q("include_expired", {"type": "boolean", "default": True}),
                    _q("in_stock", {"type": "boolean"}),
                    _sort(["expiry_date", "batch_no", "received_date", "quantity", "created_at"], "expiry_date")]
                   + _PAGINATION_PARAMS),
        "post": _op("Batches", "Create batch (optional opening quantity -> PURCHASE movement)", _ADMIN,
                    {**_ok(_envelope(_ref("StockResult")), "Created", "201", _LOCATION),
                     _V: _err("VALIDATION_ERROR"), "404": _err("NOT_FOUND"),
                     "409": _err("CONFLICT", "BATCH_EXPIRED")},
                    [_p("product_id")], body=_ref("BatchInput")),
    },
    "/batches/{batch_id}": {
        "get": _op("Batches", "Get batch", _ADMIN, {**_ok(_envelope(_ref("Batch"))), "404": _err("NOT_FOUND")},
                   [_p("batch_id")]),
        "patch": _op("Batches", "Update batch metadata (not quantity); fixing a legacy expiry clears the placeholder flag",
                     _ADMIN, {**_ok(_envelope(_ref("Batch"))), _V: _err("VALIDATION_ERROR"),
                              "404": _err("NOT_FOUND"), "409": _err("CONFLICT")},
                     [_p("batch_id")], body=_ref("BatchInput")),
    },
    "/batches/{batch_id}/write-off": {
        "post": _op("Stock", "Write off the whole batch quantity (EXPIRED_WRITEOFF)", _ADMIN,
                    {**_ok(_envelope(_ref("StockResult"))), "404": _err("NOT_FOUND"), "409": _err("CONFLICT")},
                    [_p("batch_id")], body={"type": "object", "properties": {"note": {"type": "string"}}}),
    },
    "/products/{product_id}/stock/purchase": {
        "post": _op("Stock", "Receive stock: create or top up a batch (PURCHASE)", _ADMIN,
                    {**_ok(_envelope(_ref("StockResult")), "Created", "201", _LOCATION),
                     _V: _err("VALIDATION_ERROR"), "404": _err("NOT_FOUND"),
                     "409": _err("CONFLICT", "BATCH_EXPIRED")},
                    [_p("product_id")], body=_ref("PurchaseInput"), idempotent=True),
    },
    "/products/{product_id}/stock/adjust": {
        "post": _op("Stock", "Signed stock adjustment on one batch (never below zero)", _ADMIN,
                    {**_ok(_envelope(_ref("StockResult"))), _V: _err("VALIDATION_ERROR"),
                     "404": _err("NOT_FOUND"), "409": _err("OUT_OF_STOCK")},
                    [_p("product_id")], body=_ref("AdjustInput")),
    },
    "/stock-movements": {
        "get": _op("Stock", "Stock movement ledger", _ADMIN,
                   {**_ok(_paged(_ref("Movement"))), _V: _err("VALIDATION_ERROR")},
                   [_q("product_id", {"type": "string"}), _q("batch_id", {"type": "string"}),
                    _q("reason", {"type": "string"}), _q("performed_by", {"type": "string"}),
                    _q("from", {"type": "string"}, "date or date-time (inclusive)"),
                    _q("to", {"type": "string"}, "date or date-time (inclusive)"),
                    _sort(["created_at", "change_qty"], "created_at")] + _PAGINATION_PARAMS),
    },
    "/inventory/near-expiry": {
        "get": _op("Inventory alerts", "In-stock batches expiring within `days`", _ADMIN,
                   {**_ok(_paged(_ref("Batch"))), _V: _err("VALIDATION_ERROR")},
                   [_q("days", {"type": "integer", "default": 90, "minimum": 1}),
                    _sort(["expiry_date", "quantity", "product_name"], "expiry_date")] + _PAGINATION_PARAMS),
    },
    "/inventory/expired": {
        "get": _op("Inventory alerts", "In-stock batches past expiry", _ADMIN,
                   {**_ok(_paged(_ref("Batch"))), _V: _err("VALIDATION_ERROR")},
                   [_sort(["expiry_date", "quantity", "product_name"], "expiry_date")] + _PAGINATION_PARAMS),
    },
    "/inventory/low-stock": {
        "get": _op("Inventory alerts", "Active products with stock <= reorder_level", _ADMIN,
                   {**_ok(_paged(_ref("Product"))), _V: _err("VALIDATION_ERROR")},
                   [_sort(["stock", "name", "reorder_level"], "stock")] + _PAGINATION_PARAMS),
    },
    "/inventory/out-of-stock": {
        "get": _op("Inventory alerts", "Active products with stock <= 0", _ADMIN,
                   {**_ok(_paged(_ref("Product"))), _V: _err("VALIDATION_ERROR")},
                   [_sort(["stock", "name", "reorder_level"], "stock")] + _PAGINATION_PARAMS),
    },
}
