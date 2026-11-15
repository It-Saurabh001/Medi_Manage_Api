"""OpenAPI fragment: admin accounts (Part 3). Keys are relative to API_PREFIX."""
from app.openapi._examples import AUTH_ERRORS, envelope, error, operation, paged, pagination_params, path_param, query, ref

TAG = "Admins"
ADMIN_EXAMPLE = {
    "admin_id": "AID_68e297784b96", "name": "Asha Admin", "email": "asha@pharmacy.in",
    "phone_number": "+919800000001", "role": "admin", "is_active": True, "is_approved": True, "is_owner": False,
    "image_url": None, "created_at": "2026-11-14T17:33:46Z",
}
PENDING_EXAMPLE = {
    "admin_id": "AID_3f9c0e7a1b2d", "name": "Ravi Admin", "email": "ravi@pharmacy.in",
    "phone_number": None, "role": "admin", "is_active": True, "is_approved": False, "is_owner": False,
    "image_url": None, "created_at": "2026-11-15T09:12:04Z",
}
NOT_FOUND = error(404, "NOT_FOUND", "Admin not found")
LAST_ADMIN = error(409, "CONFLICT", "At least one approved admin is required")
OWNER = error(403, "FORBIDDEN", "Owner account is protected")
DUPLICATE = error(409, "CONFLICT", "Email already registered", {"email": "already registered"})
BASE_PROPS = {
    "name": {"type": "string", "minLength": 1, "maxLength": 200},
    "email": {"type": "string", "format": "email", "maxLength": 200},
    "phone_number": {"type": "string", "pattern": "^\\+?[0-9]{7,15}$"},
    "password": {"type": "string", "minLength": 8, "maxLength": 128},
    "image": {"type": "string", "format": "binary", "description": "multipart only; jpeg/png/webp"},
}

SCHEMAS = {
    "Admin": {"type": "object", "properties": {
        "admin_id": {"type": "string"}, "name": {"type": "string"}, "email": {"type": "string"},
        "phone_number": {"type": "string", "nullable": True},
        "role": {"type": "string", "enum": ["admin", "disabled", "deleted"]}, "is_active": {"type": "boolean"},
        "is_approved": {"type": "boolean", "description": "false until an admin approves a self-registered account"},
        "is_owner": {"type": "boolean", "description": "the first registered admin; cannot be disabled or deleted"},
        "image_url": {"type": "string", "nullable": True},
        "created_at": {"type": "string", "format": "date-time", "nullable": True}}},
    "AdminCreateInput": {"type": "object", "required": ["name", "email", "password"], "properties": BASE_PROPS},
    "AdminRegisterInput": {"type": "object", "required": ["name", "email", "password"], "properties": {
        **BASE_PROPS,
        "signup_code": {"type": "string", "maxLength": 200,
                        "description": "required only when the server sets ADMIN_SIGNUP_CODE "
                                       "(see app-config admin_signup.code_required)"}}},
    "AdminUpdateInput": {"type": "object", "properties": {
        **BASE_PROPS, "role": {"type": "string", "enum": ["admin", "disabled"]},
        "current_password": {"type": "string", "description": "required when you change your own email/password"}}},
}

