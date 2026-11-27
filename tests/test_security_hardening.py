"""Security hardening: auth abuse limits, session revocation, opt-in switches, edge guard, headers, config."""
import io
import re

import pytest

from app.db import db_connection
from app.services import account_service as acc
from app.services import auth_service

PASSWORD = "Strong#Pass1"
PDF = b"%PDF-1.4\n%test\n"


# ------------------------------------------------------------------ helpers
def _otp(sender):
    return re.search(r"\b(\d{6})\b", sender.sent_messages[-1]["body"]).group(1)


def _wrong(otp):
    return "000000" if otp != "000000" else "111111"


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _approved_user(client, api, admin_headers, email):
    res = client.post(f"{api}/users", json={"name": "Test User", "email": email, "password": PASSWORD})
    assert res.status_code == 201, res.get_json()
    user_id = res.get_json()["data"]["user_id"]
    assert client.post(f"{api}/users/{user_id}/approve", headers=admin_headers).status_code == 200
    return user_id


def _login(client, api, sender, email, account_type="user", password=PASSWORD):
    sender.clear()
    res = client.post(f"{api}/auth/login", json={"email": email, "password": password, "account_type": account_type})
    assert res.status_code == 200, res.get_json()
    verify = client.post(f"{api}/auth/verify-otp", json={"account_id": res.get_json()["data"]["account_id"],
                                                          "otp": _otp(sender), "account_type": account_type})
    assert verify.status_code == 200, verify.get_json()
    return verify.get_json()["data"]


def _admin(app, email, owner=False):
    with app.app_context():
        with db_connection(immediate=True) as conn:
            return acc.insert_admin(conn, {"name": email, "email": email, "password": PASSWORD},
                                    is_approved=True, is_owner=owner)


# ------------------------------------------------------------------ auth abuse protection
def test_reset_cannot_be_reissued_to_reset_the_attempt_counter(app, client, api, admin_headers, fake_email_sender):
    _approved_user(client, api, admin_headers, "victim@example.com")
    fake_email_sender.clear()
    first = client.post(f"{api}/auth/password-reset/request", json={"email": "victim@example.com"})
    again = client.post(f"{api}/auth/password-reset/request", json={"email": "victim@example.com"})
    # Same response both times (no enumeration), but only one code inside the cooldown
    assert first.status_code == again.status_code == 200
    assert first.get_json()["message"] == again.get_json()["message"]
    assert len(fake_email_sender.sent_messages) == 1


def test_otp_budget_survives_new_codes(app, client, api, admin_headers, fake_email_sender):
    app.config["OTP_VERIFY_BUDGET"] = 6
    user_id = _approved_user(client, api, admin_headers, "budget@example.com")
    for _round in range(2):  # attacker knows the password and keeps requesting fresh codes
        client.post(f"{api}/auth/login", json={"email": "budget@example.com", "password": PASSWORD})
        otp = _otp(fake_email_sender)
        for _ in range(3):
            client.post(f"{api}/auth/verify-otp", json={"account_id": user_id, "otp": _wrong(otp)})
    client.post(f"{api}/auth/login", json={"email": "budget@example.com", "password": PASSWORD})
    res = client.post(f"{api}/auth/verify-otp", json={"account_id": user_id, "otp": _otp(fake_email_sender)})
    assert res.status_code == 429 and res.get_json()["code"] == "RATE_LIMITED"  # even the right code


def test_login_rate_limited_per_account_and_per_ip(app, client, api):
    app.config["AUTH_ACCOUNT_RATE_LIMIT"] = 3
    for _ in range(3):
        assert client.post(f"{api}/auth/login", json={"email": "x@example.com", "password": "wrongpass1"}
                           ).status_code == 401
    blocked = client.post(f"{api}/auth/login", json={"email": "x@example.com", "password": "wrongpass1"})
    assert blocked.status_code == 429 and blocked.get_json()["code"] == "RATE_LIMITED"
    assert "Retry-After" in blocked.headers
    app.config["AUTH_IP_RATE_LIMIT"] = 2
    client.post(f"{api}/auth/password-reset/request", json={"email": "a@example.com"})
    client.post(f"{api}/auth/password-reset/request", json={"email": "b@example.com"})
    assert client.post(f"{api}/auth/password-reset/request", json={"email": "c@example.com"}).status_code == 429


