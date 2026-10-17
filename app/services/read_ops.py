import os
import sqlite3

def get_db():
    db_name = os.getenv("DATABASE_NAME", "My_Medical_Shope.db")
    return sqlite3.connect(db_name)

def getAllUsers():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, user_id, date_of_account_creation, isApproved, block, name, address, email, phone_number, pin_code, role, image_url FROM Users')
        users = cursor.fetchall()

        userJson = []
        for user in users:
            tempUser = {
                "id": user[0],
                "user_id": user[1],
                "date_of_account_creation": user[2],
                "isApproved": bool(user[3]) if isinstance(user[3], int) else user[3] == "true",
                "block": bool(user[4]) if isinstance(user[4], int) else user[4] == "true",
                "name": user[5],
                "address": user[6],
                "email": user[7],
                "phone_number": user[8],
                "pin_code": user[9],
                "role": user[10] if len(user) > 10 else "user",
                "image_url": user[11] if len(user) > 11 else None
            }
            userJson.append(tempUser)
        return userJson
    finally:
        conn.close()

def getAllAdmins():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, admin_id, date_of_account_creation, name, email, phone_number, role, image_url FROM Admin')
        admins = cursor.fetchall()

        adminJson = []
        for admin in admins:
            tempAdmin = {
                "id": admin[0],
                "admin_id": admin[1],
                "date_of_account_creation": admin[2],
                "name": admin[3],
                "email": admin[4],
                "phone_number": admin[5],
                "role": admin[6] if len(admin) > 6 else "admin",
                "image_url": admin[7] if len(admin) > 7 else None
            }
            adminJson.append(tempAdmin)
        return adminJson
    finally:
        conn.close()

def getSpecificUser(userId):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, user_id, date_of_account_creation, isApproved, block, name, address, email, phone_number, pin_code, role, image_url FROM Users WHERE user_id = ?', (userId,))
        user = cursor.fetchone()
        if user is None:
            return None

        tempUser = {
            "id": user[0],
            "user_id": user[1],
            "date_of_account_creation": user[2],
            "isApproved": user[3],
            "block": user[4],
            "name": user[5],
            "address": user[6],
            "email": user[7],
            "phone_number": user[8],
            "pin_code": user[9],
            "role": user[10] if len(user) > 10 else "user",
            "image_url": user[11] if len(user) > 11 else None
        }
        return tempUser
    finally:
        conn.close()

def getAllProducts():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, Product_id, name, price, category, stock, image_url FROM Products')
        products = cursor.fetchall()

        productJson = []
        for product in products:
            tempProduct = {
                "id": product[0],
                "Product_id": product[1],
                "name": product[2],
                "price": product[3],
                "category": product[4],
                "stock": product[5],
                "image_url": product[6] if len(product) > 6 else None
            }
            productJson.append(tempProduct)
        return productJson
    finally:
        conn.close()

