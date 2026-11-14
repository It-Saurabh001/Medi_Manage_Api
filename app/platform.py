"""Cross-cutting HTTP concerns wired in create_app (Part 3): JWT blocklist, ProxyFix, CORS,
and the X-App-Version gate (426 UPGRADE_REQUIRED)."""
import re

from flask import current_app, request

from app.services.token_blocklist import init_token_blocklist
from app.utils.responses import error_response

_VERSION_RE = re.compile(r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?")
CORS_ALLOW_HEADERS = ["Authorization", "Content-Type", "Idempotency-Key", "X-App-Version"]
CORS_EXPOSE_HEADERS = ["Location", "Idempotent-Replayed", "Allow"]


def parse_version(text):
    """'1.2.3' -> (1, 2, 3); missing parts are 0; unparsable -> None."""
    match = _VERSION_RE.match(str(text or ""))
    if not match:
        return None
    return tuple(int(part or 0) for part in match.groups())


def _exempt(path, prefix):
    return (path.startswith("/health") or path.startswith("/api/docs")
            or path.rstrip("/") == f"{prefix}/app-config")


def version_gate():
    minimum = current_app.config.get("MIN_APP_VERSION") or ""
    if not minimum or request.method == "OPTIONS":
        return None
    prefix = (current_app.config.get("API_PREFIX") or "").rstrip("/")
    if _exempt(request.path, prefix):
        return None
    client = request.headers.get("X-App-Version")
    if client is None:  # non-app clients (web, tools) are not gated
        return None
    required, current = parse_version(minimum), parse_version(client)
    if required is None or (current is not None and current >= required):
        return None
    return error_response("This app version is no longer supported; please update.", 426, "UPGRADE_REQUIRED",
                          fields={"X-App-Version": f"minimum supported version is {minimum}"},
                          headers={"X-Min-App-Version": minimum})


def init_platform(app):
    init_token_blocklist(app)

    proxies = int(app.config.get("TRUSTED_PROXY_COUNT") or 0)
    if proxies > 0:
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=proxies, x_proto=proxies, x_host=proxies, x_port=proxies)

    origins = [o.strip() for o in str(app.config.get("CORS_ORIGINS") or "").split(",") if o.strip()]
    if origins:
        from flask_cors import CORS  # only required when CORS_ORIGINS is configured

        CORS(app, resources={r"/api/*": {"origins": origins}}, allow_headers=CORS_ALLOW_HEADERS,
             expose_headers=CORS_EXPOSE_HEADERS, supports_credentials=False, max_age=600)

    app.before_request(version_gate)
