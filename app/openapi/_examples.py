"""Builders for OpenAPI operations that carry real example JSON (Part 3 fragments).

Every operation gets one success example and at least one error example (R6 shape with `code`).
Examples were captured from the running code with the Flask test client; tokens are shortened.
"""

ERROR_REF = {"$ref": "#/components/schemas/Error"}
PAGINATION_REF = {"$ref": "#/components/schemas/Pagination"}
BEARER = [{"bearerAuth": []}]
LOCATION_HEADER = {"Location": {"schema": {"type": "string", "format": "uri"},
                                "description": "Absolute URL of the created resource"}}
APP_VERSION_HEADER = {"name": "X-App-Version", "in": "header", "required": False,
                      "schema": {"type": "string", "example": "1.4.0"},
                      "description": "Mobile app semver; below MIN_APP_VERSION -> 426 UPGRADE_REQUIRED"}

ACCESS_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXBlIjoiYWNjZXNzIiwic3ViIjoiVUlEXzA2YWRlMmE5Yjc2MyJ9.DIPd-HS_MYjA"
REFRESH_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXBlIjoicmVmcmVzaCIsInN1YiI6IlVJRF8wNmFkZTJhOWI3NjMifQ.GP6EUTLeDlTG"


def error(status, code, message, fields=None):
    body = {"status": status, "message": message, "code": code}
    if fields:
        body["fields"] = fields
    return body


UNAUTHORIZED = error(401, "UNAUTHORIZED", "Missing or malformed authorization token")
TOKEN_EXPIRED = error(401, "TOKEN_EXPIRED", "Token has expired")
FORBIDDEN = error(403, "FORBIDDEN", "Access Forbidden")
AUTH_ERRORS = [UNAUTHORIZED, TOKEN_EXPIRED, FORBIDDEN]


def envelope(data_schema):
    return {"type": "object", "required": ["status", "message", "data"],
            "properties": {"status": {"type": "integer"}, "message": {"type": "string"}, "data": data_schema}}


def paged(item_schema):
    return {"type": "object", "required": ["status", "message", "data", "pagination"],
            "properties": {"status": {"type": "integer"}, "message": {"type": "string"},
                           "data": {"type": "array", "items": item_schema}, "pagination": PAGINATION_REF}}


def ref(name):
    return {"$ref": f"#/components/schemas/{name}"}


def query(name, schema, description=""):
    return {"name": name, "in": "query", "required": False, "schema": schema, "description": description}


def path_param(name):
    return {"name": name, "in": "path", "required": True, "schema": {"type": "string"}}


def pagination_params(sort_values, default_sort, default_order="asc"):
    return [
        query("limit", {"type": "integer", "default": 20, "minimum": 1, "maximum": 100}),
        query("offset", {"type": "integer", "default": 0, "minimum": 0}),
        query("sort", {"type": "string", "enum": list(sort_values), "default": default_sort}),
        query("order", {"type": "string", "enum": ["asc", "desc"], "default": default_order}),
    ]


def _errors(errors):
    grouped = {}
    for example in errors:
        grouped.setdefault(str(example["status"]), []).append(example)
    responses = {}
    for status, examples in grouped.items():
        codes = sorted({e["code"] for e in examples})
        content = {"schema": ERROR_REF}
        if len(examples) == 1:
            content["example"] = examples[0]
        else:
            content["examples"] = {f"{e['code']}_{i}": {"value": e} for i, e in enumerate(examples)}
        responses[status] = {"description": "Codes: " + ", ".join(codes), "content": {"application/json": content}}
    return responses


def operation(tag, summary, roles, status, schema, example, errors, *, params=None, body=None,
              body_example=None, multipart=False, public=False, location=False, notes=""):
    """roles: list of roles or [] for public. errors: list of `error(...)` examples."""
    role_text = "public (no token)" if public else ", ".join(roles)
    success = {"description": example.get("message", "OK") if isinstance(example, dict) else "OK",
               "content": {"application/json": {"schema": schema, "example": example}}}
    if location:
        success["headers"] = LOCATION_HEADER
    op = {
        "tags": [tag],
        "summary": summary,
        "description": f"Roles: {role_text}." + (f" {notes}" if notes else ""),
        "security": [] if public else BEARER,
        "parameters": list(params or []) + [APP_VERSION_HEADER],
        "responses": {str(status): success, **_errors(errors)},
    }
    if body is not None:
        content = {"application/json": {"schema": body}}
        if body_example is not None:
            content["application/json"]["example"] = body_example
        if multipart:
            content["multipart/form-data"] = {"schema": body}
        op["requestBody"] = {"required": True, "content": content}
    return op