def getspecificproduct(Product_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, Product_id, name, price, category, stock, image_url FROM Products WHERE Product_id = ?', (Product_id,))
        product = cursor.fetchone()
        if product is None:
            return None

        tempProduct = {
            "id": product[0],
            "Product_id": product[1],
            "name": product[2],
            "price": product[3],
            "category": product[4],
            "stock": product[5],
            "image_url": product[6] if len(product) > 6 else None
        }
        return tempProduct
    finally:
        conn.close()

def getAllOrders():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                Order_Details.id, 
                Order_Details.Order_id, 
                Order_Details.user_id, 
                Order_Details.product_id, 
                Order_Details.isApproved, 
                Order_Details.quantity, 
                Order_Details.date_of_order_creation, 
                Order_Details.price, 
                Order_Details.total_amount, 
                Order_Details.product_name, 
                Order_Details.user_name, 
                Order_Details.message, 
                Order_Details.category, 
                Order_Details.sold,
                COALESCE(Order_Details.image_url, Products.image_url) AS image_url
            FROM Order_Details
            LEFT JOIN Products ON Order_Details.product_id = Products.Product_id
        ''')
        orders = cursor.fetchall()

        orderJson = []
        for order in orders:
            tempOrder = {
                "id": order[0],
                "order_id": order[1],
                "user_id": order[2],
                "product_id": order[3],
                "isApproved": bool(order[4]),
                "quantity": order[5],
                "date_of_order_creation": order[6],
                "price": order[7],
                "total_amount": order[8],
                "product_name": order[9],
                "user_name": order[10],
                "message": order[11],
                "category": order[12],
                "sold": bool(order[13]) if len(order) > 13 else False,
                "image_url": order[14] if len(order) > 14 else None
            }
            orderJson.append(tempOrder)
        return orderJson
    finally:
        conn.close()

def getUserOrders(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                Order_Details.id, 
                Order_Details.Order_id, 
                Order_Details.user_id, 
                Order_Details.product_id, 
                Order_Details.isApproved, 
                Order_Details.quantity, 
                Order_Details.date_of_order_creation, 
                Order_Details.price, 
                Order_Details.total_amount, 
                Order_Details.product_name, 
                Order_Details.user_name, 
                Order_Details.message, 
                Order_Details.category, 
                Order_Details.sold,
                COALESCE(Order_Details.image_url, Products.image_url) AS image_url
            FROM Order_Details
            LEFT JOIN Products ON Order_Details.product_id = Products.Product_id
            WHERE Order_Details.user_id = ?
        ''', (user_id,))
        orders = cursor.fetchall()

        orderJson = []
        for order in orders:
            tempOrder = {
                "id": order[0],
                "order_id": order[1],
                "user_id": order[2],
                "product_id": order[3],
                "isApproved": bool(order[4]),
                "quantity": order[5],
                "date_of_order_creation": order[6],
                "price": order[7],
                "total_amount": order[8],
                "product_name": order[9],
                "user_name": order[10],
                "message": order[11],
                "category": order[12],
                "sold": bool(order[13]) if len(order) > 13 else False,
                "image_url": order[14] if len(order) > 14 else None
            }
            orderJson.append(tempOrder)
        return orderJson
    finally:
        conn.close()

def getOrderById(Order_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                Order_Details.id, 
                Order_Details.Order_id, 
                Order_Details.user_id, 
                Order_Details.product_id, 
                Order_Details.isApproved, 
                Order_Details.quantity, 
                Order_Details.date_of_order_creation, 
                Order_Details.price, 
                Order_Details.total_amount, 
                Order_Details.product_name, 
                Order_Details.user_name, 
                Order_Details.message, 
                Order_Details.category, 
                Order_Details.sold,
                COALESCE(Order_Details.image_url, Products.image_url) AS image_url
            FROM Order_Details
            LEFT JOIN Products ON Order_Details.product_id = Products.Product_id
            WHERE Order_Details.Order_id = ?
        ''', (Order_id,))
        order = cursor.fetchone()
        if order is None:
            return None

        tempOrder = {
            "id": order[0],
            "order_id": order[1],
            "user_id": order[2],
            "product_id": order[3],
            "isApproved": bool(order[4]),
            "quantity": order[5],
            "date_of_order_creation": order[6],
            "price": order[7],
            "total_amount": order[8],
            "product_name": order[9],
            "user_name": order[10],
            "message": order[11],
            "category": order[12],
            "sold": bool(order[13]) if len(order) > 13 else False,
            "image_url": order[14] if len(order) > 14 else None
        }
        return tempOrder
    finally:
        conn.close()

def getSellHistory():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                Sell_History.id, 
                Sell_History.Sell_id, 
                Sell_History.product_id, 
                Sell_History.Order_id, 
                Sell_History.isApproved, 
                Sell_History.quantity, 
                Sell_History.Remaining_stock, 
                Sell_History.date_of_sell, 
                Sell_History.total_amount, 
                Sell_History.price, 
                Sell_History.product_name, 
                Sell_History.user_id, 
                Sell_History.user_name,
                COALESCE(Sell_History.image_url, Products.image_url) AS image_url
            FROM Sell_History
            LEFT JOIN Products ON Sell_History.product_id = Products.Product_id
        ''')
        sell_history = cursor.fetchall()

        sellJson = []
        for sell in sell_history:
            tempSell = {
                "id": sell[0],
                "Sell_id": sell[1],
                "product_id": sell[2],
                "Order_id": sell[3],
                "isApproved": bool(sell[4]),
                "quantity": sell[5],
                "remaining_stock": sell[6],
                "date_of_sell": sell[7],
                "total_amount": sell[8],
                "price": sell[9],
                "product_name": sell[10],
                "user_id": sell[11],
                "user_name": sell[12],
                "image_url": sell[13] if len(sell) > 13 else None
            }
            sellJson.append(tempSell)
        return sellJson
    finally:
        conn.close()

