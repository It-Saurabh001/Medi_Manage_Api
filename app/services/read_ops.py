import os
import sqlite3

def get_db():
    db_name = os.getenv("DATABASE_NAME", "My_Medical_Shope.db")
    return sqlite3.connect(db_name)

def getAllUsers():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, user_id, date_of_account_creation, isApproved, block, name, address, email, phone_number, pin_code, role FROM Users')
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
                "role": user[10] if len(user) > 10 else "user"
            }
            userJson.append(tempUser)
        return userJson
    finally:
        conn.close()

def getAllAdmins():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, admin_id, date_of_account_creation, name, email, phone_number, role FROM Admin')
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
                "role": admin[6] if len(admin) > 6 else "admin"
            }
            adminJson.append(tempAdmin)
        return adminJson
    finally:
        conn.close()

def getSpecificUser(userId):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, user_id, date_of_account_creation, isApproved, block, name, address, email, phone_number, pin_code, role FROM Users WHERE user_id = ?', (userId,))
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
            "role": user[10] if len(user) > 10 else "user"
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
        cursor.execute('SELECT id, Order_id, user_id, product_id, isApproved, quantity, date_of_order_creation, price, total_amount, product_name, user_name, message, category, sold FROM Order_Details')
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
                "sold": bool(order[13]) if len(order) > 13 else False
            }
            orderJson.append(tempOrder)
        return orderJson
    finally:
        conn.close()

def getUserOrders(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, Order_id, user_id, product_id, isApproved, quantity, date_of_order_creation, price, total_amount, product_name, user_name, message, category, sold FROM Order_Details WHERE user_id = ?', (user_id,))
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
                "sold": bool(order[13]) if len(order) > 13 else False
            }
            orderJson.append(tempOrder)
        return orderJson
    finally:
        conn.close()

def getOrderById(Order_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, Order_id, user_id, product_id, isApproved, quantity, date_of_order_creation, price, total_amount, product_name, user_name, message, category, sold FROM Order_Details WHERE Order_id = ?', (Order_id,))
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
            "sold": bool(order[13]) if len(order) > 13 else False
        }
        return tempOrder
    finally:
        conn.close()

def getSellHistory():
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, Sell_id, product_id, Order_id, isApproved, quantity, Remaining_stock, date_of_sell, total_amount, price, product_name, user_id, user_name FROM Sell_History')
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
            }
            sellJson.append(tempSell)
        return sellJson
    finally:
        conn.close()

def getUserSellHistory(user_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, Sell_id, product_id, Order_id, isApproved, quantity, Remaining_stock, date_of_sell, total_amount, price, product_name, user_id, user_name FROM Sell_History WHERE user_id = ?', (user_id,))
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
            }
            sellJson.append(tempSell)
        return sellJson
    finally:
        conn.close()

def getProductSellHistory(Product_id):
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT id, Sell_id, product_id, Order_id, isApproved, quantity, Remaining_stock, date_of_sell, total_amount, price, product_name, user_id, user_name FROM Sell_History WHERE product_id = ?', (Product_id,))
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
            }
            sellJson.append(tempSell)
        return sellJson
    finally:
        conn.close()
