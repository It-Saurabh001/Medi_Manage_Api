"""OpenAPI 3 document built from every `app/openapi/*.py` fragment (Part 3).

Fragments expose `PATHS` (keys relative to API_PREFIX; "" is the API index) and optionally
`SCHEMAS`. The result is cross-checked against `app.url_map`: `x-route-check` lists v1
operations that are routed but undocumented (and vice versa); tests require both lists empty.
"""
import copy
import importlib
import pkgutil
import re

from app.api_constants import API_NAME, API_VERSION, ERROR_CODES

_SKIP_MODULES = {"spec"}
_RULE_PARAM = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")
_IGNORED_METHODS = {"HEAD", "OPTIONS"}

BEARER_SCHEME = {"type": "http", "scheme": "bearer", "bearerFormat": "JWT",
                 "description": "Access token from POST /auth/verify-otp (refresh token only for POST /auth/refresh)"}


def fragment_modules():
    import app.openapi as package

    modules = []
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda i: i.name):
        if info.name.startswith("_") or info.name in _SKIP_MODULES:
            continue
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        if isinstance(getattr(module, "PATHS", None), dict):
            modules.append(module)
    return modules


def rule_to_openapi(rule):
    """'/api/v1/users/<user_id>' -> '/api/v1/users/{user_id}'."""
    return _RULE_PARAM.sub(r"{\1}", rule)


def api_prefix(app):
    return (app.config.get("API_PREFIX") or "/api/v1").rstrip("/")


def routed_v1_operations(app):
    """{(METHOD, openapi_path)} for every url_map rule under API_PREFIX."""
    prefix = api_prefix(app)
    ops = set()
    for rule in app.url_map.iter_rules():
        path = rule_to_openapi(rule.rule).rstrip("/") or "/"
        if path != prefix and not path.startswith(prefix + "/"):
            continue
        for method in rule.methods - _IGNORED_METHODS:
            ops.add((method, path))
    return ops


def build_spec(app):
    prefix = api_prefix(app)
    paths, schemas, tags = {}, {}, []
    for module in fragment_modules():
        schemas.update(copy.deepcopy(getattr(module, "SCHEMAS", {}) or {}))
        for rel, operations in module.PATHS.items():
            full = prefix + rel if rel not in ("", "/") else prefix
            paths.setdefault(full, {}).update(copy.deepcopy(operations))
            for operation in operations.values():
                for tag in operation.get("tags", []):
                    if tag not in tags:
                        tags.append(tag)

    documented = {(method.upper(), path) for path, ops in paths.items() for method in ops}
    routed = routed_v1_operations(app)
    return {
        "openapi": "3.0.3",
        "info": {
            "title": API_NAME,
            "version": API_VERSION,
            "description": ("Pharmacy management API (v1). All errors use `{status, message, code, fields?}`; "
                            "see `x-error-codes` for the code list and suggested client action."),
        },
        "servers": [{"url": "/"}],
        "tags": [{"name": tag} for tag in tags],
        "security": [{"bearerAuth": []}],
        "paths": dict(sorted(paths.items())),
        "components": {"schemas": schemas, "securitySchemes": {"bearerAuth": BEARER_SCHEME}},
        "x-error-codes": [{"code": code, "client_action": action} for code, action in ERROR_CODES.items()],
        "x-route-check": {
            "undocumented": [f"{m} {p}" for m, p in sorted(routed - documented)],
            "unrouted": [f"{m} {p}" for m, p in sorted(documented - routed)],
        },
    }
