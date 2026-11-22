"""User account endpoints under API_PREFIX (Part 3).

Replaces /user/create, /admin/getAllUsers, /admin/user/getSpecificUser, /admin/updateUser,
/admin/approveUser and /admin/deleteUser (hard delete -> soft delete). `/` and `/dox` were removed
from this blueprint (`/dox` now redirects to /api/docs, see app/routes/docs.py).
"""
from flask import request, url_for

from app.db import db_connection, get_db
from app.errors import ForbiddenError, ValidationError
from app.services import account_service as acc
from app.services import auth_service as auth
from app.services.audit_service import write_audit
from app.utils.api_blueprint import ApiBlueprint
from app.utils.decorators import current_identity, role_required
from app.utils.pagination import parse_pagination
from app.utils.responses import api_response, paginated_response
from app.utils.uploads import IMAGE_MIME, upload_file
from app.utils.validators import Validator, request_payload

user_bp = ApiBlueprint("user", __name__)
ADMIN = ["admin"]
ANY_ROLE = ["admin", "user"]
USER_IMAGE_FOLDER = "MediAdminApp/Users"


def _image_url():
    file = request.files.get("image")
    if file is None or not file.filename:
        return None
    return upload_file(file, USER_IMAGE_FOLDER, field="image", allowed_mime=IMAGE_MIME)


def _user_json(conn, user_id, include_deleted=False):
    return acc.serialize_user(acc.fetch_user(conn, user_id, include_deleted=include_deleted))


# ------------------------------------------------------------------ signup (public)
@user_bp.post("/users")
def create_user():
    payload = request_payload()
    v = Validator(payload)
    v.string("name", required=True, min_len=1, max_len=200)
    v.string("address", default="", max_len=500)
    acc.add_contact_rules(v, require_email=True)
    acc.add_password_rule(v, required=True)
    acc.reject_fields(v, acc.PROTECTED_USER_FIELDS + ("image_url",), "cannot be set at signup")
    cleaned = v.validate()
    # Role is always 'user'; any `Admin:` header is ignored (audit finding C-01).
    with db_connection(immediate=True) as conn:
        acc.ensure_user_unique(conn, cleaned.get("email"), cleaned.get("phone_number"))
    image_url = _image_url()
    if image_url:
        cleaned["image_url"] = image_url
    with db_connection(immediate=True) as conn:
        acc.ensure_user_unique(conn, cleaned.get("email"), cleaned.get("phone_number"))
        user_id = acc.insert_user(conn, cleaned)
        write_audit(conn, user_id, "user", "user.signup", "user", user_id,
                    {k: v for k, v in cleaned.items() if k != "password"})
        data = _user_json(conn, user_id)
    location = url_for("user.get_user", user_id=user_id, _external=True)
    return api_response(data, "Account created. An admin must approve it before you can log in.", 201,
                        headers={"Location": location})


# ------------------------------------------------------------------ admin listing
@user_bp.get("/users")
@role_required(ADMIN)
def list_users():
    v = Validator(request.args.to_dict())
    v.string("q", max_len=100)
    v.boolean("is_approved")
    v.boolean("is_blocked")
    v.boolean("include_deleted", default=False)
    v.iso_datetime("updated_since")
    filters = {k: val for k, val in v.validate("Invalid query parameters").items() if val != ""}
    limit, offset, sort, order = parse_pagination(request.args, acc.USER_SORT, default_sort="created_at",
                                                  default_order="desc")
    conn = get_db()
    try:
        rows, total = acc.list_users(conn, filters, limit, offset, sort, order)
    finally:
        conn.close()
    return paginated_response([acc.serialize_user(r) for r in rows], limit, offset, total,
                              "Users fetched successfully")


# ------------------------------------------------------------------ self service
def _require_user_role():
    identity, role = current_identity()
    if role != "user":
        raise ForbiddenError("Only customer accounts have a /users/me profile; admins use /admins/{admin_id}")
    return identity


@user_bp.get("/users/me")
@role_required(ANY_ROLE)
def get_me():
    identity = _require_user_role()
    conn = get_db()
    try:
        data = _user_json(conn, identity)
    finally:
        conn.close()
    return api_response(data, "Profile fetched successfully")


