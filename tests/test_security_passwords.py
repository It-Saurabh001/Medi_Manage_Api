import os
import sqlite3

def test_password_hashing_and_exclusion(client, make_headers):
    # 1. Create a user
    client.post("/user/create", data={
        "name": "SecUser",
        "email": "sec@example.com",
        "password": "MyPlainPassword123",
        "phoneNumber": "7777777777"
    })

    admin_headers = make_headers("sec_admin", "admin")
    users = client.get("/admin/getAllUsers", headers=admin_headers).get_json()["users"]
    user = [u for u in users if u["email"] == "sec@example.com"][0]
    user_id = user["user_id"]

    # Verify password is not in read response
    assert "password" not in user

    # Query database directly to confirm hash algorithm is used
    db_file = os.getenv("DATABASE_NAME", "test_medical_shop.db")
    conn = sqlite3.connect(db_file)
    stored_pwd = conn.execute("SELECT password FROM Users WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()
    assert stored_pwd.startswith("scrypt:") or stored_pwd.startswith("pbkdf2:"), "Raw password stored on create"

    # 2. Update password
    client.patch("/admin/updateUser", data={
        "user_id": user_id,
        "password": "NewPlainPassword456"
    }, headers=admin_headers)

    conn = sqlite3.connect(db_file)
    updated_pwd = conn.execute("SELECT password FROM Users WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()
    assert updated_pwd.startswith("scrypt:") or updated_pwd.startswith("pbkdf2:"), "Raw password stored on update"
    assert updated_pwd != "NewPlainPassword456", "Plaintext password persisted"
