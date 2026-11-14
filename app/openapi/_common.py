"""Small builders shared by the Part 2+ OpenAPI fragments (PATHS keys are relative to API_PREFIX).

Shared component schemas `Error` and `Pagination` live in app.openapi.inventory.SCHEMAS.
"""

BEARER = [{"bearerAuth": []}]
ANY = "Roles: admin, user (users only see their own resources; others return 404)"
ADMIN = "Roles: admin"
USER = "Roles: user"
LOCATION = {"Location": {"schema": {"type": "string", "format": "uri"}, "description": "URL of the created resource"}}
AUTH_ERRORS = {
    "401": {"description": "Codes: UNAUTHORIZED, TOKEN_EXPIRED, TOKEN_INVALID",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
    "403": {"description": "Codes: FORBIDDEN",
            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}},
}


def ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def err(*codes):
    return {"description": "Error (R6 shape). Codes: " + ", ".join(codes),
            "content": {"application/json": {"schema": ref("Error")}}}


def envelope(data_schema):
    return {"type": "object", "properties": {"status": {"type": "integer"}, "message": {"type": "string"},
                                             "data": data_schema}}


def paged(item, extra=None):
    props = {"status": {"type": "integer"}, "message": {"type": "string"},
             "data": {"type": "array", "items": item}, "pagination": ref("Pagination")}
    props.update(extra or {})
    return {"type": "object", "properties": props}


def ok(schema, description="OK", status="200", headers=None):
    resp = {"description": description, "content": {"application/json": {"schema": schema}}}
    if headers:
        resp["headers"] = headers
    return {status: resp}


def q(name, schema, description=""):
    return {"name": name, "in": "query", "required": False, "schema": schema, "description": description}


def p(name):
    return {"name": name, "in": "path", "required": True, "schema": {"type": "string"}}


PAGINATION = [
    q("limit", {"type": "integer", "default": 20, "maximum": 100}),
    q("offset", {"type": "integer", "default": 0}),
    q("order", {"type": "string", "enum": ["asc", "desc"]}),
]


def sort(values, default):
    return q("sort", {"type": "string", "enum": list(values), "default": default})


def op(tag, summary, roles, responses, params=None, body=None, idempotent=False, multipart_only=False):
    operation = {"tags": [tag], "summary": summary, "description": roles, "security": BEARER,
                 "parameters": list(params or []), "responses": {**AUTH_ERRORS, **responses}}
    if idempotent:
        operation["parameters"].append({"name": "Idempotency-Key", "in": "header", "required": False,
                                        "schema": {"type": "string", "maxLength": 255},
                                        "description": "Retries with the same key replay the first response"})
    if body:
        content = {"multipart/form-data": {"schema": body}}
        if not multipart_only:
            content["application/json"] = {"schema": body}
        operation["requestBody"] = {"required": True, "content": content}
    return operation