def test_signup_rate_limited(app, client, api):
    app.config["SIGNUP_RATE_LIMIT"] = 1
    ok = client.post(f"{api}/users", json={"name": "A", "email": "s1@example.com", "password": PASSWORD})
    assert ok.status_code == 201
    res = client.post(f"{api}/users", json={"name": "B", "email": "s2@example.com", "password": PASSWORD})
    assert res.status_code == 429


# ------------------------------------------------------------------ session revocation
def test_block_and_delete_revoke_existing_tokens_with_known_codes(client, api, admin_headers, fake_email_sender):
    user_id = _approved_user(client, api, admin_headers, "rev@example.com")
    tokens = _login(client, api, fake_email_sender, "rev@example.com")
    assert client.get(f"{api}/users/me", headers=_bearer(tokens["access_token"])).status_code == 200

    client.post(f"{api}/users/{user_id}/block", headers=admin_headers)
    res = client.get(f"{api}/users/me", headers=_bearer(tokens["access_token"]))
    assert res.status_code == 403 and res.get_json()["code"] == "ACCOUNT_BLOCKED"

    client.post(f"{api}/users/{user_id}/unblock", headers=admin_headers)
    res = client.get(f"{api}/users/me", headers=_bearer(tokens["access_token"]))
    assert res.status_code == 401 and res.get_json()["code"] == "TOKEN_INVALID"  # log in again
    fresh = _login(client, api, fake_email_sender, "rev@example.com")
    assert client.get(f"{api}/users/me", headers=_bearer(fresh["access_token"])).status_code == 200

    client.delete(f"{api}/users/{user_id}", headers=admin_headers)
    res = client.get(f"{api}/users/me", headers=_bearer(fresh["access_token"]))
    assert res.status_code == 401 and res.get_json()["code"] == "UNAUTHORIZED"


def test_password_reset_kills_stolen_refresh_token(client, api, admin_headers, fake_email_sender):
    _approved_user(client, api, admin_headers, "stolen@example.com")
    stolen = _login(client, api, fake_email_sender, "stolen@example.com")
    fake_email_sender.clear()
    client.post(f"{api}/auth/password-reset/request", json={"email": "stolen@example.com"})
    ok = client.post(f"{api}/auth/password-reset/confirm", json={
        "email": "stolen@example.com", "otp": _otp(fake_email_sender), "new_password": "Another#Pass2"})
    assert ok.status_code == 200 and ok.get_json()["data"] is None  # response unchanged
    res = client.post(f"{api}/auth/refresh", headers=_bearer(stolen["refresh_token"]))
    assert res.status_code == 401 and res.get_json()["code"] == "TOKEN_INVALID"
    _login(client, api, fake_email_sender, "stolen@example.com", password="Another#Pass2")


def test_disabled_admin_loses_access_immediately(app, client, api, fake_email_sender):
    _admin(app, "owner@example.com", owner=True)
    victim = _admin(app, "second@example.com")
    owner_tokens = _login(client, api, fake_email_sender, "owner@example.com", account_type="admin")
    second_tokens = _login(client, api, fake_email_sender, "second@example.com", account_type="admin")
    assert client.get(f"{api}/admins", headers=_bearer(second_tokens["access_token"])).status_code == 200
    res = client.patch(f"{api}/admins/{victim}", json={"role": "disabled"},
                       headers=_bearer(owner_tokens["access_token"]))
    assert res.status_code == 200
    res = client.get(f"{api}/admins", headers=_bearer(second_tokens["access_token"]))
    assert res.status_code == 403 and res.get_json()["code"] == "ACCOUNT_BLOCKED"