@user_bp.patch("/users/me")
@role_required(ANY_ROLE)
def update_me():
    identity = _require_user_role()
    payload = request_payload()
    v = acc.profile_validator(payload)
    acc.add_password_rule(v)
    acc.reject_fields(v, acc.PROTECTED_USER_FIELDS + ("image_url",))
    conn = get_db()
    try:
        row = acc.fetch_user(conn, identity)
    finally:
        conn.close()
    auth.reject_google_email_change(v, row)
    acc.require_current_password(v, payload, row, auth.verify_password)
    cleaned = v.validate()
    cleaned.pop("current_password", None)
    has_image = bool(request.files.get("image") and request.files["image"].filename)
    if not cleaned and not has_image:
        raise ValidationError("No updatable fields supplied")
    with db_connection(immediate=True) as conn:
        acc.ensure_user_unique(conn, cleaned.get("email"), cleaned.get("phone_number"), exclude_id=identity)
    if has_image:
        cleaned["image_url"] = _image_url()
    with db_connection(immediate=True) as conn:
        acc.update_user(conn, identity, cleaned)
        write_audit(conn, identity, "user", "user.update_self", "user", identity, {"fields": sorted(cleaned)})
        data = _user_json(conn, identity)
    return api_response(data, "Profile updated")


# ------------------------------------------------------------------ by id
@user_bp.get("/users/<user_id>")
@role_required(ANY_ROLE)
def get_user(user_id):
    identity, role = current_identity()
    if role != "admin" and identity != user_id:
        raise acc.NotFoundError("User not found")
    conn = get_db()
    try:
        data = _user_json(conn, user_id, include_deleted=role == "admin")
    finally:
        conn.close()
    return api_response(data, "User fetched successfully")


@user_bp.patch("/users/<user_id>")
@role_required(ADMIN)
def update_user(user_id):
    payload = request_payload()
    v = acc.profile_validator(payload)
    acc.reject_fields(v, acc.PROTECTED_USER_FIELDS + ("password", "image_url"),
                      "use the approve/block/unblock actions or the password-reset flow")
    if v.cleaned.get("email"):
        conn = get_db()
        try:
            target = auth.fetch_account(conn, "user", user_id)
        finally:
            conn.close()
        if target is not None:
            auth.reject_google_email_change(v, target)
    cleaned = v.validate()
    has_image = bool(request.files.get("image") and request.files["image"].filename)
    if not cleaned and not has_image:
        raise ValidationError("No updatable fields supplied")
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        acc.fetch_user(conn, user_id)
        acc.ensure_user_unique(conn, cleaned.get("email"), cleaned.get("phone_number"), exclude_id=user_id)
    if has_image:
        cleaned["image_url"] = _image_url()
    with db_connection(immediate=True) as conn:
        acc.update_user(conn, user_id, cleaned)
        write_audit(conn, identity, role, "user.update", "user", user_id, cleaned)
        data = _user_json(conn, user_id)
    return api_response(data, "User updated")


@user_bp.delete("/users/<user_id>")
@role_required(ADMIN)
def delete_user(user_id):
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        acc.set_user_flags(conn, user_id, role="deleted", block=1)
        write_audit(conn, identity, role, "user.delete", "user", user_id, {"soft_delete": True})
        data = _user_json(conn, user_id, include_deleted=True)
    return api_response(data, "User deleted")


def _flag_action(user_id, action, message, **flags):
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        acc.set_user_flags(conn, user_id, **flags)
        write_audit(conn, identity, role, f"user.{action}", "user", user_id, flags)
        data = _user_json(conn, user_id)
    return api_response(data, message)


@user_bp.post("/users/<user_id>/approve")
@role_required(ADMIN)
def approve_user(user_id):
    return _flag_action(user_id, "approve", "User approved", isApproved=1)


@user_bp.post("/users/<user_id>/block")
@role_required(ADMIN)
def block_user(user_id):
    return _flag_action(user_id, "block", "User blocked", block=1)


@user_bp.post("/users/<user_id>/unblock")
@role_required(ADMIN)
def unblock_user(user_id):
    return _flag_action(user_id, "unblock", "User unblocked", block=0)
