"""Login + OTP flows on /api/v1/auth (Part 3: replaces /user/login, /user/verifyUserOtp, /admin/login, /admin/verifyOtp)."""
import re


def _otp(sender):
    return re.search(r"\b(\d{6})\b", sender.sent_messages[-1]["body"]).group(1)


def test_user_signup_login_and_otp_flow(client, api, fake_email_sender, admin_headers):
    signup = client.post(f"{api}/users", json={
        "name": "Alice Tester", "email": "alice@example.com", "password": "Password123!",
        "phone_number": "9876543210", "pin_code": "400001", "address": "123 Test St"})
    assert signup.status_code == 201
    user_id = signup.get_json()["data"]["user_id"]
    assert client.post(f"{api}/users/{user_id}/approve", headers=admin_headers).status_code == 200

    fake_email_sender.clear()
    login = client.post(f"{api}/auth/login", json={"email": "alice@example.com", "password": "Password123!"})
    assert login.status_code == 200
    assert login.get_json()["data"]["account_id"] == user_id
    assert len(fake_email_sender.sent_messages) == 1
    assert fake_email_sender.sent_messages[0]["to"] == "alice@example.com"
    otp = _otp(fake_email_sender)

    wrong = "000000" if otp != "000000" else "111111"
    bad = client.post(f"{api}/auth/verify-otp", json={"account_id": user_id, "otp": wrong})
    assert bad.status_code == 400
    assert bad.get_json()["code"] == "VALIDATION_ERROR"

    good = client.post(f"{api}/auth/verify-otp", json={"account_id": user_id, "otp": otp})
    assert good.status_code == 200
    tokens = good.get_json()["data"]
    assert tokens["access_token"] and tokens["refresh_token"]
    assert tokens["role"] == "user"


def test_admin_login_and_otp_flow(client, api, fake_email_sender, admin_headers):
    created = client.post(f"{api}/admins", json={
        "email": "admin@example.com", "name": "Admin One", "password": "AdminPassword123!",
        "phone_number": "9123456780"}, headers=admin_headers)
    assert created.status_code == 201

    fake_email_sender.clear()
    login = client.post(f"{api}/auth/login", json={
        "email": "admin@example.com", "password": "AdminPassword123!", "account_type": "admin"})
    assert login.status_code == 200
    admin_id = login.get_json()["data"]["account_id"]
    assert len(fake_email_sender.sent_messages) == 1

    verify = client.post(f"{api}/auth/verify-otp", json={
        "account_id": admin_id, "otp": _otp(fake_email_sender), "account_type": "admin"})
    assert verify.status_code == 200
    assert verify.get_json()["data"]["role"] == "admin"
