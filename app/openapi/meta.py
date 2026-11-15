"""OpenAPI fragment: API index, app-config, OpenAPI JSON, device tokens (Part 3). Keys relative to API_PREFIX."""
from app.openapi._examples import UNAUTHORIZED, envelope, error, operation, path_param, ref

DEVICE_EXAMPLE = {
    "device_id": "DEV_b15c145f32af", "user_id": "UID_06ade2a9b763", "platform": "android", "app_version": "1.4.0",
    "is_active": True, "created_at": "2026-11-14T17:33:50Z", "updated_at": "2026-11-14T17:33:50Z",
}
APP_CONFIG_EXAMPLE = {
    "api_version": "v1", "api_prefix": "/api/v1", "min_app_version": None, "server_time": "2026-11-14T17:33:45Z",
    "docs_enabled": True,
    "enums": {
        "schedule_types": ["OTC", "H", "H1", "X", "NARCOTIC"], "prescription_schedules": ["H", "H1", "NARCOTIC", "X"],
        "dosage_forms": ["Tablet", "Capsule", "Syrup", "Injection", "Ointment", "Drops", "Other"],
        "order_statuses": ["pending", "approved", "sold", "cancelled", "returned"],
        "units": ["strip", "bottle", "tube", "box", "vial", "sachet", "piece", "pack"],
        "stock_movement_reasons": ["PURCHASE", "SALE", "ADJUSTMENT", "EXPIRED_WRITEOFF", "RETURN", "CANCEL_RESTOCK"],
        "account_types": ["user", "admin"], "device_platforms": ["android", "ios"],
    },
    "uploads": {"max_upload_mb": 5, "max_request_bytes": 6291456,
                "allowed_mime_types": ["image/jpeg", "image/png", "image/webp", "application/pdf"],
                "image_mime_types": ["image/jpeg", "image/png", "image/webp"]},
    "pagination": {"default_limit": 20, "max_limit": 100},
    "otp": {"length": 6, "expires_in": 300, "max_attempts": 5},
    "admin_signup": {"enabled": True, "code_required": False},
    "error_codes": ["VALIDATION_ERROR", "NOT_FOUND", "UNAUTHORIZED", "TOKEN_EXPIRED", "TOKEN_INVALID", "FORBIDDEN",
                    "ACCOUNT_BLOCKED", "ACCOUNT_NOT_APPROVED", "OUT_OF_STOCK", "PRESCRIPTION_REQUIRED",
                    "PRESCRIPTION_NOT_VERIFIED", "INVALID_TRANSITION", "CONFLICT", "ALREADY_SOLD", "BATCH_EXPIRED",
                    "UPGRADE_REQUIRED", "RATE_LIMITED", "PAYLOAD_TOO_LARGE", "UNSUPPORTED_MEDIA_TYPE",
                    "METHOD_NOT_ALLOWED", "INTERNAL_ERROR"],
}
UPGRADE = error(426, "UPGRADE_REQUIRED", "This app version is no longer supported; please update.",
                {"X-App-Version": "minimum supported version is 2.0.0"})
METHOD = error(405, "METHOD_NOT_ALLOWED", "Method not allowed")
DOCS_OFF = error(404, "NOT_FOUND", "Resource not found")

