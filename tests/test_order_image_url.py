import sqlite3

from app.db import db_connection


def test_order_and_sale_image_url(app, client, api, make_headers, admin_headers):
    """Orders and sales expose the product image (new /api/v1 order + sales endpoints)."""
    with app.app_context():
        with db_connection() as conn:
            conn.execute("INSERT INTO Users (user_id, name, email, role, isApproved, block) "
                         "VALUES ('U1', 'Test User', 'u1@test.com', 'user', 1, 0)")
    user_headers = make_headers("U1", "user")

    pids = []
    for name in ("Image Med", "No Image Med"):
        res = client.post(f"{api}/products", json={"name": name, "price": 20}, headers=admin_headers)
        pids.append(res.get_json()["data"]["product_id"])
        client.post(f"{api}/products/{pids[-1]}/stock/purchase", headers=admin_headers,
                    json={"batch_no": "B1", "expiry_date": "2999-12-31", "quantity": 50})
    image = "https://res.cloudinary.com/test/image.jpg"
    with app.app_context():
        with db_connection() as conn:
            conn.execute("UPDATE Products SET image_url = ? WHERE Product_id = ?", (image, pids[0]))

    ord1 = client.post(f"{api}/orders", json={"product_id": pids[0], "quantity": 2, "message": "Take twice daily"},
                       headers=user_headers).get_json()["data"]
    ord2 = client.post(f"{api}/orders", json={"product_id": pids[1], "quantity": 1},
                       headers=user_headers).get_json()["data"]
    assert ord1["image_url"] == image and ord2["image_url"] is None

    all_orders = client.get(f"{api}/orders", headers=admin_headers).get_json()["data"]
    assert any(o["order_id"] == ord1["order_id"] and o["image_url"] == image for o in all_orders)
    user_orders = client.get(f"{api}/users/U1/orders", headers=user_headers).get_json()["data"]
    assert any(o["order_id"] == ord1["order_id"] and o["image_url"] == image for o in user_orders)
    single = client.get(f"{api}/orders/{ord1['order_id']}", headers=user_headers).get_json()["data"]
    assert single["image_url"] == image

    client.post(f"{api}/orders/{ord1['order_id']}/approve", headers=admin_headers)
    sold = client.post(f"{api}/orders/{ord1['order_id']}/sell", headers=admin_headers)
    assert sold.status_code == 200
    sale_id = sold.get_json()["data"]["sales"][0]["sale_id"]
    for query in ("", "?user_id=U1", f"?product_id={pids[0]}"):
        sales = client.get(f"{api}/sales{query}", headers=admin_headers).get_json()["data"]
        assert any(s["sale_id"] == sale_id and s["image_url"] == image for s in sales)


PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def test_admin_and_user_profile_image_url(app, client, api, make_headers, admin_headers):
    """Part 3: image_url is exposed by /api/v1/admins and /api/v1/users (replaces legacy read_ops checks)."""
    from app.db import db_connection
    from app.services import account_service as acc

    with app.app_context():
        with db_connection() as conn:
            admin_id = acc.insert_admin(conn, {"name": "Admin Pic", "email": "admin_pic@test.com", "password": "Password123!",
                                               "phone_number": "9998887771",
                                               "image_url": "https://res.cloudinary.com/test/admin_avatar.jpg"})
            user_id = acc.insert_user(conn, {"name": "User Pic", "email": "user_pic@test.com", "password": "Password123!",
                                             "phone_number": "9998887772", "pin_code": "123456", "address": "123 Test St",
                                             "image_url": "https://res.cloudinary.com/test/user_avatar.jpg"})

    admins = client.get(f"{api}/admins", headers=admin_headers).get_json()["data"]
    assert [a for a in admins if a["admin_id"] == admin_id][0]["image_url"] == "https://res.cloudinary.com/test/admin_avatar.jpg"
    users = client.get(f"{api}/users", headers=admin_headers).get_json()["data"]
    assert [u for u in users if u["user_id"] == user_id][0]["image_url"] == "https://res.cloudinary.com/test/user_avatar.jpg"
    own = client.get(f"{api}/users/me", headers=make_headers(user_id, "user")).get_json()["data"]
    assert own["image_url"] == "https://res.cloudinary.com/test/user_avatar.jpg"

    # image_url cannot be set directly through the API (only via an uploaded file).
    res = client.patch(f"{api}/users/me", json={"image_url": "https://evil.example/x.jpg"}, headers=make_headers(user_id, "user"))
    assert res.status_code == 400


def test_admin_and_user_file_upload(app, client, api, make_headers, admin_headers, monkeypatch):
    import io

    import cloudinary.uploader

    def mock_upload(file, **kwargs):
        return {"secure_url": f"https://res.cloudinary.com/demo/image/upload/{kwargs.get('folder', 'default')}/{file.filename}"}

    monkeypatch.setattr(cloudinary.uploader, "upload", mock_upload)
    base = "https://res.cloudinary.com/demo/image/upload"

    res_admin = client.post(f"{api}/admins", data={
        "email": "uploaded_admin@test.com", "name": "Uploaded Admin", "password": "Password123!",
        "phone_number": "8887776661", "image": (io.BytesIO(PNG_BYTES), "admin_profile.png")},
        headers=admin_headers, content_type="multipart/form-data")
    assert res_admin.status_code == 201
    new_admin = res_admin.get_json()["data"]
    assert new_admin["image_url"] == f"{base}/MediAdminApp/Admins/admin_profile.png"

    res_admin_up = client.patch(f"{api}/admins/{new_admin['admin_id']}", data={
        "image": (io.BytesIO(PNG_BYTES), "admin_new.png")}, headers=admin_headers, content_type="multipart/form-data")
    assert res_admin_up.status_code == 200
    assert res_admin_up.get_json()["data"]["image_url"] == f"{base}/MediAdminApp/Admins/admin_new.png"

    res_user = client.post(f"{api}/users", data={
        "name": "Uploaded User", "password": "Password123!", "email": "uploaded_user@test.com",
        "phone_number": "8887776662", "image": (io.BytesIO(PNG_BYTES), "user_profile.png")},
        content_type="multipart/form-data")
    assert res_user.status_code == 201
    new_user = res_user.get_json()["data"]
    assert new_user["image_url"] == f"{base}/MediAdminApp/Users/user_profile.png"

    res_user_up = client.patch(f"{api}/users/me", data={"image": (io.BytesIO(PNG_BYTES), "user_new.png")},
                               headers=make_headers(new_user["user_id"], "user"), content_type="multipart/form-data")
    assert res_user_up.status_code == 200
    assert res_user_up.get_json()["data"]["image_url"] == f"{base}/MediAdminApp/Users/user_new.png"