PATHS = {
    "/admins": {
        "get": operation(
            TAG, "List admins (paginated; deleted admins hidden)", ["admin"], 200, paged(ref("Admin")),
            {"status": 200, "message": "Admins fetched successfully", "data": [ADMIN_EXAMPLE],
             "pagination": {"limit": 20, "offset": 0, "total": 1}},
            [error(400, "VALIDATION_ERROR", "Invalid query parameters", {"role": "must be one of: admin, disabled"})]
            + AUTH_ERRORS,
            params=[query("q", {"type": "string"}, "matches name or email"),
                    query("role", {"type": "string", "enum": ["admin", "disabled"]}),
                    query("is_approved", {"type": "boolean"}, "false = self-registered admins awaiting approval")]
            + pagination_params(("created_at", "name"), "name")),
        "post": operation(
            TAG, "Create an admin", ["admin"], 201, envelope(ref("Admin")),
            {"status": 201, "message": "Admin created", "data": ADMIN_EXAMPLE},
            [error(400, "VALIDATION_ERROR", "Validation failed",
                   {"email": "must be a valid email address", "name": "is required",
                    "password": "must be at least 8 characters"})] + AUTH_ERRORS + [DUPLICATE],
            body=ref("AdminCreateInput"),
            body_example={"name": "Asha Admin", "email": "asha@pharmacy.in", "password": "Secret#2026",
                          "phone_number": "+919800000001"},
            multipart=True, location=True, notes="Writes an audit-log entry."),
    },
    "/admins/register": {
        "post": operation(
            TAG, "Public admin signup (first admin becomes the approved owner; later ones await approval)", [], 201,
            envelope(ref("Admin")),
            {"status": 201, "message": "Admin registered. Awaiting approval.", "data": PENDING_EXAMPLE},
            [error(400, "VALIDATION_ERROR", "Validation failed",
                   {"email": "must be a valid email address", "password": "must be at least 8 characters",
                    "role": "cannot be set at signup"}),
             error(403, "FORBIDDEN", "Invalid signup code"),
             DUPLICATE,
             error(413, "PAYLOAD_TOO_LARGE", "File too large", {"image": "max 5 MB"}),
             error(415, "UNSUPPORTED_MEDIA_TYPE", "Unsupported file type",
                   {"image": "allowed types: image/jpeg, image/png, image/webp"}),
             error(429, "RATE_LIMITED", "Too many attempts; try again later")],
            body=ref("AdminRegisterInput"),
            body_example={"name": "Ravi Admin", "email": "ravi@pharmacy.in", "password": "Secret#2026",
                          "signup_code": "<ADMIN_SIGNUP_CODE>"},
            multipart=True, public=True, location=True,
            notes="role/is_approved/is_blocked/is_owner are rejected. First admin: 'Admin registered.' with "
                  "is_approved=true, is_owner=true. Otherwise login returns 403 ACCOUNT_NOT_APPROVED until "
                  "POST /admins/{admin_id}/approve. Rate-limited per client IP (429 + Retry-After). "
                  "Writes an audit-log entry."),
    },
    "/admins/{admin_id}/approve": {
        "post": operation(
            TAG, "Approve a self-registered admin", ["admin"], 200, envelope(ref("Admin")),
            {"status": 200, "message": "Admin approved", "data": {**PENDING_EXAMPLE, "is_approved": True}},
            AUTH_ERRORS + [NOT_FOUND], params=[path_param("admin_id")],
            notes="Idempotent. Writes an audit-log entry."),
    },
    "/admins/{admin_id}": {
        "get": operation(
            TAG, "Get an admin", ["admin"], 200, envelope(ref("Admin")),
            {"status": 200, "message": "Admin fetched successfully", "data": ADMIN_EXAMPLE},
            AUTH_ERRORS + [NOT_FOUND], params=[path_param("admin_id")]),
        "patch": operation(
            TAG, "Update an admin (email/password: owner only, with current_password; role=disabled demotes)",
            ["admin"], 200, envelope(ref("Admin")),
            {"status": 200, "message": "Admin updated", "data": {**ADMIN_EXAMPLE, "name": "Asha K"}},
            [error(400, "VALIDATION_ERROR", "Validation failed", {"password": "only the account owner can change this"}),
             error(400, "VALIDATION_ERROR", "Validation failed", {"current_password": "required to change email or password"})]
            + AUTH_ERRORS + [OWNER, NOT_FOUND, LAST_ADMIN],
            params=[path_param("admin_id")], body=ref("AdminUpdateInput"), body_example={"name": "Asha K"},
            multipart=True, notes="Writes an audit-log entry."),
        "delete": operation(
            TAG, "Soft-delete an admin (not the owner, not the last approved admin)", ["admin"], 200,
            envelope(ref("Admin")),
            {"status": 200, "message": "Admin deleted",
             "data": {**ADMIN_EXAMPLE, "admin_id": "AID_664fc2b97efc", "name": "Ravi Admin", "email": "ravi@pharmacy.in",
                      "phone_number": None, "role": "deleted", "is_active": False, "created_at": "2026-11-14T17:33:47Z"}},
            AUTH_ERRORS + [OWNER, NOT_FOUND, LAST_ADMIN], params=[path_param("admin_id")],
            notes="Writes an audit-log entry."),
    },
}
