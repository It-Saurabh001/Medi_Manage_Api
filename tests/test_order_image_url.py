import sqlite3
from app.services.add_ops import createOrder, record_Sell
from app.services.read_ops import getAllOrders, getUserOrders, getOrderById, getSellHistory, getUserSellHistory, getProductSellHistory

def test_order_and_sell_history_image_url(app, client, make_headers):
    # Setup test product with image and product without image
    conn = sqlite3.connect("test_medical_shop.db")
    c = conn.cursor()
    c.execute("INSERT INTO Users (user_id, name, email, role) VALUES ('U1', 'Test User', 'u1@test.com', 'user')")
    c.execute("INSERT INTO Products (Product_id, name, price, category, stock, image_url) VALUES ('PROD_IMG', 'Image Med', 20.0, 'Pills', 50, 'https://res.cloudinary.com/test/image.jpg')")
    c.execute("INSERT INTO Products (Product_id, name, price, category, stock, image_url) VALUES ('PROD_NO_IMG', 'No Image Med', 10.0, 'Liquid', 50, NULL)")
    conn.commit()
    conn.close()

    # 1. Create order with image
    res1 = createOrder('U1', 'PROD_IMG', 2, 'Take twice daily')
    ord1_id = res1['message']

    # 2. Create order without image
    res2 = createOrder('U1', 'PROD_NO_IMG', 1, '')
    ord2_id = res2['message']

    # Verify getAllOrders
    orders = getAllOrders()
    ord1 = [o for o in orders if o['order_id'] == ord1_id][0]
    ord2 = [o for o in orders if o['order_id'] == ord2_id][0]
    assert ord1['image_url'] == 'https://res.cloudinary.com/test/image.jpg'
    assert ord2['image_url'] is None

    # Verify getUserOrders
    user_orders = getUserOrders('U1')
    assert any(o['order_id'] == ord1_id and o['image_url'] == 'https://res.cloudinary.com/test/image.jpg' for o in user_orders)
    assert any(o['order_id'] == ord2_id and o['image_url'] is None for o in user_orders)

    # Verify getOrderById
    single_order = getOrderById(ord1_id)
    assert single_order is not None
    assert single_order['image_url'] == 'https://res.cloudinary.com/test/image.jpg'

    # Approve order 1 and record sell
    conn = sqlite3.connect("test_medical_shop.db")
    c = conn.cursor()
    c.execute("UPDATE Order_Details SET isApproved = 1 WHERE Order_id = ?", (ord1_id,))
    conn.commit()
    conn.close()

    res_sell = record_Sell(ord1_id)
    sell_id = res_sell['message']

    # Verify getSellHistory
    sells = getSellHistory()
    sell1 = [s for s in sells if s['Sell_id'] == sell_id][0]
    assert sell1['image_url'] == 'https://res.cloudinary.com/test/image.jpg'

    # Verify getUserSellHistory
    user_sells = getUserSellHistory('U1')
    assert any(s['Sell_id'] == sell_id and s['image_url'] == 'https://res.cloudinary.com/test/image.jpg' for s in user_sells)

    # Verify getProductSellHistory
    prod_sells = getProductSellHistory('PROD_IMG')
    assert any(s['Sell_id'] == sell_id and s['image_url'] == 'https://res.cloudinary.com/test/image.jpg' for s in prod_sells)

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

