import sqlite3
from flask import jsonify

def delete_User(user_id):
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()

    cursor.execute('DELETE FROM Users WHERE user_id = ?',(user_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': 'User Deleted Successfully', 'status': 200})


# Products table delete operation 
def delete_Product(Product_id):
    try:
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()
        cursor.execute('DELETE FROM Products WHERE Product_id = ?', (Product_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Product deleted successfully', 'status': 200})

    except Exception as error:
        return jsonify({'message': str(error), 'status': 400})  

def delete_Order(Order_id):
    try:
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()
        cursor.execute('DELETE FROM Order_Details WHERE Order_id = ?', (Order_id,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Order deleted successfully', 'status': 200})

    except Exception as error:
        return jsonify({'message': str(error), 'status': 400})



