"""Swagger UI at /api/docs and the legacy /dox redirect (both 404 when ENABLE_DOCS is false)."""
from flask import Blueprint, abort, current_app, redirect, url_for

docs_bp = Blueprint("docs", __name__)

# Pinned swagger-ui-dist version (served from jsDelivr; see requirements/base.txt note).
SWAGGER_UI_VERSION = "5.17.14"

_PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Medi_Manage_Api docs</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{v}/swagger-ui.css">
<style>body{{margin:0;background:#fafafa}}</style></head>
<body><div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{v}/swagger-ui-bundle.js"></script>
<script>window.ui = SwaggerUIBundle({{url: "{spec}", dom_id: "#swagger-ui", persistAuthorization: true}});</script>
</body></html>"""


def _require_docs():
    if not current_app.config.get("ENABLE_DOCS"):
        abort(404)


@docs_bp.route("/api/docs", methods=["GET"], strict_slashes=False)
def swagger_ui():
    _require_docs()
    html = _PAGE.format(v=SWAGGER_UI_VERSION, spec=url_for("meta.openapi_json"))
    return current_app.response_class(html, mimetype="text/html")


@docs_bp.route("/dox", methods=["GET"], strict_slashes=False)
def legacy_dox():
    """Legacy documentation URL: permanent redirect to /api/docs."""
    _require_docs()
    return redirect(url_for("docs.swagger_ui"), code=301)
