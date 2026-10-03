def test_role_required_unauthorized(client):
    # Missing authorization token
    response = client.get("/admin/getAllUsers")
    assert response.status_code == 401

def test_role_required_forbidden_for_user(client, make_headers):
    # User token attempting to access admin-only endpoint
    headers = make_headers("user_123", "user")
    response = client.get("/admin/getAllUsers", headers=headers)
    assert response.status_code == 403
    assert response.get_json()["message"] == "Access Forbidden"

def test_role_required_allowed_for_admin(client, make_headers):
    # Admin token accessing admin-only endpoint
    headers = make_headers("admin_123", "admin")
    response = client.get("/admin/getAllUsers", headers=headers)
    assert response.status_code == 200

def test_prevent_privilege_escalation_on_user_update(client, make_headers):
    # 1. Create user
    client.post("/user/create", data={
        "name": "Bob Normal",
        "email": "bob@example.com",
        "password": "Password123!",
        "phoneNumber": "8888888888"
    })

    # Fetch user_id via admin
    admin_headers = make_headers("admin_boss", "admin")
    users = client.get("/admin/getAllUsers", headers=admin_headers).get_json()["users"]
    target_user = [u for u in users if u["email"] == "bob@example.com"][0]
    user_id = target_user["user_id"]

    # Normal user attempts to make themselves admin and approved
    user_headers = make_headers(user_id, "user")
    update_res = client.patch("/admin/updateUser", data={
        "user_id": user_id,
        "name": "Bob Hacked",
        "role": "admin",
        "isApproved": "true",
        "block": "false"
    }, headers=user_headers)
    assert update_res.status_code == 200

    # Verify user record: name updated, but role and isApproved remained untouched
    user_check = client.post("/admin/user/getSpecificUser", data={"user_id": user_id}, headers=admin_headers).get_json()["user"]
    assert user_check["name"] == "Bob Hacked"
    assert user_check["role"] == "user"
    assert user_check["isApproved"] is not True
