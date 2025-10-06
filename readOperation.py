import sqlite3
from flask import Flask,jsonify
from flask_jwt_extended import jwt_required


def getAllUsers():
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Users ')

    users = cursor.fetchall()

    userJson = []
    for user in users:                  # this loop is used to assign specific key to the values 
        tempUser = {
            "id": user[0],
             "user_id":user[1],
            "password": user[2],
            "date_of_account_creation": user[3],
            "isApproved": bool(user[4]) if isinstance(user[4], int) else user[4] == "true",
            "block": bool(user[5]) if isinstance(user[5], int) else user[5] == "true",
            "name": user[6],
            "address": user[7],
            "email":user[8],
            "phone_number": user[9],
            "pin_code":user[10],
            "role": user[11]
        }
        userJson.append(tempUser)    
    conn.close()    
    return userJson               # no change in database thus no use of commit 

def getAllAdmins():
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Admin ')

    admins = cursor.fetchall()

    adminJson = []
    for admin in admins:                  # this loop is used to assign specific key to the values 
        tempUser = {
            "id": admin[0],
            "admin_id":admin[1],
            "password": admin[2],
            "date_of_account_creation": admin[3],
            "name": admin[4],
            "email":admin[5],
            "phone_number": admin[6],
            "role": admin[7]
           
        }
        adminJson.append(tempUser)    
    conn.close()    
    return adminJson               # no change in database thus no use of commit 


def getSpecificUser(userId):
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Users WHERE user_id = ?",(userId,))       # after userId use , "comma" so that it can understand as tuple
    user = cursor.fetchone()   
    conn.close() 
    

    tempUser = {
            "id": user[0],
            "user_id":user[1],
            "password": user[2],
            "date_of_account_creation": user[3],
            "isApproved": user[4],
            "block": user[5],
            "name": user[6],
            "address": user[7],
            "email":user[8],
            "phone_number": user[9],
            "pin_code":user[10]
        }  
    return tempUser

def getAllProducts():

    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Products ')
    products = cursor.fetchall();
    conn.close()

    productJson = []
    for product in products:
        tempProduct = {
            "id": product[0],
            "Product_id":product[1],
            "name": product[2],
            "price": product[3],
            "category": product[4],
            "stock": product[5]
        }
        productJson.append(tempProduct)             # i can call this json in tempproduct directly not in userjson
    return productJson               # no change in database thus no use of commit
    
       
    
def getspecificproduct(Product_id):        
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Products WHERE Product_id = ?",(Product_id,))       # after userId use , "comma" so that it can understand as tuple
    product = cursor.fetchone()
    conn.close()
    tempProduct = {
            "id": product[0],
            "Product_id":product[1],
            "name": product[2],
            "price": product[3],
            "category": product[4],
            "stock": product[5]
        }
   
    return tempProduct

def getAllOrders():

    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Order_Details')

    orders = cursor.fetchall()
    conn.close()

    orderJson = []
    for order in orders:
        tempOrder = {
            "id": order[0],
            "order_id":order[1],
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
            "sold": bool(order[13])
        }
        orderJson.append(tempOrder)
    return orderJson               # no change in database thus no use of commit
       
def getUserOrders(user_id):
    
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Order_Details WHERE user_id = ?",(user_id,))       # after userId use , "comma" so that it can understand as tuple
    orders = cursor.fetchall()
    conn.close()

    orderJson = []
    for order in orders:
        tempOrder = {
            "id": order[0],
            "order_id":order[1],
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
            "sold": bool(order[13])
        }
        orderJson.append(tempOrder)
    return orderJson

def getOrderById(Order_id):
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Order_Details WHERE Order_id = ?",(Order_id,))       # after userId use , "comma" so that it can understand as tuple
    order = cursor.fetchone()
    conn.close()

    if order is None:
        return None

    tempOrder = {
        "id": order[0],
        "order_id":order[1],
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
        "sold": bool(order[13])
    }
    
    return tempOrder
       
        



def getSellHistory():

    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Sell_History')
    sell_history = cursor.fetchall()
    conn.close()

    sellJson = []
    for sell in sell_history:
        tempSell = {
             "id": sell[0],
            "Sell_id":sell[1],
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
            "user_name": sell[12],}
        sellJson.append(tempSell)
    return sellJson


def getUserSellHistory(user_id):

    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Sell_History WHERE user_id = ?",(user_id,))       # after userId use , "comma" so that it can understand as tuple
    sell_history = cursor.fetchall()
    conn.close()

    sellJson = []
    for sell in sell_history:
        tempSell = {
             "id": sell[0],
            "Sell_id":sell[1],
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

def getProductSellHistory(Product_id):

    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Sell_History WHERE product_id = ?",(Product_id,))       # after userId use , "comma" so that it can understand as tuple
    sell_history = cursor.fetchall()
    conn.close()

    sellJson = []
    for sell in sell_history:
        tempSell = {
            "id": sell[0],
            "Sell_id":sell[1],
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
        