# ------------------------------------------------------------------ opt-in switches
def test_owner_only_admin_management(app, client, api, fake_email_sender):
    app.config["ADMIN_MANAGEMENT_OWNER_ONLY"] = True
    _admin(app, "boss@example.com", owner=True)
    _admin(app, "staff@example.com")
    boss = _login(client, api, fake_email_sender, "boss@example.com", account_type="admin")
    staff = _login(client, api, fake_email_sender, "staff@example.com", account_type="admin")
    body = {"name": "New", "email": "new-admin@example.com", "password": PASSWORD}
    denied = client.post(f"{api}/admins", json=body, headers=_bearer(staff["access_token"]))
    assert denied.status_code == 403 and denied.get_json()["code"] == "FORBIDDEN"
    assert client.post(f"{api}/admins", json=body, headers=_bearer(boss["access_token"])).status_code == 201


def test_user_email_verification_when_enabled(app, client, api, admin_headers, fake_email_sender):
    app.config["REQUIRE_USER_EMAIL_VERIFICATION"] = True
    fake_email_sender.clear()
    res = client.post(f"{api}/users", json={"name": "V", "email": "verify@example.com", "password": PASSWORD})
    assert res.status_code == 201 and res.get_json()["data"]["otp_required"] is True
    user_id = res.get_json()["data"]["user_id"]
    client.post(f"{api}/users/{user_id}/approve", headers=admin_headers)
    login = client.post(f"{api}/auth/login", json={"email": "verify@example.com", "password": PASSWORD})
    assert login.status_code == 403 and login.get_json()["code"] == "EMAIL_NOT_VERIFIED"
    ok = client.post(f"{api}/auth/verify-otp", json={"email": "verify@example.com", "otp": _otp(fake_email_sender),
                                                      "account_type": "user"})
    assert ok.status_code == 200
    _login(client, api, fake_email_sender, "verify@example.com")


def test_google_link_drops_password_of_unverified_account(app, client, api, monkeypatch):
    app.config["REQUIRE_USER_EMAIL_VERIFICATION"] = True
    # Attacker pre-registers the victim's address with their own password, never verifies it
    client.post(f"{api}/users", json={"name": "Mallory", "email": "gina@example.com", "password": PASSWORD})
    monkeypatch.setattr(auth_service, "verify_google_id_token",
                        lambda raw: {"sub": "g-1", "email": "gina@example.com", "name": "Gina"})
    client.post(f"{api}/auth/google", json={"id_token": "tok"})
    with app.app_context():
        with db_connection() as conn:
            row = conn.execute("SELECT password, auth_provider FROM Users WHERE email = ?",
                               ("gina@example.com",)).fetchone()
    assert row["password"] is None and row["auth_provider"] == "google"


def test_private_prescriptions_get_signed_expiring_urls(app, env_order, monkeypatch):
    import cloudinary
    import cloudinary.uploader

    app.config["PRESCRIPTION_PRIVATE_STORAGE"] = True
    cloudinary.config(cloud_name="demo", api_key="k", api_secret="s")
    calls = []

    def fake_upload(file, **kw):
        calls.append(kw)
        return {"public_id": "MediAdminApp/Prescriptions/abc", "resource_type": "image", "format": "pdf"}

    monkeypatch.setattr(cloudinary.uploader, "upload", fake_upload)
    client, api, headers, order_id = env_order
    res = client.post(f"{api}/orders/{order_id}/prescription", headers=headers, content_type="multipart/form-data",
                      data={"prescription": (io.BytesIO(PDF), "rx.pdf", "application/pdf")})
    url = res.get_json()["data"]["prescription_url"]
    assert res.status_code == 200 and calls[0]["type"] == "private"
    assert url.startswith("https://api.cloudinary.com/") and "expires_at=" in url and "signature=" in url


