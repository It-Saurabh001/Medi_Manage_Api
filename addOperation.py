import sqlite3              # import sqlite3 to connect with database
import uuid, secrets
from datetime import date
from flask import Flask, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

def createAdmin(email, name, password,phoneNumber, role):
    try:
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()

        # Check if email already exists
        cursor.execute('SELECT 1 FROM Admin WHERE email = ?',(email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'message': 'Email already registered', 'status': 409})

        admin_id = "AID"+str(uuid.uuid4().hex)[:8]        #generating admin id
        date_of_Account_creation = date.today()     ## to assign date of creation
        hashpassword = generate_password_hash(password)
        cursor.execute('''
INSERT INTO Admin(admin_id, password, name, email,phone_number,date_of_account_creation, role) VALUES(?,?,?,?,?,?,?)
''', (admin_id, hashpassword, name, email,phoneNumber, date_of_Account_creation, role))

        conn.commit()
        conn.close()
        return jsonify({'message': f"Admin created with role {role} and admin id = ${admin_id} ", 'status': 201})

    except Exception as error:
        return jsonify({'message': str(error), "status": 400})



def createUser(name, password, phoneNumber, email, pincode, address,role):
    try:
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()

        # Check if email already exists
        cursor.execute('SELECT 1 FROM Users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'message': 'Email already registered', 'status': 409})

        user_id = "UID"+str(uuid.uuid4().hex)[:8]        # generating user id in string
        date_of_Account_creation = date.today()     ## to assign date of creation
        
        # hasing password 
        hash_password = generate_password_hash(password)
        cursor.execute('''
INSERT INTO Users(user_id, password ,date_of_account_creation ,isApproved , block , name, address , email , phone_number ,pin_code,role) VALUES(?,?,?,?,?,?,?,?,?,?,?)
''', (user_id, hash_password, date_of_Account_creation, False, False, name, address, email, phoneNumber, pincode,role))

        conn.commit()
        conn.close() 
        return jsonify({'message': f"User created with role {role}  and user id = ${user_id} ", 'status': 201})

    except Exception as error:
        return jsonify({'message': str(error), "status": 400})
    
def addProduct(name, price, category, stock):
    try: 
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()
        Product_id = "PROD_"+str(uuid.uuid4().hex)[:8]        # generating user id in string
        cursor.execute('''
INSERT INTO Products(Product_id, name, price, category, stock) VALUES(?,?,?,?,?)
''', (Product_id, name, price, category, stock))
        conn.commit()
        conn.close()
        return jsonify({'message': Product_id, 'status': 200})
    
    except Exception as error:
        return jsonify({'message': str(error), 'status': 400})
    


def createOrder(user_id, Product_id, quantity,message):
    try:

        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()
        order_id = "ORD"+str(uuid.uuid4().hex)[:8]        # generating user id in string
        date_of_order_creation = date.today()
        cursor.execute('SELECT name, price, category FROM Products WHERE Product_id = ?', (Product_id,))
        product = cursor.fetchone()
        if not product:
            conn.close()
            return jsonify({'message': 'Product not found', 'status': 404}) 
        name , price, category = product
        product_name = name
        cursor.execute('SELECT name FROM Users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            return jsonify({'message': 'User not found', 'status': 404})
        name = user[0]
        user_name = name

        total_amount = price * quantity             # calculating total amount
        cursor.execute('''
INSERT INTO Order_Details(Order_id, user_id, Product_id, isApproved, quantity, date_of_order_creation, price, total_amount, product_name, user_name, message, category) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
''',(order_id, user_id, Product_id, 0, quantity, date_of_order_creation, price, total_amount, product_name, user_name, message, category))

        conn.commit()
        conn.close()
        return jsonify({'message': order_id, 'status': 201})
    except Exception as error:
        return jsonify({'message': str(error), 'status': 400})

def record_Sell(Order_id):
    try:
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()

        # Check if Sell_History already has a record for this Order_id
        cursor.execute('SELECT 1 FROM Sell_History WHERE Order_id = ?', (Order_id,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'message': 'Sell record already exists for this order', 'status': 200})

        # Fetch order details using order_id and check if approved
        cursor.execute('''
            SELECT user_id, Product_id, quantity, price, product_name, user_name, category, isApproved
            FROM Order_Details
            WHERE Order_id = ?
        ''', (Order_id,))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return jsonify({'message': 'Order not found', 'status': 404})

        user_id, Product_id, quantity, price, product_name, user_name, category, isApproved = order

        if not isApproved:
            conn.close()
            return jsonify({'message': 'Order not approved by admin', 'status': 400})

        # Fetch product stock
        cursor.execute('SELECT stock FROM Products WHERE Product_id = ?', (Product_id,))
        product = cursor.fetchone()
        if not product:
            conn.close()
            return jsonify({'message': 'Product not found', 'status': 404})
        stock = product[0]
        print("product stock:", stock)
        print(f"Fetched stock: {stock}, Required quantity: {quantity}")
        if stock < quantity:
            conn.close()
            return jsonify({'message': 'Not enough stock available', 'status': 400})

        total_amount = price * quantity
        Remaining_stock = stock - quantity

        # Update product stock
        cursor.execute('UPDATE Products SET stock = ? WHERE Product_id = ?', (Remaining_stock, Product_id))

        Sell_id = "SELL" + str(uuid.uuid4().hex)[:8]
        cursor.execute('''
INSERT INTO Sell_History(Sell_id, product_id, Order_id, isApproved, quantity, Remaining_stock, date_of_sell, total_amount, price, product_name, user_id, user_name)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', (Sell_id, Product_id, Order_id, isApproved, quantity, Remaining_stock, date.today(), total_amount, price, product_name, user_id, user_name))

        conn.commit()
        conn.close()
        return jsonify({'message': Sell_id, 'status': 201})
    except Exception as error:
        return jsonify({'message': str(error), 'status': 400})









