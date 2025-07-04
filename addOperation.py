import sqlite3              # import sqlite3 to connect with database
import uuid, secrets
from datetime import date
from flask import Flask, jsonify


def createUser( name, password, phoneNumber, email, pincode, address):

    try:
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()         # manager of database


        user_id = str(uuid.uuid4())        # generating user id in string
        date_of_Account_creation = date.today()     ## to assign date of creation
        cursor.execute('''

INSERT INTO Users_New(user_id, password ,date_of_account_creation ,isApproved , block , name, address , email , phone_number ,pin_code) VALUES(?,?,?,?,?,?,?,?,?,?)

''', (user_id, password, date_of_Account_creation, False, False, name, address, email,phoneNumber,pincode))



        conn.commit()
        conn.close() 
        return jsonify({'message': user_id, 'status':200})
    
    except Exception as error:
        return   jsonify({'message': str(error), "status" : 400})
    
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

def record_Sell(Product_id, quantity, user_id):
    try:
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()
        cursor.execute('SELECT name, price, stock FROM Products WHERE Product_id = ?', (Product_id,))
        product = cursor.fetchone()
        if not product:
            conn.close()
            return jsonify({'message': 'Product not found', 'status': 404})
        name , price, stock = product
        product_name = name
        if stock < quantity:
            conn.close()
            return jsonify({'message': 'Not enough stock available', 'status': 400})
        
        cursor.execute('SELECT name FROM Users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            return jsonify({'message': 'User not found', 'status': 404})
        name = user[0]
        user_name = name
        total_amount = price * quantity             # calculating total amount
        Remaining_stock = stock - quantity
        cursor.execute('UPDATE Products SET stock = ? WHERE Product_id = ?', (Remaining_stock, Product_id))

        Sell_id = "SELL"+str(uuid.uuid4().hex)[:8]        # generating user id in string
        cursor.execute('''
INSERT INTO Sell_History(Sell_id, Product_id, quantity, Remaining_stock, date_of_sell, total_amount, price, product_name, user_id, user_name) VALUES(?,?,?,?,?,?,?,?,?,?)
''',(Sell_id, Product_id, quantity, Remaining_stock, date.today(), total_amount, price, product_name, user_id, user_name))
        
        #update the stock in Available_product table
        cursor.execute('UPDATE Available_product SET Remaining_stock = ? WHERE Product_id = ?', (Remaining_stock, Product_id))
        conn.commit()
        conn.close()
        return jsonify({'message': Sell_id, 'status': 201})
    except Exception as error:
        return jsonify({'message': str(error), 'status': 400})
    


        





