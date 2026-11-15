"""OpenAPI fragment: user accounts (Part 3). Keys are relative to API_PREFIX."""
from app.openapi._examples import (AUTH_ERRORS, FORBIDDEN, UNAUTHORIZED, envelope, error, operation, paged,
                                   pagination_params, path_param, query, ref)

TAG = "Users"
USER_EXAMPLE = {
    "user_id": "UID_06ade2a9b763", "name": "Priya Sharma", "email": "priya@example.com",
    "phone_number": "+919811111111", "address": "12 MG Road, Pune", "pin_code": "411001", "role": "user",
    "is_approved": True, "is_blocked": False, "is_deleted": False, "image_url": None,
    "created_at": "2026-11-14T17:33:47Z",
}
NOT_FOUND = error(404, "NOT_FOUND", "User not found")
DUPLICATE = error(409, "CONFLICT", "Email already registered", {"email": "already registered"})
CONTACT_PROPS = {
    "name": {"type": "string", "minLength": 1, "maxLength": 200},
    "address": {"type": "string", "maxLength": 500},
    "email": {"type": "string", "format": "email", "maxLength": 200},
    "phone_number": {"type": "string", "pattern": "^\\+?[0-9]{7,15}$"},
    "pin_code": {"type": "string", "pattern": "^[0-9]{4,10}$"},
    "image": {"type": "string", "format": "binary", "description": "multipart only; jpeg/png/webp"},
}

SCHEMAS = {
    "User": {"type": "object", "properties": {
        "user_id": {"type": "string"}, "name": {"type": "string"}, "email": {"type": "string", "nullable": True},
        "phone_number": {"type": "string", "nullable": True}, "address": {"type": "string", "nullable": True},
        "pin_code": {"type": "string", "nullable": True}, "role": {"type": "string", "enum": ["user"]},
        "is_approved": {"type": "boolean"}, "is_blocked": {"type": "boolean"}, "is_deleted": {"type": "boolean"},
        "image_url": {"type": "string", "nullable": True},
        "created_at": {"type": "string", "format": "date-time", "nullable": True}}},
    "SignupInput": {"type": "object", "required": ["name", "email", "password"], "properties": {
        **CONTACT_PROPS, "password": {"type": "string", "minLength": 8, "maxLength": 128}}},
    "ProfileInput": {"type": "object", "properties": {
        **CONTACT_PROPS, "password": {"type": "string", "minLength": 8, "maxLength": 128},
        "current_password": {"type": "string", "description": "required when email or password changes"}}},
    "AdminUserInput": {"type": "object", "properties": CONTACT_PROPS},
}


def _action(summary, message, **changes):
    return {"post": operation(
        TAG, summary, ["admin"], 200, envelope(ref("User")),
        {"status": 200, "message": message, "data": {**USER_EXAMPLE, **changes}},
        AUTH_ERRORS + [NOT_FOUND], params=[path_param("user_id")], notes="Writes an audit-log entry.")}


PATHS = {
    "/users": {
        "post": operation(
            TAG, "Customer signup (role is always `user`; account starts unapproved)", [], 201,
            envelope(ref("User")),
            {"status": 201, "message": "Account created. An admin must approve it before you can log in.",
             "data": {**USER_EXAMPLE, "is_approved": False}},
            [error(400, "VALIDATION_ERROR", "Validation failed",
                   {"email": "must be a valid email address", "password": "must be at least 8 characters"}),
             DUPLICATE,
             error(415, "UNSUPPORTED_MEDIA_TYPE", "Unsupported file type",
                   {"image": "allowed types: image/jpeg, image/png, image/webp"})],
            body=ref("SignupInput"),
            body_example={"name": "Priya Sharma", "email": "priya@example.com", "password": "Priya#2026",
                          "phone_number": "+919811111111", "address": "12 MG Road, Pune", "pin_code": "411001"},
            multipart=True, public=True, location=True,
            notes="Fields role/is_approved/is_blocked are rejected; an `Admin` header is ignored."),
        "get": operation(
            TAG, "List customers (paginated)", ["admin"], 200, paged(ref("User")),
            {"status": 200, "message": "Users fetched successfully", "data": [USER_EXAMPLE],
             "pagination": {"limit": 20, "offset": 0, "total": 1}},
            [error(400, "VALIDATION_ERROR", "Invalid query parameters", {"is_approved": "must be true or false"})] + AUTH_ERRORS,
            params=[query("q", {"type": "string"}, "matches name, email or phone"),
                    query("is_approved", {"type": "boolean"}), query("is_blocked", {"type": "boolean"}),
                    query("include_deleted", {"type": "boolean", "default": False}),
                    query("updated_since", {"type": "string", "format": "date-time"},
                          "Users have no updated_at column: filters by created_at >= value")]
            + pagination_params(("created_at", "name"), "created_at", "desc")),
    },
    "/users/me": {
        "get": operation(
            TAG, "Own customer profile", ["user"], 200, envelope(ref("User")),
            {"status": 200, "message": "Profile fetched successfully", "data": USER_EXAMPLE},
            [UNAUTHORIZED, error(403, "FORBIDDEN",
                                 "Only customer accounts have a /users/me profile; admins use /admins/{admin_id}")],
            notes="Admin tokens get 403; admins use /admins/{admin_id}."),
        "patch": operation(
            TAG, "Update own profile (name, address, phone_number, pin_code; email/password need current_password)",
            ["user"], 200, envelope(ref("User")),
            {"status": 200, "message": "Profile updated",
             "data": {**USER_EXAMPLE, "address": "14 MG Road, Pune", "pin_code": "411002"}},
            [error(400, "VALIDATION_ERROR", "Validation failed", {"current_password": "required to change email or password"}),
             error(400, "VALIDATION_ERROR", "Validation failed", {"role": "cannot be changed here"}),
             UNAUTHORIZED, FORBIDDEN, DUPLICATE],
            body=ref("ProfileInput"), body_example={"address": "14 MG Road, Pune", "pin_code": "411002"}, multipart=True),
    },
    "/users/{user_id}": {
        "get": operation(
            TAG, "Get a user (admin: any; user: own id only, else 404)", ["admin", "user"], 200, envelope(ref("User")),
            {"status": 200, "message": "User fetched successfully", "data": USER_EXAMPLE},
            [UNAUTHORIZED, NOT_FOUND], params=[path_param("user_id")]),
        "patch": operation(
            TAG, "Admin edits a user's profile fields", ["admin"], 200, envelope(ref("User")),
            {"status": 200, "message": "User updated", "data": {**USER_EXAMPLE, "name": "Priya S"}},
            [error(400, "VALIDATION_ERROR", "Validation failed",
                   {"is_approved": "use the approve/block/unblock actions or the password-reset flow"})]
            + AUTH_ERRORS + [NOT_FOUND, DUPLICATE],
            params=[path_param("user_id")], body=ref("AdminUserInput"), body_example={"name": "Priya S"}, multipart=True),
        "delete": operation(
            TAG, "Soft-delete a user (role=deleted, blocked)", ["admin"], 200, envelope(ref("User")),
            {"status": 200, "message": "User deleted", "data": {**USER_EXAMPLE, "is_blocked": True, "is_deleted": True}},
            AUTH_ERRORS + [NOT_FOUND], params=[path_param("user_id")]),
    },
    "/users/{user_id}/approve": _action("Approve a customer account", "User approved", is_approved=True),
    "/users/{user_id}/block": _action("Block a customer (login and refresh rejected)", "User blocked", is_blocked=True),
    "/users/{user_id}/unblock": _action("Unblock a customer", "User unblocked"),
}
