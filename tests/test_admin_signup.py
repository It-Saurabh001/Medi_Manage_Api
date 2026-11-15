"""Public admin signup (POST /admins/register), approval, owner and last-approved-admin protection."""
import re
import sqlite3
import threading

from app.db import db_connection

PASSWORD = "Strong#Pass1"


def _register(client, api, email, **extra):
    return client.post(f"{api}/admins/register",
                       json={"name": "Admin " + email.split("@")[0], "email": email, "password": PASSWORD, **extra})


def _otp(sender):
    return re.search(r"\b(\d{6})\b", sender.sent_messages[-1]["body"]).group(1)


def _verify_email(client, api, email, sender):
    res = client.post(f"{api}/auth/verify-otp", json={"email": email, "otp": _otp(sender), "account_type": "admin"})
    assert res.status_code == 200, res.get_json()


def _admin_login(client, api, email):
    return client.post(f"{api}/auth/login", json={"email": email, "password": PASSWORD, "account_type": "admin"})


def _audit_actions(app, admin_id):
    with app.app_context():
        with db_connection() as conn:
            rows = conn.execute("SELECT action, details FROM Audit_Log WHERE entity_id = ?", (admin_id,)).fetchall()
    return rows


# ------------------------------------------------------------------ signup + approval flow
def test_first_signup_is_approved_owner(app, client, api, fake_email_sender):
    res = _register(client, api, "owner@example.com")
    assert res.status_code == 201, res.get_json()
    body = res.get_json()
    data = body["data"]
    assert body["message"] == "Admin registered. Verification code sent to your email."
    unverified = _admin_login(client, api, "owner@example.com")
    assert unverified.status_code == 403 and unverified.get_json()["code"] == "EMAIL_NOT_VERIFIED"
    _verify_email(client, api, "owner@example.com", fake_email_sender)
    assert data["is_approved"] is True and data["is_owner"] is True and data["role"] == "admin"
    assert "password" not in data
    assert res.headers["Location"].endswith(f"/admins/{data['admin_id']}")
    assert _admin_login(client, api, "owner@example.com").status_code == 200
    rows = _audit_actions(app, data["admin_id"])
    assert "admin.register" in {r["action"] for r in rows}
    assert all("password" not in r["details"] and "signup_code" not in r["details"] for r in rows)


def test_second_signup_needs_approval_then_login_works(app, client, api, admin_headers, fake_email_sender):
    assert _register(client, api, "owner@example.com").status_code == 201
    res = _register(client, api, "second@example.com", phone_number="+919800000002")
    assert res.status_code == 201
    body = res.get_json()
    assert body["message"] == "Admin registered. Awaiting approval. Verification code sent to your email."
    _verify_email(client, api, "second@example.com", fake_email_sender)
    admin_id = body["data"]["admin_id"]
    assert body["data"]["is_approved"] is False and body["data"]["is_owner"] is False

    denied = _admin_login(client, api, "second@example.com")
    assert denied.status_code == 403 and denied.get_json()["code"] == "ACCOUNT_NOT_APPROVED"

    pending = client.get(f"{api}/admins", query_string={"is_approved": "false"}, headers=admin_headers).get_json()
    assert [a["admin_id"] for a in pending["data"]] == [admin_id]
    approved_list = client.get(f"{api}/admins", query_string={"is_approved": "true"}, headers=admin_headers)
    assert admin_id not in {a["admin_id"] for a in approved_list.get_json()["data"]}

    approved = client.post(f"{api}/admins/{admin_id}/approve", headers=admin_headers)
    assert approved.status_code == 200 and approved.get_json()["data"]["is_approved"] is True
    assert "admin.approve" in {r["action"] for r in _audit_actions(app, admin_id)}

    fake_email_sender.clear()
    login = _admin_login(client, api, "second@example.com")
    assert login.status_code == 200
    verify = client.post(f"{api}/auth/verify-otp", json={"account_id": admin_id, "otp": _otp(fake_email_sender),
                                                          "account_type": "admin"})
    assert verify.status_code == 200 and verify.get_json()["data"]["role"] == "admin"


def test_unapproved_admin_can_be_deleted(client, api, admin_headers):
    _register(client, api, "owner@example.com")
    admin_id = _register(client, api, "pending@example.com").get_json()["data"]["admin_id"]
    assert client.delete(f"{api}/admins/{admin_id}", headers=admin_headers).status_code == 200
    assert client.post(f"{api}/admins/{admin_id}/approve", headers=admin_headers).status_code == 404


def test_approve_requires_admin_token(client, api, user_headers):
    assert client.post(f"{api}/admins/AID_x/approve").status_code == 401
    res = client.post(f"{api}/admins/AID_x/approve", headers=user_headers)
    assert res.status_code == 403 and res.get_json()["code"] == "FORBIDDEN"


def test_duplicate_email_conflict(client, api):
    assert _register(client, api, "dup@example.com").status_code == 201
    res = _register(client, api, "DUP@example.com")
    assert res.status_code == 409
    body = res.get_json()
    assert body["code"] == "CONFLICT" and body["fields"] == {"email": "already registered"}


def test_validation_and_protected_fields(client, api):
    res = client.post(f"{api}/admins/register", json={"name": "", "email": "bad", "password": "short"})
    assert res.status_code == 400
    assert {"name", "email", "password"} <= set(res.get_json()["fields"])
    for field in ("role", "is_approved", "is_blocked", "is_owner"):
        res = _register(client, api, f"{field}@example.com", **{field: True})
        assert res.status_code == 400 and res.get_json()["code"] == "VALIDATION_ERROR", field
        assert field in res.get_json()["fields"]


