"""Part 3: auth/users/admins security, app/mobile endpoints, docs and URL-structure checks."""
import os
import re
import sqlite3
from collections import Counter

import pytest
from flask_jwt_extended import create_refresh_token

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASSWORD = "Strong#Pass1"


# ------------------------------------------------------------------ helpers
def _otp(sender):
    return re.search(r"\b(\d{6})\b", sender.sent_messages[-1]["body"]).group(1)


def _wrong(otp):
    return "000000" if otp != "000000" else "111111"


def _signup(client, api, email, **extra):
    res = client.post(f"{api}/users", json={"name": "Test User", "email": email, "password": PASSWORD, **extra})
    assert res.status_code == 201, res.get_json()
    return res.get_json()["data"]["user_id"]


def _approved_user(client, api, admin_headers, email):
    user_id = _signup(client, api, email)
    assert client.post(f"{api}/users/{user_id}/approve", headers=admin_headers).status_code == 200
    return user_id


def _login(client, api, sender, email, account_type="user", password=PASSWORD):
    sender.clear()
    res = client.post(f"{api}/auth/login", json={"email": email, "password": password, "account_type": account_type})
    assert res.status_code == 200, res.get_json()
    account_id = res.get_json()["data"]["account_id"]
    verify = client.post(f"{api}/auth/verify-otp", json={"account_id": account_id, "otp": _otp(sender),
                                                          "account_type": account_type})
    assert verify.status_code == 200, verify.get_json()
    return verify.get_json()["data"]


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _db_role(table, id_col, value):
    conn = sqlite3.connect(os.getenv("DATABASE_NAME", "test_medical_shop.db"))
    try:
        return conn.execute(f"SELECT role FROM {table} WHERE {id_col} = ?", (value,)).fetchone()[0]
    finally:
        conn.close()


# ------------------------------------------------------------------ signup / OTP
def test_signup_role_always_user_even_with_admin_header(client, api):
    res = client.post(f"{api}/users", json={"name": "Mallory", "email": "mal@example.com", "password": PASSWORD},
                      headers={"Admin": "true"})
    assert res.status_code == 201
    data = res.get_json()["data"]
    assert data["role"] == "user" and data["is_approved"] is False
    assert res.headers["Location"].endswith(f"/users/{data['user_id']}")
    assert _db_role("Users", "user_id", data["user_id"]) == "user"
    rejected = client.post(f"{api}/users", json={"name": "M2", "email": "m2@example.com", "password": PASSWORD,
                                                 "role": "admin"})
    assert rejected.status_code == 400 and "role" in rejected.get_json()["fields"]


def test_otp_never_in_responses(client, api, admin_headers, fake_email_sender):
    _approved_user(client, api, admin_headers, "otp@example.com")
    login = client.post(f"{api}/auth/login", json={"email": "otp@example.com", "password": PASSWORD})
    otp = _otp(fake_email_sender)
    assert otp not in login.get_data(as_text=True)
    assert "otp" not in login.get_json()["data"]
    reset = client.post(f"{api}/auth/password-reset/request", json={"email": "otp@example.com"})
    reset_otp = _otp(fake_email_sender)
    assert reset_otp not in reset.get_data(as_text=True)


def test_reset_otp_unusable_at_login_verify(client, api, admin_headers, fake_email_sender):
    user_id = _approved_user(client, api, admin_headers, "reset@example.com")
    client.post(f"{api}/auth/password-reset/request", json={"email": "reset@example.com"})
    reset_otp = _otp(fake_email_sender)
    res = client.post(f"{api}/auth/verify-otp", json={"account_id": user_id, "otp": reset_otp})
    assert res.status_code == 400 and res.get_json()["code"] == "VALIDATION_ERROR"
    ok = client.post(f"{api}/auth/password-reset/confirm", json={
        "email": "reset@example.com", "otp": reset_otp, "new_password": "Another#Pass2"})
    assert ok.status_code == 200
    _login(client, api, fake_email_sender, "reset@example.com", password="Another#Pass2")


def test_five_wrong_otps_invalidate_it(client, api, admin_headers, fake_email_sender):
    user_id = _approved_user(client, api, admin_headers, "brute@example.com")
    client.post(f"{api}/auth/login", json={"email": "brute@example.com", "password": PASSWORD})
    otp = _otp(fake_email_sender)
    for _ in range(4):
        res = client.post(f"{api}/auth/verify-otp", json={"account_id": user_id, "otp": _wrong(otp)})
        assert res.status_code == 400
    fifth = client.post(f"{api}/auth/verify-otp", json={"account_id": user_id, "otp": _wrong(otp)})
    assert fifth.status_code == 429 and fifth.get_json()["code"] == "RATE_LIMITED"
    after = client.post(f"{api}/auth/verify-otp", json={"account_id": user_id, "otp": otp})
    assert after.status_code == 400  # invalidated: even the right code no longer works


