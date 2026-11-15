"""API index, app-config, OpenAPI JSON and device-token endpoints under API_PREFIX (Part 3)."""
import uuid

from flask import abort, current_app, jsonify, url_for

from app.api_constants import API_NAME, API_VERSION, DEVICE_PLATFORMS, ERROR_CODES, SUGGESTED_UNITS
from app.db import db_connection
from app.errors import NotFoundError
from app.services import order_service, product_service, stock_service
from app.services.audit_service import write_audit
from app.utils.api_blueprint import ApiBlueprint
from app.utils.decorators import current_identity, role_required
from app.utils.responses import api_response
from app.utils.timeutil import to_iso_z, utc_now_iso
from app.utils.uploads import IMAGE_MIME
from app.utils.validators import Validator, request_payload
from app.openapi.spec import build_spec


meta_bp = ApiBlueprint("meta", __name__)

PUBLIC_ENDPOINTS = (
    "meta.api_index", "meta.app_config", "meta.openapi_json", "docs.swagger_ui", "health.health",
    "health.ready", "auth.login", "auth.verify_otp", "auth.password_reset_request",
    "auth.password_reset_confirm", "user.create_user", "admin.register_admin",
)
DOC_ENDPOINTS = ("meta.openapi_json", "docs.swagger_ui")


@meta_bp.get("")
def api_index():
    docs_enabled = bool(current_app.config.get("ENABLE_DOCS"))
    links = []
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint not in PUBLIC_ENDPOINTS or (rule.endpoint in DOC_ENDPOINTS and not docs_enabled):
            continue
        links.append({"rel": rule.endpoint, "href": rule.rule,
                      "methods": sorted(rule.methods - {"HEAD", "OPTIONS"})})
    links.sort(key=lambda link: link["href"])
    return api_response({"name": API_NAME, "version": API_VERSION, "api_version": "v1", "links": links},
                        "Medi_Manage_Api v1")


@meta_bp.get("/app-config")
def app_config():
    cfg = current_app.config
    return api_response({
        "api_version": "v1",
        "api_prefix": cfg.get("API_PREFIX"),
        "min_app_version": cfg.get("MIN_APP_VERSION") or None,
        "server_time": utc_now_iso(),
        "docs_enabled": bool(cfg.get("ENABLE_DOCS")),
        "enums": {
            "schedule_types": list(product_service.SCHEDULE_TYPES),
            "prescription_schedules": sorted(product_service.RX_SCHEDULES),
            "dosage_forms": list(product_service.DOSAGE_FORMS),
            "order_statuses": list(order_service.STATUSES),
            "units": list(SUGGESTED_UNITS),
            "stock_movement_reasons": list(stock_service.REASONS),
            "account_types": ["user", "admin"],
            "device_platforms": list(DEVICE_PLATFORMS),
        },
        "uploads": {
            "max_upload_mb": cfg.get("MAX_UPLOAD_MB"),
            "max_request_bytes": cfg.get("MAX_CONTENT_LENGTH"),
            "allowed_mime_types": list(cfg.get("ALLOWED_UPLOAD_MIME", ())),
            "image_mime_types": list(IMAGE_MIME),
        },
        "pagination": {"default_limit": 20, "max_limit": 100},
        "otp": {"length": 6, "expires_in": int(cfg.get("OTP_EXPIRY_SECONDS", 300)), "max_attempts": 5},
        "admin_signup": {"enabled": True, "code_required": bool(cfg.get("ADMIN_SIGNUP_CODE"))},
        "error_codes": list(ERROR_CODES),
    }, "App configuration")


@meta_bp.get("/openapi.json")
def openapi_json():
    if not current_app.config.get("ENABLE_DOCS"):
        abort(404)

    return jsonify(build_spec(current_app))


# ------------------------------------------------------------------ devices
def _serialize_device(row):
    return {
        "device_id": row["Device_id"],
        "user_id": row["user_id"],
        "platform": row["platform"],
        "app_version": row["app_version"] or "",
        "is_active": bool(row["is_active"]),
        "created_at": to_iso_z(row["created_at"]),
        "updated_at": to_iso_z(row["updated_at"]),
    }


@meta_bp.post("/devices")
@role_required(["admin", "user"])
def register_device():
    v = Validator(request_payload())
    v.string("token", required=True, min_len=8, max_len=4096)
    v.enum("platform", DEVICE_PLATFORMS, required=True)
    v.string("app_version", default="", max_len=32)
    cleaned = v.validate()
    identity, role = current_identity()
    now = utc_now_iso()
    with db_connection(immediate=True) as conn:
        existing = conn.execute("SELECT * FROM Device_Tokens WHERE token = ?", (cleaned["token"],)).fetchone()
        if existing is not None:
            device_id, created = existing["Device_id"], False
            conn.execute(
                """UPDATE Device_Tokens SET user_id = ?, platform = ?, app_version = ?, is_active = 1, updated_at = ?
                   WHERE Device_id = ?""",
                (identity, cleaned["platform"], cleaned["app_version"], now, device_id))
        else:
            device_id, created = "DEV_" + uuid.uuid4().hex[:12], True
            conn.execute(
                """INSERT INTO Device_Tokens(Device_id, user_id, token, platform, app_version, is_active, created_at,
                       updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                (device_id, identity, cleaned["token"], cleaned["platform"], cleaned["app_version"], now, now))
        write_audit(conn, identity, role, "device.register", "device", device_id,
                    {"platform": cleaned["platform"], "created": created})
        row = conn.execute("SELECT * FROM Device_Tokens WHERE Device_id = ?", (device_id,)).fetchone()
    location = url_for("meta.delete_device", device_id=device_id, _external=True)
    return api_response(_serialize_device(row), "Device registered" if created else "Device updated",
                        201 if created else 200, headers={"Location": location})


@meta_bp.delete("/devices/<device_id>")
@role_required(["admin", "user"])
def delete_device(device_id):
    identity, role = current_identity()
    with db_connection(immediate=True) as conn:
        cur = conn.execute(
            "UPDATE Device_Tokens SET is_active = 0, updated_at = ? WHERE Device_id = ? AND user_id = ? AND is_active = 1",
            (utc_now_iso(), device_id, identity))
        if cur.rowcount == 0:
            raise NotFoundError("Device not found")
        write_audit(conn, identity, role, "device.unregister", "device", device_id, {})
        row = conn.execute("SELECT * FROM Device_Tokens WHERE Device_id = ?", (device_id,)).fetchone()
    return api_response(_serialize_device(row), "Device unregistered")
