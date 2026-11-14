from flask import Blueprint, current_app, jsonify

from app.db import get_db
from app.utils.responses import error_response

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"], strict_slashes=False)
def health():
    """Liveness: the process is up (no dependencies checked)."""
    return jsonify({
        "status": "healthy",
        "service": "Medi_Manage_Api"
    }), 200


@health_bp.route("/health/ready", methods=["GET"], strict_slashes=False)
def ready():
    """Readiness: database reachable; Redis-backed OTP store reachable when configured."""
    checks = {"database": "ok", "cache": "skipped"}
    try:
        conn = get_db()
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except Exception:
        current_app.logger.exception("Readiness check: database unavailable")
        return error_response("Service not ready: database unavailable", 503, "INTERNAL_ERROR")
    client = getattr(current_app.extensions.get("otp_store"), "_client", None)
    if client is not None:
        try:
            client.ping()
            checks["cache"] = "ok"
        except Exception:
            current_app.logger.exception("Readiness check: cache unavailable")
            return error_response("Service not ready: cache unavailable", 503, "INTERNAL_ERROR")
    return jsonify({"status": "ready", "service": "Medi_Manage_Api", "checks": checks}), 200