def test_generic_reset_response_for_unknown_email(client, api, admin_headers, fake_email_sender):
    _approved_user(client, api, admin_headers, "known@example.com")
    fake_email_sender.clear()
    known = client.post(f"{api}/auth/password-reset/request", json={"email": "known@example.com"})
    unknown = client.post(f"{api}/auth/password-reset/request", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 200
    assert known.get_json() == unknown.get_json()
    assert len(fake_email_sender.sent_messages) == 1


# ------------------------------------------------------------------ account state / tokens
def test_unapproved_and_blocked_cannot_login_or_refresh(client, api, admin_headers, fake_email_sender):
    user_id = _signup(client, api, "state@example.com")
    res = client.post(f"{api}/auth/login", json={"email": "state@example.com", "password": PASSWORD})
    assert res.status_code == 403 and res.get_json()["code"] == "ACCOUNT_NOT_APPROVED"

    client.post(f"{api}/users/{user_id}/approve", headers=admin_headers)
    tokens = _login(client, api, fake_email_sender, "state@example.com")
    client.post(f"{api}/users/{user_id}/block", headers=admin_headers)

    res = client.post(f"{api}/auth/login", json={"email": "state@example.com", "password": PASSWORD})
    assert res.status_code == 403 and res.get_json()["code"] == "ACCOUNT_BLOCKED"
    res = client.post(f"{api}/auth/refresh", headers=_bearer(tokens["refresh_token"]))
    assert res.status_code == 403 and res.get_json()["code"] == "ACCOUNT_BLOCKED"


def test_refresh_rereads_role_from_db_and_rotates(app, client, api, admin_headers):
    user_id = _approved_user(client, api, admin_headers, "rotate@example.com")
    with app.app_context():  # forged claim: role=admin on a customer account
        forged = create_refresh_token(identity=user_id, additional_claims={"role": "admin", "account_type": "user"})
    res = client.post(f"{api}/auth/refresh", headers=_bearer(forged))
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["role"] == "user" and data["refresh_token"] != forged
    assert client.get(f"{api}/users", headers=_bearer(data["access_token"])).status_code == 403
    reuse = client.post(f"{api}/auth/refresh", headers=_bearer(forged))
    assert reuse.status_code == 401 and reuse.get_json()["code"] == "TOKEN_INVALID"
    assert client.post(f"{api}/auth/refresh", headers=_bearer(data["refresh_token"])).status_code == 200


def test_logout_revokes_access_and_refresh(client, api, admin_headers, fake_email_sender):
    _approved_user(client, api, admin_headers, "bye@example.com")
    tokens = _login(client, api, fake_email_sender, "bye@example.com")
    assert client.get(f"{api}/users/me", headers=_bearer(tokens["access_token"])).status_code == 200
    out = client.post(f"{api}/auth/logout", json={"refresh_token": tokens["refresh_token"]},
                      headers=_bearer(tokens["access_token"]))
    assert out.status_code == 200 and out.get_json()["data"]["revoked"] == ["access", "refresh"]
    me = client.get(f"{api}/users/me", headers=_bearer(tokens["access_token"]))
    assert me.status_code == 401 and me.get_json()["code"] == "TOKEN_INVALID"
    assert client.post(f"{api}/auth/refresh", headers=_bearer(tokens["refresh_token"])).status_code == 401


# ------------------------------------------------------------------ users / admins
def test_users_me_whitelist_and_current_password(client, api, make_headers):
    user_id = _signup(client, api, "me@example.com")
    headers = make_headers(user_id, "user")
    for field, value in (("role", "admin"), ("is_approved", True), ("is_blocked", False), ("user_id", "X")):
        res = client.patch(f"{api}/users/me", json={field: value}, headers=headers)
        assert res.status_code == 400 and field in res.get_json()["fields"]
    ok = client.patch(f"{api}/users/me", json={"name": "New Name", "address": "Addr", "phone_number": "+919800011122",
                                               "pin_code": "411001"}, headers=headers)
    assert ok.status_code == 200 and ok.get_json()["data"]["name"] == "New Name"
    missing = client.patch(f"{api}/users/me", json={"email": "me2@example.com"}, headers=headers)
    assert missing.status_code == 400 and "current_password" in missing.get_json()["fields"]
    wrong = client.patch(f"{api}/users/me", json={"password": "Another#Pass2", "current_password": "nope-nope"},
                         headers=headers)
    assert wrong.status_code == 400 and "current_password" in wrong.get_json()["fields"]
    short = client.patch(f"{api}/users/me", json={"password": "short", "current_password": PASSWORD}, headers=headers)
    assert short.status_code == 400 and "password" in short.get_json()["fields"]
    good = client.patch(f"{api}/users/me", json={"email": "me2@example.com", "current_password": PASSWORD},
                        headers=headers)
    assert good.status_code == 200 and good.get_json()["data"]["email"] == "me2@example.com"


def test_user_cannot_read_or_update_another_user(client, api, make_headers):
    alice = _signup(client, api, "alice2@example.com")
    bob = _signup(client, api, "bob2@example.com")
    headers = make_headers(alice, "user")
    assert client.get(f"{api}/users/{alice}", headers=headers).status_code == 200
    other = client.get(f"{api}/users/{bob}", headers=headers)
    assert other.status_code == 404 and other.get_json()["code"] == "NOT_FOUND"
    upd = client.patch(f"{api}/users/{bob}", json={"name": "x"}, headers=headers)
    assert upd.status_code == 403 and upd.get_json()["code"] == "FORBIDDEN"
    assert client.delete(f"{api}/users/{bob}", headers=headers).status_code == 403


def test_user_soft_delete_and_rowcount_404(client, api, admin_headers):
    user_id = _signup(client, api, "gone@example.com")
    res = client.delete(f"{api}/users/{user_id}", headers=admin_headers)
    assert res.status_code == 200 and res.get_json()["data"]["is_deleted"] is True
    assert _db_role("Users", "user_id", user_id) == "deleted"  # row kept (soft delete)
    again = client.delete(f"{api}/users/{user_id}", headers=admin_headers)
    assert again.status_code == 404 and again.get_json()["code"] == "NOT_FOUND"
    assert client.post(f"{api}/users/UID_missing/approve", headers=admin_headers).status_code == 404


def test_last_admin_protected(client, api, admin_headers):
    created = client.post(f"{api}/admins", json={"name": "Solo", "email": "solo@example.com", "password": PASSWORD},
                          headers=admin_headers)
    assert created.status_code == 201
    assert created.headers["Location"].endswith(f"/admins/{created.get_json()['data']['admin_id']}")
    admins = client.get(f"{api}/admins", query_string={"limit": 100}, headers=admin_headers).get_json()["data"]
    active = [a["admin_id"] for a in admins if a["role"] == "admin"]
    for admin_id in active[:-1]:
        assert client.delete(f"{api}/admins/{admin_id}", headers=admin_headers).status_code == 200
    last = active[-1]
    res = client.delete(f"{api}/admins/{last}", headers=admin_headers)
    assert res.status_code == 409 and res.get_json()["code"] == "CONFLICT"
    demote = client.patch(f"{api}/admins/{last}", json={"role": "disabled"}, headers=admin_headers)
    assert demote.status_code == 409


def test_admin_writes_are_audited(client, api, admin_headers):
    user_id = _signup(client, api, "audit@example.com")
    client.post(f"{api}/users/{user_id}/block", headers=admin_headers)
    logs = client.get(f"{api}/audit-logs", query_string={"entity_id": user_id}, headers=admin_headers).get_json()["data"]
    assert "user.block" in {log["action"] for log in logs}


# ------------------------------------------------------------------ app / mobile
def test_app_config_public(client, api):
    res = client.get(f"{api}/app-config")
    assert res.status_code == 200
    data = res.get_json()["data"]
    for key in ("min_app_version", "enums", "uploads", "server_time", "error_codes"):
        assert key in data
    assert data["server_time"].endswith("Z")
    assert {"schedule_types", "dosage_forms", "order_statuses", "units"} <= set(data["enums"])
    assert "UPGRADE_REQUIRED" in data["error_codes"]


def test_version_gate_and_exemptions(app, client, api, admin_headers):
    app.config["MIN_APP_VERSION"] = "2.1.0"
    old = {"X-App-Version": "2.0.9"}
    res = client.get(f"{api}/products", headers={**admin_headers, **old})
    assert res.status_code == 426 and res.get_json()["code"] == "UPGRADE_REQUIRED"
    assert client.get(f"{api}/products", headers={**admin_headers, "X-App-Version": "2.10.0"}).status_code == 200
    assert client.get(f"{api}/products", headers={**admin_headers, "X-App-Version": "2.1.0"}).status_code == 200
    for path in ("/health", "/health/ready", f"{api}/app-config", "/api/docs"):
        assert client.get(path, headers=old).status_code == 200, path
    app.config["MIN_APP_VERSION"] = ""
    assert client.get(f"{api}/products", headers={**admin_headers, **old}).status_code == 200


def test_device_register_and_unregister_own_only(client, api, make_headers):
    alice, bob = make_headers("UID_alice", "user"), make_headers("UID_bob", "user")
    body = {"token": "fcm-token-123456789", "platform": "android", "app_version": "1.0.0"}
    first = client.post(f"{api}/devices", json=body, headers=alice)
    assert first.status_code == 201 and "Location" in first.headers
    device_id = first.get_json()["data"]["device_id"]
    again = client.post(f"{api}/devices", json={**body, "app_version": "1.1.0"}, headers=alice)
    assert again.status_code == 200 and again.get_json()["data"]["device_id"] == device_id
    bad = client.post(f"{api}/devices", json={"token": "x", "platform": "web"}, headers=alice)
    assert bad.status_code == 400 and {"token", "platform"} <= set(bad.get_json()["fields"])
    assert client.delete(f"{api}/devices/{device_id}", headers=bob).status_code == 404
    gone = client.delete(f"{api}/devices/{device_id}", headers=alice)
    assert gone.status_code == 200 and gone.get_json()["data"]["is_active"] is False
    assert client.delete(f"{api}/devices/{device_id}", headers=alice).status_code == 404


def test_api_index(client, api):
    res = client.get(api)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["name"] and data["version"]
    hrefs = {link["href"] for link in data["links"]}
    assert f"{api}/app-config" in hrefs and f"{api}/auth/login" in hrefs
    assert f"{api}/users/me" not in hrefs and f"{api}/admins" not in hrefs  # public links only


# ------------------------------------------------------------------ docs
def test_openapi_valid_and_covers_every_v1_route(app, client, api):
    res = client.get(f"{api}/openapi.json")
    assert res.status_code == 200
    spec = res.get_json()
    assert spec["openapi"].startswith("3.")
    assert spec["components"]["securitySchemes"]["bearerAuth"]["scheme"] == "bearer"
    assert spec["x-route-check"] == {"undocumented": [], "unrouted": []}
    documented = {(m.upper(), p) for p, ops in spec["paths"].items() for m in ops}
    for rule in app.url_map.iter_rules():
        if rule.rule == api or rule.rule.startswith(api + "/"):
            path = re.sub(r"<(?:[^:<>]+:)?([^<>]+)>", r"{\1}", rule.rule)
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                assert (method, path) in documented, (method, path)
    schemas = spec["components"]["schemas"]
    for path, ops in spec["paths"].items():
        for op in ops.values():
            assert op["tags"] and op["responses"]
            for response in op["responses"].values():
                for media in response.get("content", {}).values():
                    ref = media["schema"].get("$ref")
                    if ref:
                        assert ref.rsplit("/", 1)[-1] in schemas, ref
    # Part 3 fragments carry a success example and error examples with a `code`.
    from app.openapi import admins, auth, meta, users
    for module in (auth, users, admins, meta):
        for ops in module.PATHS.values():
            for op in ops.values():
                statuses = op["responses"]
                assert any(s.startswith("2") and "example" in statuses[s]["content"]["application/json"]
                           for s in statuses)
                errors = [r["content"]["application/json"] for s, r in statuses.items() if s[0] in "45"]
                assert errors
                for media in errors:
                    examples = [media["example"]] if "example" in media else [e["value"] for e in media["examples"].values()]
                    assert all(e.get("code") for e in examples)


def test_docs_404_when_disabled(app, client, api):
    app.config["ENABLE_DOCS"] = False
    for path in (f"{api}/openapi.json", "/api/docs", "/dox"):
        res = client.get(path)
        assert res.status_code == 404 and res.get_json()["code"] == "NOT_FOUND", path
    app.config["ENABLE_DOCS"] = True


# ------------------------------------------------------------------ D1: URL structure (from url_map)
ROOT_ALLOWED = {"/health", "/health/ready", "/api/docs"}
LEGACY_REDIRECTS = {"/dox"}  # permanent redirect to /api/docs (kept on request; 404 when docs are off)


def _rules(app):
    # `static` is Flask's built-in static-file rule, not an API route.
    return [r for r in app.url_map.iter_rules() if r.endpoint != "static"]


def test_every_rule_is_v1_health_or_docs(app, api):
    for rule in _rules(app):
        path = rule.rule
        assert (path == api or path.startswith(api + "/") or path in ROOT_ALLOWED
                or path in LEGACY_REDIRECTS), path


def test_no_old_style_urls(app, api):
    for rule in _rules(app):
        path = rule.rule
        assert not re.match(r"^/(admin|user)(/|$)", path), path
        for segment in path.split("/"):
            if segment.startswith("<"):
                continue
            assert re.fullmatch(r"[a-z0-9.\-]*", segment), f"non kebab-case segment {segment!r} in {path}"


def test_no_duplicate_rules_or_endpoint_names(app):
    pairs = Counter((r.rule, m) for r in _rules(app) for m in r.methods - {"HEAD", "OPTIONS"})
    assert not [p for p, n in pairs.items() if n > 1]
    endpoints = Counter(r.endpoint for r in _rules(app))
    assert not [e for e, n in endpoints.items() if n > 1]


# ------------------------------------------------------------------ 401/403 on Part 3 endpoints
ADMIN_ONLY = [
    ("get", "/users"), ("patch", "/users/UID_x"), ("delete", "/users/UID_x"),
    ("post", "/users/UID_x/approve"), ("post", "/users/UID_x/block"), ("post", "/users/UID_x/unblock"),
    ("get", "/admins"), ("post", "/admins"), ("get", "/admins/AID_x"), ("patch", "/admins/AID_x"),
    ("delete", "/admins/AID_x"),
]
ANY_ROLE = [
    ("get", "/users/me"), ("patch", "/users/me"), ("get", "/users/UID_x"), ("post", "/devices"),
    ("delete", "/devices/DEV_x"), ("post", "/auth/logout"), ("post", "/auth/refresh"),
]


@pytest.mark.parametrize("method,path", ADMIN_ONLY + ANY_ROLE)
def test_part3_endpoints_require_token(client, api, method, path):
    res = getattr(client, method)(f"{api}{path}", json={})
    assert res.status_code == 401
    body = res.get_json()
    assert body["code"] == "UNAUTHORIZED" and {"status", "message", "code"} <= set(body)


@pytest.mark.parametrize("method,path", ADMIN_ONLY)
def test_part3_admin_endpoints_forbid_users(client, api, user_headers, method, path):
    res = getattr(client, method)(f"{api}{path}", json={}, headers=user_headers)
    assert res.status_code == 403 and res.get_json()["code"] == "FORBIDDEN"


@pytest.mark.parametrize("method", ["get", "patch"])
def test_users_me_forbidden_for_admin_token(client, api, admin_headers, method):
    res = getattr(client, method)(f"{api}/users/me", json={"name": "x"}, headers=admin_headers)
    assert res.status_code == 403 and res.get_json()["code"] == "FORBIDDEN"


def test_error_shapes_include_code(client, api, admin_headers):
    cases = [
        client.post(f"{api}/users", json={"name": "", "email": "bad", "password": "x"}),
        client.get(f"{api}/admins/AID_missing", headers=admin_headers),
        client.put(f"{api}/users", headers=admin_headers),
        client.post(f"{api}/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}),
        client.post(f"{api}/users", data="{bad", content_type="application/json"),
    ]
    for res in cases:
        body = res.get_json()
        assert body["status"] == res.status_code and body["code"] and body["message"]
        assert "Traceback" not in res.get_data(as_text=True)
    assert cases[0].get_json()["fields"]


# ------------------------------------------------------------------ response.md coverage
def test_every_v1_rule_documented_in_response_md(app, api):
    with open(os.path.join(ROOT, "response.md"), encoding="utf-8") as fh:
        text = fh.read()
    documented = set(re.findall(r"^#{3,4} [^\n]*?\b(GET|POST|PATCH|PUT|DELETE) (/\S*)", text, re.M))
    missing = []
    for rule in app.url_map.iter_rules():
        if rule.rule == api or rule.rule.startswith(api + "/"):
            path = re.sub(r"<(?:[^:<>]+:)?([^<>]+)>", r"{\1}", rule.rule)
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                if (method, path) not in documented:
                    missing.append(f"{method} {path}")
    assert not missing, missing
