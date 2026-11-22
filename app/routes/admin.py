"""Admin account endpoints under API_PREFIX (Part 3).

Replaces /admin/create, /admin/getAllAdmins, /admin/update and /admin/delete (hard -> soft delete).
Public admin signup (POST /admins/register) + approval (POST /admins/{admin_id}/approve).
"""
import hmac

from flask import current_app, request, url_for

from app.db import db_connection, get_db
from app.errors import ForbiddenError, ValidationError
from app.services import account_service as acc
from app.services import auth_service as auth
from app.services.audit_service import write_audit
from app.utils.api_blueprint import ApiBlueprint
from app.utils.decorators import current_identity, role_required
from app.utils.pagination import parse_pagination
from app.utils.rate_limit import enforce_rate_limit
from app.utils.responses import api_response, paginated_response
from app.utils.uploads import IMAGE_MIME, upload_file
from app.utils.validators import Validator, request_payload

admin_bp = ApiBlueprint("admin", __name__)
ADMIN = ["admin"]
ADMIN_IMAGE_FOLDER = "MediAdminApp/Admins"


def _image_url():
    file = request.files.get("image")
    if file is None or not file.filename:
        return None
    return upload_file(file, ADMIN_IMAGE_FOLDER, field="image", allowed_mime=IMAGE_MIME)


@admin_bp.get("/admins")
@role_required(ADMIN)
def list_admins():
    v = Validator(request.args.to_dict())
    v.string("q", max_len=100)
    v.enum("role", acc.ADMIN_ROLES)
    v.boolean("is_approved")
    filters = {k: val for k, val in v.validate("Invalid query parameters").items()
               if val or (k == "is_approved" and val is False)}
    limit, offset, sort, order = parse_pagination(request.args, acc.ADMIN_SORT, default_sort="name")
    conn = get_db()
    try:
        rows, total = acc.list_admins(conn, filters, limit, offset, sort, order)
    finally:
        conn.close()
    return paginated_response([acc.serialize_admin(r) for r in rows], limit, offset, total,
                              "Admins fetched successfully")


@admin_bp.post("/admins")
@role_required(ADMIN)
def create_admin():
    v = Validator(request_payload())
    v.string("name", required=True, min_len=1, max_len=200)
    acc.add_contact_rules(v, require_email=True)
    acc.add_password_rule(v, required=True)
    acc.reject_fields(v, ("role", "admin_id", "image_url", "pin_code", "is_approved", "is_owner"), "cannot be set")
    cleaned = v.validate()
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        acc.ensure_admin_unique(conn, cleaned["email"], cleaned.get("phone_number"))
    image_url = _image_url()
    if image_url:
        cleaned["image_url"] = image_url
    with db_connection(immediate=True) as conn:
        acc.ensure_admin_unique(conn, cleaned["email"], cleaned.get("phone_number"))
        admin_id = acc.insert_admin(conn, cleaned)
        write_audit(conn, identity, role, "admin.create", "admin", admin_id,
                    {k: v for k, v in cleaned.items() if k != "password"})
        data = acc.serialize_admin(acc.fetch_admin(conn, admin_id))
    location = url_for("admin.get_admin", admin_id=admin_id, _external=True)
    return api_response(data, "Admin created", 201, headers={"Location": location})


def _check_signup_code(supplied):
    expected = current_app.config.get("ADMIN_SIGNUP_CODE") or ""
    if not expected:
        return
    if not hmac.compare_digest((supplied or "").encode("utf-8"), expected.encode("utf-8")):
        raise ForbiddenError("Invalid signup code")


