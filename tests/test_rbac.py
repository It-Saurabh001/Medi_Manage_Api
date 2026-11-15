"""RBAC on /api/v1/users (Part 3: replaces /admin/getAllUsers, /admin/updateUser, /admin/user/getSpecificUser)."""


def test_role_required_unauthorized(client, api):
    response = client.get(f"{api}/users")
    assert response.status_code == 401
    assert response.get_json()["code"] == "UNAUTHORIZED"


def test_role_required_forbidden_for_user(client, api, make_headers):
    response = client.get(f"{api}/users", headers=make_headers("user_123", "user"))
    assert response.status_code == 403
    assert response.get_json()["code"] == "FORBIDDEN"


def test_role_required_allowed_for_admin(client, api, make_headers):
    assert client.get(f"{api}/users", headers=make_headers("admin_123", "admin")).status_code == 200


def test_prevent_privilege_escalation_on_user_update(client, api, make_headers, admin_headers):
    created = client.post(f"{api}/users", json={
        "name": "Bob Normal", "email": "bob@example.com", "password": "Password123!", "phone_number": "8888888888"})
    user_id = created.get_json()["data"]["user_id"]
    user_headers = make_headers(user_id, "user")

    escalate = client.patch(f"{api}/users/me", json={
        "name": "Bob Hacked", "role": "admin", "is_approved": True, "is_blocked": False}, headers=user_headers)
    assert escalate.status_code == 400
    assert {"role", "is_approved", "is_blocked"} <= set(escalate.get_json()["fields"])

    assert client.patch(f"{api}/users/me", json={"name": "Bob Renamed"}, headers=user_headers).status_code == 200
    check = client.get(f"{api}/users/{user_id}", headers=admin_headers).get_json()["data"]
    assert check["name"] == "Bob Renamed"
    assert check["role"] == "user"
    assert check["is_approved"] is False