SCHEMAS = {
    "Device": {"type": "object", "properties": {
        "device_id": {"type": "string"}, "user_id": {"type": "string"},
        "platform": {"type": "string", "enum": ["android", "ios"]}, "app_version": {"type": "string"},
        "is_active": {"type": "boolean"}, "created_at": {"type": "string", "format": "date-time"},
        "updated_at": {"type": "string", "format": "date-time"}}},
    "DeviceInput": {"type": "object", "required": ["token", "platform"], "properties": {
        "token": {"type": "string", "minLength": 8, "maxLength": 4096, "description": "FCM/APNs push token"},
        "platform": {"type": "string", "enum": ["android", "ios"]},
        "app_version": {"type": "string", "maxLength": 32}}},
    "AppConfig": {"type": "object", "properties": {
        "api_version": {"type": "string"}, "api_prefix": {"type": "string"},
        "min_app_version": {"type": "string", "nullable": True},
        "server_time": {"type": "string", "format": "date-time"}, "docs_enabled": {"type": "boolean"},
        "enums": {"type": "object", "additionalProperties": {"type": "array", "items": {"type": "string"}}},
        "uploads": {"type": "object"}, "pagination": {"type": "object"}, "otp": {"type": "object"},
        "admin_signup": {"type": "object", "properties": {
            "enabled": {"type": "boolean"},
            "code_required": {"type": "boolean", "description": "true -> show a signup-code field"}}},
        "error_codes": {"type": "array", "items": {"type": "string"}}}},
    "ApiIndex": {"type": "object", "properties": {
        "name": {"type": "string"}, "version": {"type": "string"}, "api_version": {"type": "string"},
        "links": {"type": "array", "items": {"type": "object", "properties": {
            "rel": {"type": "string"}, "href": {"type": "string"},
            "methods": {"type": "array", "items": {"type": "string"}}}}}}},
}

PATHS = {
    "": {"get": operation(
        "Meta", "API index: name, version and public links (built from the URL map)", [], 200, envelope(ref("ApiIndex")),
        {"status": 200, "message": "Medi_Manage_Api v1", "data": {
            "name": "Medi_Manage_Api", "version": "1.0.0", "api_version": "v1",
            "links": [{"rel": "meta.app_config", "href": "/api/v1/app-config", "methods": ["GET"]},
                      {"rel": "auth.login", "href": "/api/v1/auth/login", "methods": ["POST"]},
                      {"rel": "user.create_user", "href": "/api/v1/users", "methods": ["POST"]}]}},
        [UPGRADE, METHOD], public=True)},
    "/app-config": {"get": operation(
        "Meta", "Client bootstrap: min_app_version, enums, upload limits, server_time (UTC), error codes", [], 200,
        envelope(ref("AppConfig")), {"status": 200, "message": "App configuration", "data": APP_CONFIG_EXAMPLE},
        [METHOD], public=True, notes="Exempt from the X-App-Version gate.")},
    "/openapi.json": {"get": operation(
        "Meta", "This OpenAPI document (404 when ENABLE_DOCS is false)", [], 200, {"type": "object"},
        {"openapi": "3.0.3", "info": {"title": "Medi_Manage_Api", "version": "1.0.0"}, "paths": {}},
        [DOCS_OFF], public=True)},
    "/devices": {"post": operation(
        "Devices", "Register or update this device's push token (upsert on token)", ["admin", "user"], 201,
        envelope(ref("Device")), {"status": 201, "message": "Device registered", "data": DEVICE_EXAMPLE},
        [error(400, "VALIDATION_ERROR", "Validation failed",
               {"platform": "must be one of: android, ios", "token": "must be at least 8 characters"}), UNAUTHORIZED],
        body=ref("DeviceInput"), body_example={"token": "fcm-token-abc123456", "platform": "android", "app_version": "1.4.0"},
        multipart=True, location=True,
        notes="201 when the token is new; 200 'Device updated' when the token already exists (it is re-assigned to "
              "the caller and re-activated). Storage only: no push is sent yet.")},
    "/devices/{device_id}": {"delete": operation(
        "Devices", "Unregister one of your devices (soft delete: is_active=false)", ["admin", "user"], 200,
        envelope(ref("Device")),
        {"status": 200, "message": "Device unregistered",
         "data": {**DEVICE_EXAMPLE, "app_version": "1.5.0", "is_active": False}},
        [UNAUTHORIZED, error(404, "NOT_FOUND", "Device not found")], params=[path_param("device_id")],
        notes="Other users' devices and already-removed devices return 404.")},
}