def test_prescription_url_host_allowlist(app, env_order):
    client, api, headers, _ = env_order
    app.config["ALLOWED_PRESCRIPTION_URL_HOSTS"] = ("res.cloudinary.com",)
    pid = env_order.product_id
    bad = client.post(f"{api}/orders", headers=headers, json={"product_id": pid, "quantity": 1,
                                                               "prescription_url": "https://evil.example/rx.pdf"})
    assert bad.status_code == 400 and "prescription_url" in bad.get_json()["fields"]
    plain = client.post(f"{api}/orders", headers=headers, json={"product_id": pid, "quantity": 1,
                                                                 "prescription_url": "http://res.cloudinary.com/x"})
    assert plain.status_code == 400
    ok = client.post(f"{api}/orders", headers=headers, json={
        "product_id": pid, "quantity": 1, "prescription_url": "https://res.cloudinary.com/demo/rx.pdf"})
    assert ok.status_code == 201


def test_admin_cannot_redirect_customer_email(client, api, admin_headers):
    user_id = _approved_user(client, api, admin_headers, "owner-of-mail@example.com")
    same = client.patch(f"{api}/users/{user_id}", json={"email": "owner-of-mail@example.com", "name": "Renamed"},
                        headers=admin_headers)
    assert same.status_code == 200
    other = client.patch(f"{api}/users/{user_id}", json={"email": "attacker@example.com"}, headers=admin_headers)
    assert other.status_code == 400 and "email" in other.get_json()["fields"]


def test_first_owner_cannot_be_claimed_in_production_without_code(app, client, api):
    app.config["FLASK_ENV"] = "production"
    res = client.post(f"{api}/admins/register", json={"name": "Eve", "email": "eve@example.com",
                                                       "password": PASSWORD})
    assert res.status_code == 403
    app.config["ADMIN_SIGNUP_CODE"] = "a-long-signup-code"
    ok = client.post(f"{api}/admins/register", json={"name": "Owner", "email": "own@example.com",
                                                      "password": PASSWORD, "signup_code": "a-long-signup-code"})
    assert ok.status_code == 201 and ok.get_json()["data"]["is_owner"] is True


# ------------------------------------------------------------------ edge guard + headers
@pytest.mark.parametrize("kwargs, status", [
    ({"path": "/api/v1/products", "headers": {"User-Agent": "sqlmap/1.7"}}, 403),
    ({"path": "/.env"}, 404),
    ({"path": "/.git/config"}, 404),
    ({"path": "/wp-login.php"}, 404),
    ({"path": "/api/v1/products", "query_string": {"q": "1' or '1'='1"}}, 403),
    ({"path": "/api/v1/products", "query_string": {"q": "x union select password from Admin"}}, 403),
    ({"path": "/api/v1/products", "query_string": {"q": "<script>alert(1)</script>"}}, 403),
    ({"path": "/api/v1/products", "query_string": {"q": "../../etc/passwd"}}, 403),
    ({"path": "/api/v1/products", "headers": {"User-Agent": "${jndi:ldap://x/a}"}}, 403),
    ({"path": "/api/v1/products", "query_string": "q=" + "a" * 3000}, 414),
])
def test_edge_guard_blocks_attacks(client, kwargs, status):
    res = client.get(kwargs.pop("path"), **kwargs)
    assert res.status_code == status
    if status == 403:
        assert res.get_json()["code"] == "REQUEST_BLOCKED"


def test_edge_guard_allows_normal_traffic(client, api, user_headers):
    for q in ("paracetamol 500mg", "Dr. O'Brien", "vitamin-c & zinc", "crocin (advance)"):
        res = client.get(f"{api}/products", query_string={"q": q}, headers=user_headers)
        assert res.status_code == 200, (q, res.get_json())


