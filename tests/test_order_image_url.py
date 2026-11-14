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


def test_admin_and_user_profile_image_url(app, client, make_headers):
    from app.services.read_ops import getAllAdmins, getAllUsers, getSpecificUser
    from app.services.add_ops import createAdmin, createUser

    # 1. Create admin and user with image_url
    createAdmin("admin_pic@test.com", "Admin Pic", "Password123!", "9998887771", "admin", "https://res.cloudinary.com/test/admin_avatar.jpg")
    createUser("User Pic", "Password123!", "9998887772", "user_pic@test.com", "123456", "123 Test St", "user", "https://res.cloudinary.com/test/user_avatar.jpg")

    # 2. Check getAllAdmins
    admins = getAllAdmins()
    admin_pic = [a for a in admins if a['email'] == 'admin_pic@test.com'][0]
    assert admin_pic['image_url'] == 'https://res.cloudinary.com/test/admin_avatar.jpg'

    # 3. Check getAllUsers
    users = getAllUsers()
    user_pic = [u for u in users if u['email'] == 'user_pic@test.com'][0]
    assert user_pic['image_url'] == 'https://res.cloudinary.com/test/user_avatar.jpg'

    # 4. Check getSpecificUser
    spec_user = getSpecificUser(user_pic['user_id'])
    assert spec_user['image_url'] == 'https://res.cloudinary.com/test/user_avatar.jpg'

    # 5. Check HTTP route update user profile image
    user_headers = make_headers(user_pic['user_id'], "user")
    update_res = client.patch("/admin/updateUser", data={
        "user_id": user_pic['user_id'],
        "image_url": "https://res.cloudinary.com/test/user_updated.jpg"
    }, headers=user_headers)
    assert update_res.status_code == 200

    updated_user = getSpecificUser(user_pic['user_id'])
    assert updated_user['image_url'] == 'https://res.cloudinary.com/test/user_updated.jpg'

def test_admin_and_user_file_upload(app, client, make_headers, monkeypatch):
    import io
    from app.services.read_ops import getAllAdmins, getAllUsers, getSpecificUser

    # Mock cloudinary.uploader.upload
    uploaded_files = []
    def mock_upload(file, **kwargs):
        folder = kwargs.get("folder", "default")
        url = f"https://res.cloudinary.com/demo/image/upload/{folder}/{file.filename}"
        uploaded_files.append((file.filename, folder))
        return {"secure_url": url}

    import cloudinary.uploader
    monkeypatch.setattr(cloudinary.uploader, "upload", mock_upload)

    # 1. Admin creates another admin with image file
    admin_headers = make_headers("A_ROOT", "admin")
    res_admin = client.post("/admin/create", data={
        "email": "uploaded_admin@test.com",
        "name": "Uploaded Admin",
        "password": "Password123!",
        "phoneNumber": "8887776661",
        "image": (io.BytesIO(b"fake image bytes"), "admin_profile.png")
    }, headers=admin_headers)
    assert res_admin.status_code == 201

    admins = getAllAdmins()
    new_admin = [a for a in admins if a['email'] == "uploaded_admin@test.com"][0]
    assert new_admin['image_url'] == "https://res.cloudinary.com/demo/image/upload/MediAdminApp/Admins/admin_profile.png"

    # 2. Update admin with image file
    res_admin_up = client.patch("/admin/update", data={
        "admin_id": new_admin['admin_id'],
        "image": (io.BytesIO(b"fake image bytes 2"), "admin_new.png")
    }, headers=admin_headers)
    assert res_admin_up.status_code == 200

    admins_updated = getAllAdmins()
    updated_admin = [a for a in admins_updated if a['admin_id'] == new_admin['admin_id']][0]
    assert updated_admin['image_url'] == "https://res.cloudinary.com/demo/image/upload/MediAdminApp/Admins/admin_new.png"

    # 3. Create user with image file
    res_user = client.post("/user/create", data={
        "name": "Uploaded User",
        "password": "Password123!",
        "email": "uploaded_user@test.com",
        "phoneNumber": "8887776662",
        "image": (io.BytesIO(b"fake user image bytes"), "user_profile.png")
    })
    assert res_user.status_code == 201

    users = getAllUsers()
    new_user = [u for u in users if u['email'] == "uploaded_user@test.com"][0]
    assert new_user['image_url'] == "https://res.cloudinary.com/demo/image/upload/MediAdminApp/Users/user_profile.png"

    # 4. Update user with image file
    user_headers = make_headers(new_user['user_id'], "user")
    res_user_up = client.patch("/admin/updateUser", data={
        "user_id": new_user['user_id'],
        "image": (io.BytesIO(b"fake user image bytes 2"), "user_new.png")
    }, headers=user_headers)
    assert res_user_up.status_code == 200

    spec_user = getSpecificUser(new_user['user_id'])
    assert spec_user['image_url'] == "https://res.cloudinary.com/demo/image/upload/MediAdminApp/Users/user_new.png"

