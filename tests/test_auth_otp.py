import re
from app.services.otp_service import user_otp_store, otp_store

def test_user_signup_login_and_otp_flow(client, fake_email_sender):
    # 1. Signup
    signup_res = client.post("/user/create", data={
        "name": "Alice Tester",
        "email": "alice@example.com",
        "password": "Password123!",
        "phoneNumber": "9876543210",
        "pincode": "400001",
        "address": "123 Test St"
    })
    assert signup_res.status_code == 201

    # 2. Login
    fake_email_sender.clear()
    login_res = client.post("/user/login", data={
        "email": "alice@example.com",
        "password": "Password123!"
    })
    assert login_res.status_code == 200
    login_data = login_res.get_json()
    user_id = login_data["user_id"]
    assert user_id is not None

    # Check fake email sender received OTP
    assert len(fake_email_sender.sent_messages) == 1
    sent_msg = fake_email_sender.sent_messages[0]
    assert sent_msg["to"] == "alice@example.com"
    otp_match = re.search(r"\b(\d{6})\b", sent_msg["body"])
    assert otp_match is not None
    otp = otp_match.group(1)

    # 3. Verify OTP with wrong code
    bad_verify = client.post("/user/verifyUserOtp", data={
        "user_id": user_id,
        "otp": "000000"
    })
    assert bad_verify.status_code == 400

    # 4. Verify OTP with correct code
    good_verify = client.post("/user/verifyUserOtp", data={
        "user_id": user_id,
        "otp": otp
    })
    assert good_verify.status_code == 200
    tokens = good_verify.get_json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["role"] == "user"

def test_admin_login_and_otp_flow(client, fake_email_sender, make_headers):
    # Create admin using admin headers
    admin_headers = make_headers("master_admin", "admin")
    client.post("/admin/create", data={
        "email": "admin@example.com",
        "name": "Admin One",
        "password": "AdminPassword123!",
        "phoneNumber": "9123456780"
    }, headers=admin_headers)

    # Admin login
    fake_email_sender.clear()
    login_res = client.post("/admin/login", data={
        "email": "admin@example.com",
        "password": "AdminPassword123!"
    })
    assert login_res.status_code == 200
    admin_id = login_res.get_json()["admin_id"]

    assert len(fake_email_sender.sent_messages) == 1
    otp_match = re.search(r"\b(\d{6})\b", fake_email_sender.sent_messages[0]["body"])
    otp = otp_match.group(1)

    # Verify admin OTP
    verify_res = client.post("/admin/verifyOtp", data={
        "admin_id": admin_id,
        "otp": otp
    })
    assert verify_res.status_code == 200
    assert verify_res.get_json()["role"] == "admin"
