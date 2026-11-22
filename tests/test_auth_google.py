"""POST /api/v1/auth/google (Google Sign-In). verify_google_id_token is mocked; no network."""
import re

import pytest

from app.errors import ApiError
from app.services import auth_service

SUB = "google-sub-123"


def _claims(email="gina@example.com", sub=SUB, name="Gina Google"):
    return {"sub": sub, "email": email, "name": name}


@pytest.fixture
def google(monkeypatch):
    """Set `google.claims` (dict) or `google.error` (ApiError) to control the mocked verifier."""
    state = type("GoogleMock", (), {"claims": _claims(), "error": None})()

    def fake_verify(raw_token):
        assert raw_token == "tok"
        if state.error:
            raise state.error
        return dict(state.claims)

    monkeypatch.setattr(auth_service, "verify_google_id_token", fake_verify)
    return state


def _google_login(client, api, account_type="user"):
    return client.post(f"{api}/auth/google", json={"id_token": "tok", "account_type": account_type})


def _otp(sender):
    return re.search(r"\b(\d{6})\b", sender.sent_messages[-1]["body"]).group(1)


def _signup_user(client, api, admin_headers, email="gina@example.com", approve=True):
    res = client.post(f"{api}/users", json={"name": "Gina", "email": email, "password": "Password123!"})
    assert res.status_code == 201
    user_id = res.get_json()["data"]["user_id"]
    if approve:
        assert client.post(f"{api}/users/{user_id}/approve", headers=admin_headers).status_code == 200
    return user_id


def _user_row(app, user_id):
    from app.db import get_db
    with app.app_context():
        conn = get_db()
        try:
            return conn.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,)).fetchone()
        finally:
            conn.close()


def test_new_user_is_created_unapproved_without_password(app, client, api, google):
    res = _google_login(client, api)
    assert res.status_code == 403
    assert res.get_json()["code"] == "ACCOUNT_NOT_APPROVED"
    with app.app_context():
        from app.db import get_db
        conn = get_db()
        try:
            row = conn.execute("SELECT * FROM Users WHERE email = ?", ("gina@example.com",)).fetchone()
        finally:
            conn.close()
    assert row is not None and row["google_sub"] == SUB and not row["password"]
    assert row["auth_provider"] == "google" and int(row["is_email_verified"]) == 1


def test_existing_user_linked_by_email_then_login_by_sub(app, client, api, google, admin_headers):
    user_id = _signup_user(client, api, admin_headers, email="Gina@Example.com")
    res = _google_login(client, api)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["account_id"] == user_id and data["access_token"] and data["role"] == "user"
    assert _user_row(app, user_id)["google_sub"] == SUB

    google.claims = _claims(email="other-address@example.com")  # sub lookup wins over email
    again = _google_login(client, api)
    assert again.status_code == 200 and again.get_json()["data"]["account_id"] == user_id


def test_google_account_mismatch(client, api, google, admin_headers):
    _signup_user(client, api, admin_headers)
    assert _google_login(client, api).status_code == 200
    google.claims = _claims(sub="a-different-sub")
    res = _google_login(client, api)
    assert res.status_code == 409
    assert res.get_json()["code"] == "GOOGLE_ACCOUNT_MISMATCH"


@pytest.mark.parametrize("message", ["Invalid Google sign-in token", "Google account email is not verified"])
def test_rejected_tokens(client, api, google, message):
    # verify_google_id_token raises these for a bad signature/audience and for email_verified=false
    google.error = ApiError(message, 401, "UNAUTHORIZED")
    res = _google_login(client, api)
    assert res.status_code == 401 and res.get_json()["code"] == "UNAUTHORIZED"