@admin_bp.post("/admins/register")
def register_admin():
    """Public admin signup. The first admin ever becomes the approved owner; later ones await approval."""
    cfg = current_app.config
    enforce_rate_limit("admin_register", cfg.get("ADMIN_SIGNUP_RATE_LIMIT", 10),
                       cfg.get("ADMIN_SIGNUP_RATE_WINDOW_SECONDS", 3600))
    v = Validator(request_payload())
    v.string("name", required=True, min_len=1, max_len=200)
    acc.add_contact_rules(v, require_email=True)
    acc.add_password_rule(v, required=True)
    v.string("signup_code", max_len=200)
    acc.reject_fields(v, acc.PROTECTED_ADMIN_FIELDS, "cannot be set at signup")
    cleaned = v.validate()
    _check_signup_code(cleaned.pop("signup_code", None))
    with db_connection(immediate=True) as conn:
        acc.ensure_admin_unique(conn, cleaned["email"], cleaned.get("phone_number"))
    image_url = _image_url()
    if image_url:
        cleaned["image_url"] = image_url
    password_hash = acc.hash_password(cleaned["password"])  # slow; keep it outside the write lock
    # BEGIN IMMEDIATE holds SQLite's write lock across the first-admin check and the insert, so two
    # concurrent signups cannot both see "no admin yet"; ux_admin_owner is the second line of defence.
    with db_connection(immediate=True) as conn:
        acc.ensure_admin_unique(conn, cleaned["email"], cleaned.get("phone_number"))
        is_first = not acc.has_live_admin(conn)
        admin_id = acc.insert_admin(conn, cleaned, is_approved=is_first, is_owner=is_first,
                                    password_hash=password_hash, email_verified=False)
        details = {k: val for k, val in cleaned.items() if k != "password"}
        details.update(is_approved=is_first, is_owner=is_first)
        write_audit(conn, admin_id, "admin", "admin.register", "admin", admin_id, details)
        data = acc.serialize_admin(acc.fetch_admin(conn, admin_id))
    location = url_for("admin.get_admin", admin_id=admin_id, _external=True)
    auth.enforce_resend_cooldown("verify", "admin", admin_id)
    try:
        auth.send_verification_otp("admin", admin_id, cleaned["email"])  # 502 EMAIL_DELIVERY_FAILED on failure
    except Exception:
        current_app.logger.exception("Admin signup: verification email failed; removing admin %s", admin_id)
        # Undo the signup so the same email/phone can register again once email delivery works.
        with db_connection(immediate=True) as conn:
            conn.execute("DELETE FROM Admin WHERE admin_id = ? AND COALESCE(is_email_verified, 0) = 0", (admin_id,))
            write_audit(conn, admin_id, "admin", "admin.register_rollback", "admin", admin_id,
                        {"reason": "email_delivery_failed"})
        auth.clear_resend_cooldown("verify", "admin", admin_id)
        raise
    data.update(otp_required=True, otp_expires_in=auth.otp_ttl("verify"))
    message = ("Admin registered." if is_first else "Admin registered. Awaiting approval.")         + " Verification code sent to your email."
    return api_response(data, message, 201, headers={"Location": location})


@admin_bp.post("/admins/<admin_id>/approve")
@role_required(ADMIN)
def approve_admin(admin_id):
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        acc.approve_admin(conn, admin_id)
        write_audit(conn, identity, role, "admin.approve", "admin", admin_id, {"is_approved": True})
        data = acc.serialize_admin(acc.fetch_admin(conn, admin_id))
    return api_response(data, "Admin approved")


@admin_bp.get("/admins/<admin_id>")
@role_required(ADMIN)
def get_admin(admin_id):
    conn = get_db()
    try:
        data = acc.serialize_admin(acc.fetch_admin(conn, admin_id))
    finally:
        conn.close()
    return api_response(data, "Admin fetched successfully")


@admin_bp.patch("/admins/<admin_id>")
@role_required(ADMIN)
def update_admin(admin_id):
    payload = request_payload()
    identity, role = current_identity()
    is_self = identity == admin_id
    v = Validator(payload, partial=True)
    v.string("name", required=True, min_len=1, max_len=200)
    acc.add_contact_rules(v)
    acc.add_password_rule(v)
    v.enum("role", acc.ADMIN_ROLES)
    acc.reject_fields(v, ("admin_id", "image_url", "pin_code", "is_active", "is_owner"), "cannot be changed")
    acc.reject_fields(v, ("is_approved",), "use POST /admins/{admin_id}/approve")
    if not is_self:
        for field in ("email", "password"):
            v.reject(field, "only the account owner can change this")
    conn = get_db()
    try:
        row = acc.fetch_admin(conn, admin_id)
    finally:
        conn.close()
    auth.reject_google_email_change(v, row)
    if is_self:
        acc.require_current_password(v, payload, row, auth.verify_password)
    cleaned = v.validate()
    has_image = bool(request.files.get("image") and request.files["image"].filename)
    if not cleaned and not has_image:
        raise ValidationError("No updatable fields supplied")
    with db_connection(immediate=True) as conn:
        row = acc.fetch_admin(conn, admin_id)
        if cleaned.get("role") == "disabled":
            acc.ensure_admin_removable(conn, row)
        acc.ensure_admin_unique(conn, cleaned.get("email"), cleaned.get("phone_number"), exclude_id=admin_id)
    if has_image:
        cleaned["image_url"] = _image_url()
    with db_connection(immediate=True) as conn:
        row = acc.fetch_admin(conn, admin_id)
        if cleaned.get("role") == "disabled":
            acc.ensure_admin_removable(conn, row)
        acc.update_admin(conn, admin_id, cleaned)
        write_audit(conn, identity, role, "admin.update", "admin", admin_id,
                    {k: v for k, v in cleaned.items() if k != "password"})
        data = acc.serialize_admin(acc.fetch_admin(conn, admin_id))
    return api_response(data, "Admin updated")


@admin_bp.delete("/admins/<admin_id>")
@role_required(ADMIN)
def delete_admin(admin_id):
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        row = acc.fetch_admin(conn, admin_id)
        acc.ensure_admin_removable(conn, row)
        acc.update_admin(conn, admin_id, {"role": "deleted"})
        write_audit(conn, identity, role, "admin.delete", "admin", admin_id, {"soft_delete": True})
        data = acc.serialize_admin(acc.fetch_admin(conn, admin_id, include_deleted=True))
    return api_response(data, "Admin deleted")
