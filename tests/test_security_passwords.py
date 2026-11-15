"""Passwords are hashed and never serialised (Part 3: /api/v1/users replaces /user/create, /admin/updateUser)."""
import os
import sqlite3


def _stored_password(user_id):
    conn = sqlite3.connect(os.getenv("DATABASE_NAME", "test_medical_shop.db"))
    try:
        return conn.execute("SELECT password FROM Users WHERE user_id = ?", (user_id,)).fetchone()[0]
    finally:
        conn.close()


def test_password_hashing_and_exclusion(client, api, make_headers, admin_headers):
    created = client.post(f"{api}/users", json={
        "name": "SecUser", "email": "sec@example.com", "password": "MyPlainPassword123", "phone_number": "7777777777"})
    assert created.status_code == 201
    assert "password" not in created.get_json()["data"]

    users = client.get(f"{api}/users", headers=admin_headers).get_json()["data"]
    user = [u for u in users if u["email"] == "sec@example.com"][0]
    assert "password" not in user
    user_id = user["user_id"]

    stored = _stored_password(user_id)
    assert stored.startswith(("scrypt:", "pbkdf2:")), "Raw password stored on create"

    res = client.patch(f"{api}/users/me", json={"password": "NewPlainPassword456", "current_password": "MyPlainPassword123"},
                       headers=make_headers(user_id, "user"))
    assert res.status_code == 200
    assert "password" not in res.get_json()["data"]
    updated = _stored_password(user_id)
    assert updated.startswith(("scrypt:", "pbkdf2:")), "Raw password stored on update"
    assert updated != stored and updated != "NewPlainPassword456"