def test_verifier_rejects_unverified_email_and_bad_token(app, monkeypatch):
    from google.oauth2 import id_token as google_id_token

    app.config["GOOGLE_CLIENT_ID"] = "web-client-id"
    base = {"iss": "accounts.google.com", "sub": SUB, "email": "gina@example.com"}
    with app.test_request_context():
        monkeypatch.setattr(google_id_token, "verify_oauth2_token", lambda *a: {**base, "email_verified": False})
        with pytest.raises(ApiError) as exc:
            auth_service.verify_google_id_token("tok")
        assert exc.value.status == 401

        def boom(*a):
            raise ValueError("Token used too late, secret details")
        monkeypatch.setattr(google_id_token, "verify_oauth2_token", boom)
        with pytest.raises(ApiError) as exc:
            auth_service.verify_google_id_token("tok")
        assert exc.value.status == 401 and "secret" not in str(exc.value.message)

        monkeypatch.setattr(google_id_token, "verify_oauth2_token", lambda *a: {**base, "email_verified": True})
        assert auth_service.verify_google_id_token("tok")["sub"] == SUB


def test_missing_id_token_is_validation_error(client, api, google):
    res = client.post(f"{api}/auth/google", json={"account_type": "user"})
    assert res.status_code == 400 and res.get_json()["code"] == "VALIDATION_ERROR"


def test_admin_not_registered(client, api, google):
    res = _google_login(client, api, "admin")
    assert res.status_code == 403
    assert res.get_json()["code"] == "ADMIN_ACCOUNT_NOT_REGISTERED"


def test_existing_admin_goes_through_otp(client, api, google, admin_headers, fake_email_sender):
    created = client.post(f"{api}/admins", json={
        "email": "gina@example.com", "name": "Gina Admin", "password": "AdminPassword123!"}, headers=admin_headers)
    assert created.status_code == 201
    fake_email_sender.clear()
    res = _google_login(client, api, "admin")
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["otp_required"] is True and "access_token" not in data
    verify = client.post(f"{api}/auth/verify-otp", json={
        "account_id": data["account_id"], "otp": _otp(fake_email_sender), "account_type": "admin"})
    assert verify.status_code == 200 and verify.get_json()["data"]["role"] == "admin"


def test_blocked_user_rejected(client, api, google, admin_headers):
    user_id = _signup_user(client, api, admin_headers)
    assert client.post(f"{api}/users/{user_id}/block", headers=admin_headers).status_code == 200
    res = _google_login(client, api)
    assert res.status_code == 403 and res.get_json()["code"] == "ACCOUNT_BLOCKED"


def test_password_login_fails_for_google_only_account(client, api, google, admin_headers):
    _google_login(client, api)  # creates the unapproved Google-only user
    res = client.post(f"{api}/auth/login", json={"email": "gina@example.com", "password": "anything123"})
    assert res.status_code == 401


def test_email_change_blocked_for_linked_account(client, api, google, admin_headers):
    user_id = _signup_user(client, api, admin_headers)
    tokens = _google_login(client, api).get_json()["data"]
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    res = client.patch(f"{api}/users/me", json={"email": "new@example.com", "current_password": "Password123!"},
                       headers=headers)
    assert res.status_code == 400 and "email" in res.get_json()["fields"]
    by_admin = client.patch(f"{api}/users/{user_id}", json={"email": "new@example.com"}, headers=admin_headers)
    assert by_admin.status_code == 400 and "email" in by_admin.get_json()["fields"]
    me = client.get(f"{api}/users/me", headers=headers).get_json()["data"]
    assert me["google_linked"] is True and me["has_password"] is True


def test_rate_limited(app, client, api, google):
    app.config["GOOGLE_LOGIN_RATE_LIMIT"] = 2
    codes = [_google_login(client, api).status_code for _ in range(3)]
    assert codes[-1] == 429


def test_refresh_and_logout_after_google_login(client, api, google, admin_headers):
    _signup_user(client, api, admin_headers)
    tokens = _google_login(client, api).get_json()["data"]
    refreshed = client.post(f"{api}/auth/refresh", headers={"Authorization": f"Bearer {tokens['refresh_token']}"})
    assert refreshed.status_code == 200
    new = refreshed.get_json()["data"]
    out = client.post(f"{api}/auth/logout", json={"refresh_token": new["refresh_token"]},
                      headers={"Authorization": f"Bearer {new['access_token']}"})
    assert out.status_code == 200