def test_signup_code_required_when_configured(app, client, api):
    app.config["ADMIN_SIGNUP_CODE"] = "s3cret-code"
    assert client.get(f"{api}/app-config").get_json()["data"]["admin_signup"] == {
        "enabled": True, "code_required": True}
    for extra in ({}, {"signup_code": "wrong"}, {"signup_code": ""}):
        res = _register(client, api, "coded@example.com", **extra)
        assert res.status_code == 403, extra
        assert res.get_json() == {"status": 403, "message": "Invalid signup code", "code": "FORBIDDEN"}
    ok = _register(client, api, "coded@example.com", signup_code="s3cret-code")
    assert ok.status_code == 201 and ok.get_json()["data"]["is_owner"] is True


def test_app_config_code_not_required_by_default(client, api):
    assert client.get(f"{api}/app-config").get_json()["data"]["admin_signup"] == {
        "enabled": True, "code_required": False}


def test_signup_rate_limited(app, client, api):
    app.config["ADMIN_SIGNUP_RATE_LIMIT"] = 2
    assert _register(client, api, "r1@example.com").status_code == 201
    assert _register(client, api, "r2@example.com").status_code == 201
    res = _register(client, api, "r3@example.com")
    assert res.status_code == 429 and res.get_json()["code"] == "RATE_LIMITED"
    assert int(res.headers["Retry-After"]) > 0


def test_concurrent_first_signups_exactly_one_owner(app, api):
    results, barrier = [], threading.Barrier(6)

    def worker(i):
        client = app.test_client()
        barrier.wait()
        res = _register(client, api, f"race{i}@example.com")
        results.append((res.status_code, res.get_json()["data"]))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert [code for code, _ in results] == [201] * 6
    assert sum(d["is_approved"] for _, d in results) == 1
    assert sum(d["is_owner"] for _, d in results) == 1
    conn = sqlite3.connect(app.config["DATABASE_NAME"])
    try:
        assert conn.execute("SELECT COUNT(*) FROM Admin WHERE is_owner = 1").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM Admin WHERE is_approved = 1").fetchone()[0] == 1
    finally:
        conn.close()


# ------------------------------------------------------------------ owner / last approved admin
def test_owner_cannot_be_deleted_or_disabled(client, api, admin_headers):
    owner_id = _register(client, api, "owner@example.com").get_json()["data"]["admin_id"]
    second = _register(client, api, "second@example.com").get_json()["data"]["admin_id"]
    client.post(f"{api}/admins/{second}/approve", headers=admin_headers)
    for res in (client.delete(f"{api}/admins/{owner_id}", headers=admin_headers),
                client.patch(f"{api}/admins/{owner_id}", json={"role": "disabled"}, headers=admin_headers)):
        assert res.status_code == 403
        assert res.get_json() == {"status": 403, "message": "Owner account is protected", "code": "FORBIDDEN"}
    res = client.patch(f"{api}/admins/{owner_id}", json={"is_approved": False}, headers=admin_headers)
    assert res.status_code == 400 and "is_approved" in res.get_json()["fields"]
    # a non-owner approved admin can still be removed while the owner remains
    assert client.delete(f"{api}/admins/{second}", headers=admin_headers).status_code == 200


def test_last_approved_admin_cannot_be_deleted(client, api, admin_headers):
    # Legacy-style database: an admin created via POST /admins (approved, not owner) is the only one.
    only = client.post(f"{api}/admins", json={"name": "Only", "email": "only@example.com", "password": PASSWORD},
                       headers=admin_headers).get_json()["data"]
    assert only["is_approved"] is True and only["is_owner"] is False
    # An unapproved signup does not count as an approved admin.
    pending = _register(client, api, "pending@example.com").get_json()["data"]
    assert pending["is_approved"] is False and pending["is_owner"] is False
    res = client.delete(f"{api}/admins/{only['admin_id']}", headers=admin_headers)
    assert res.status_code == 409
    assert res.get_json() == {"status": 409, "message": "At least one approved admin is required", "code": "CONFLICT"}
    demote = client.patch(f"{api}/admins/{only['admin_id']}", json={"role": "disabled"}, headers=admin_headers)
    assert demote.status_code == 409


# ------------------------------------------------------------------ migration + CLI
def test_migration_keeps_existing_admins_approved(app):
    from app.services.db_init import init_db

    with app.app_context():
        with db_connection() as conn:
            conn.execute("INSERT INTO Admin(admin_id, password, name, email, role) VALUES "
                         "('AID_legacy', 'x', 'Legacy', 'legacy@example.com', 'admin')")
        init_db(backup=False)  # idempotent re-run
        with db_connection() as conn:
            row = conn.execute("SELECT is_approved, is_owner FROM Admin WHERE admin_id = 'AID_legacy'").fetchone()
    assert (row["is_approved"], row["is_owner"]) == (1, 0)


def test_cli_approve_admin(app, client, api):
    _register(client, api, "owner@example.com")
    pending = _register(client, api, "rescue@example.com").get_json()["data"]["admin_id"]
    runner = app.test_cli_runner()
    result = runner.invoke(args=["approve-admin", "--email", "rescue@example.com", "--owner"])
    assert result.exit_code == 0, result.output
    with app.app_context():
        with db_connection() as conn:
            rows = {r["email"]: (r["is_approved"], r["is_owner"])
                    for r in conn.execute("SELECT email, is_approved, is_owner FROM Admin")}
    assert rows == {"owner@example.com": (1, 0), "rescue@example.com": (1, 1)}
    assert "admin.approve" in {r["action"] for r in _audit_actions(app, pending)}
    missing = runner.invoke(args=["approve-admin", "--email", "nobody@example.com"])
    assert missing.exit_code != 0 and "No admin account" in missing.output
