import os
import sqlite3
import uuid
from datetime import date
from werkzeug.security import generate_password_hash

def get_db():
    db_name = os.getenv("DATABASE_NAME", "My_Medical_Shope.db")
    return sqlite3.connect(db_name)

def createAdmin(email, name, password, phoneNumber, role):
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM Admin WHERE email = ?', (email,))
            if cursor.fetchone():
                return {'message': 'Email already registered', 'status': 409}

            admin_id = "AID" + str(uuid.uuid4().hex)[:8]
            date_of_creation = date.today().isoformat()
            hashpassword = generate_password_hash(password)
            cursor.execute('''
INSERT INTO Admin(admin_id, password, name, email, phone_number, date_of_account_creation, role) VALUES(?,?,?,?,?,?,?)
''', (admin_id, hashpassword, name, email, phoneNumber, date_of_creation, role))

        return {'message': f"Admin created with role {role} and admin id = ${admin_id} ", 'status': 201}
    except Exception as error:
        return {'message': str(error), 'status': 400}
    finally:
        conn.close()

def createUser(name, password, phoneNumber, email, pincode, address, role):
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()
            if email:
                cursor.execute('SELECT 1 FROM Users WHERE email = ?', (email,))
                if cursor.fetchone():
                    return {'message': 'Email already registered', 'status': 409}
            if phoneNumber:
                cursor.execute('SELECT 1 FROM Users WHERE phone_number = ?', (phoneNumber,))
                if cursor.fetchone():
                    return {'message': 'Phone number already registered', 'status': 409}

            user_id = "UID" + str(uuid.uuid4().hex)[:8]
            date_of_creation = date.today().isoformat()
            hash_password = generate_password_hash(password)

            cursor.execute('''
INSERT INTO Users(user_id, password, date_of_account_creation, isApproved, block, name, address, email, phone_number, pin_code, role) VALUES(?,?,?,?,?,?,?,?,?,?,?)
''', (user_id, hash_password, date_of_creation, False, False, name, address, email, phoneNumber, pincode, role))

        return {'message': f"User created with role {role} and user id = ${user_id} ", 'status': 201}
    except Exception as error:
        return {'message': str(error), 'status': 400}
    finally:
        conn.close()

def addProduct(name, price, category, stock, image_url=None):
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()
            Product_id = "PROD_" + str(uuid.uuid4().hex)[:8]
            cursor.execute('''
INSERT INTO Products(Product_id, name, price, category, stock, image_url) VALUES(?,?,?,?,?,?)
''', (Product_id, name, price, category, stock, image_url))
        return {'message': Product_id, 'status': 201}
    except Exception as error:
        return {'message': str(error), 'status': 400}
    finally:
        conn.close()

def createOrder(user_id, Product_id, quantity, message=""):
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()
            order_id = "ORD" + str(uuid.uuid4().hex)[:8]
            date_of_order_creation = date.today().isoformat()

            cursor.execute('SELECT name, price, category FROM Products WHERE Product_id = ?', (Product_id,))
            product = cursor.fetchone()
            if not product:
                return {'message': 'Product not found', 'status': 404}
            name, price, category = product
            product_name = name

            cursor.execute('SELECT name FROM Users WHERE user_id = ?', (user_id,))
            user = cursor.fetchone()
            if not user:
                return {'message': 'User not found', 'status': 404}
            user_name = user[0]

            total_amount = price * quantity
            cursor.execute('''
INSERT INTO Order_Details(Order_id, user_id, Product_id, isApproved, quantity, date_of_order_creation, price, total_amount, product_name, user_name, message, category, sold) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
''', (order_id, user_id, Product_id, 0, quantity, date_of_order_creation, price, total_amount, product_name, user_name, message, category, 0))

        return {'message': order_id, 'status': 201}
    except Exception as error:
        return {'message': str(error), 'status': 400}
    finally:
        conn.close()

def record_Sell(Order_id):
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM Sell_History WHERE Order_id = ?', (Order_id,))
            if cursor.fetchone():
                return {'message': 'Sell record already exists for this order', 'status': 200}

            cursor.execute('''
                SELECT user_id, Product_id, quantity, price, product_name, user_name, category, isApproved
                FROM Order_Details
                WHERE Order_id = ?
            ''', (Order_id,))
            order = cursor.fetchone()
            if not order:
                return {'message': 'Order not found', 'status': 404}

            user_id, Product_id, quantity, price, product_name, user_name, category, isApproved = order
            if not isApproved:
                return {'message': 'Order not approved by admin', 'status': 400}

            cursor.execute('SELECT stock FROM Products WHERE Product_id = ?', (Product_id,))
            product = cursor.fetchone()
            if not product:
                return {'message': 'Product not found', 'status': 404}
            stock = product[0]
            if stock < quantity:
                return {'message': 'Not enough stock available', 'status': 400}

            total_amount = price * quantity
            Remaining_stock = stock - quantity

            cursor.execute('UPDATE Products SET stock = ? WHERE Product_id = ?', (Remaining_stock, Product_id))

            Sell_id = "SELL" + str(uuid.uuid4().hex)[:8]
            cursor.execute('''
INSERT INTO Sell_History(Sell_id, product_id, Order_id, isApproved, quantity, Remaining_stock, date_of_sell, total_amount, price, product_name, user_id, user_name)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (Sell_id, Product_id, Order_id, isApproved, quantity, Remaining_stock, date.today().isoformat(), total_amount, price, product_name, user_id, user_name))

        return {'message': Sell_id, 'status': 201}
    except Exception as error:
        return {'message': str(error), 'status': 400}
    finally:
        conn.close()