def getUserSellHistory(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                Sell_History.id, 
                Sell_History.Sell_id, 
                Sell_History.product_id, 
                Sell_History.Order_id, 
                Sell_History.isApproved, 
                Sell_History.quantity, 
                Sell_History.Remaining_stock, 
                Sell_History.date_of_sell, 
                Sell_History.total_amount, 
                Sell_History.price, 
                Sell_History.product_name, 
                Sell_History.user_id, 
                Sell_History.user_name,
                COALESCE(Sell_History.image_url, Products.image_url) AS image_url
            FROM Sell_History
            LEFT JOIN Products ON Sell_History.product_id = Products.Product_id
            WHERE Sell_History.user_id = ?
        ''', (user_id,))
        sell_history = cursor.fetchall()

        sellJson = []
        for sell in sell_history:
            tempSell = {
                "id": sell[0],
                "Sell_id": sell[1],
                "product_id": sell[2],
                "Order_id": sell[3],
                "isApproved": bool(sell[4]),
                "quantity": sell[5],
                "remaining_stock": sell[6],
                "date_of_sell": sell[7],
                "total_amount": sell[8],
                "price": sell[9],
                "product_name": sell[10],
                "user_id": sell[11],
                "user_name": sell[12],
                "image_url": sell[13] if len(sell) > 13 else None
            }
            sellJson.append(tempSell)
        return sellJson
    finally:
        conn.close()

def getProductSellHistory(Product_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                Sell_History.id, 
                Sell_History.Sell_id, 
                Sell_History.product_id, 
                Sell_History.Order_id, 
                Sell_History.isApproved, 
                Sell_History.quantity, 
                Sell_History.Remaining_stock, 
                Sell_History.date_of_sell, 
                Sell_History.total_amount, 
                Sell_History.price, 
                Sell_History.product_name, 
                Sell_History.user_id, 
                Sell_History.user_name,
                COALESCE(Sell_History.image_url, Products.image_url) AS image_url
            FROM Sell_History
            LEFT JOIN Products ON Sell_History.product_id = Products.Product_id
            WHERE Sell_History.product_id = ?
        ''', (Product_id,))
        sell_history = cursor.fetchall()

        sellJson = []
        for sell in sell_history:
            tempSell = {
                "id": sell[0],
                "Sell_id": sell[1],
                "product_id": sell[2],
                "Order_id": sell[3],
                "isApproved": bool(sell[4]),
                "quantity": sell[5],
                "remaining_stock": sell[6],
                "date_of_sell": sell[7],
                "total_amount": sell[8],
                "price": sell[9],
                "product_name": sell[10],
                "user_id": sell[11],
                "user_name": sell[12],
                "image_url": sell[13] if len(sell) > 13 else None
            }
            sellJson.append(tempSell)
        return sellJson
    finally:
        conn.close()