def test_origin_lock_ip_rules_and_global_rate(app, client, api):
    app.config["ORIGIN_AUTH_SECRET"] = "s" * 40
    assert client.get(f"{api}/app-config").get_json()["code"] == "ORIGIN_FORBIDDEN"
    assert client.get(f"{api}/app-config", headers={"X-Origin-Auth": "s" * 40}).status_code == 200
    assert client.get("/health").status_code == 200  # platform health checks stay open
    app.config["ORIGIN_AUTH_SECRET"] = ""

    app.config["IP_BLOCKLIST"] = "127.0.0.0/8"
    assert client.get(f"{api}/app-config").status_code == 403
    app.config["IP_BLOCKLIST"] = ""
    app.config["IP_ALLOWLIST"] = "10.0.0.0/8"
    assert client.get(f"{api}/app-config").status_code == 403
    app.config["IP_ALLOWLIST"] = ""

    app.config["GLOBAL_RATE_LIMIT"] = 2
    client.get(f"{api}/app-config")
    client.get(f"{api}/app-config")
    limited = client.get(f"{api}/app-config")
    assert limited.status_code == 429 and limited.headers.get("Retry-After")


def test_trusted_client_ip_header_only_with_origin_lock(app, client, api):
    app.config["CLIENT_IP_HEADER"] = "CF-Connecting-IP"
    app.config["IP_BLOCKLIST"] = "203.0.113.7"
    spoof = {"CF-Connecting-IP": "203.0.113.7"}
    assert client.get(f"{api}/app-config", headers=spoof).status_code == 200  # ignored without origin lock
    app.config["ORIGIN_AUTH_SECRET"] = "s" * 40
    res = client.get(f"{api}/app-config", headers={**spoof, "X-Origin-Auth": "s" * 40})
    assert res.status_code == 403


def test_security_headers(client, api):
    res = client.get(f"{api}/app-config")
    assert res.headers["X-Content-Type-Options"] == "nosniff"
    assert res.headers["X-Frame-Options"] == "DENY"
    assert res.headers["Cache-Control"] == "no-store"
    assert "frame-ancestors 'none'" in res.headers["Content-Security-Policy"]
    assert "cdn.jsdelivr.net" in client.get("/api/docs").headers["Content-Security-Policy"]


# ------------------------------------------------------------------ configuration
def test_missing_flask_env_fails_closed(monkeypatch):
    from config import get_config
    from config.production import ProductionConfig

    validated = []
    monkeypatch.delenv("FLASK_ENV", raising=False)
    monkeypatch.setattr(ProductionConfig, "validate", classmethod(lambda cls: validated.append(cls)))
    assert get_config() is ProductionConfig and validated == [ProductionConfig]


def test_production_rejects_published_secrets(monkeypatch):
    from config.production import ProductionConfig

    monkeypatch.setenv("JWT_SECRET_KEY", "dev-jwt-fallback-secret-key-456")
    with pytest.raises(ValueError, match="JWT_SECRET_KEY \\(uses a value published"):
        ProductionConfig.validate()


# ------------------------------------------------------------------ fixtures
class _OrderEnv(tuple):
    product_id = None


@pytest.fixture
def env_order(app, client, api, admin_headers, fake_email_sender):
    """Approved customer (real login) with one pending order on a stocked product."""
    _approved_user(client, api, admin_headers, "buyer@example.com")
    tokens = _login(client, api, fake_email_sender, "buyer@example.com")
    headers = _bearer(tokens["access_token"])
    product = client.post(f"{api}/products", headers=admin_headers, json={
        "name": "Paracetamol", "price": 10, "category": "General", "dosage_form": "Tablet"})
    assert product.status_code == 201, product.get_json()
    pid = product.get_json()["data"]["product_id"]
    stock = client.post(f"{api}/products/{pid}/stock/purchase", headers=admin_headers, json={
        "batch_no": "B1", "expiry_date": "2099-12-31", "quantity": 50, "purchase_price": 5})
    assert stock.status_code in (200, 201), stock.get_json()
    order = client.post(f"{api}/orders", headers=headers, json={"product_id": pid, "quantity": 1})
    assert order.status_code == 201, order.get_json()
    env = _OrderEnv((client, api, headers, order.get_json()["data"]["order_id"]))
    env.product_id = pid
    return env
