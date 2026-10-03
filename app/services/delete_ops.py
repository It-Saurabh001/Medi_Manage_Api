import os
import sqlite3

def get_db():
    db_name = os.getenv("DATABASE_NAME", "My_Medical_Shope.db")
    return sqlite3.connect(db_name)

def delete_User(user_id):
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM Users WHERE user_id = ?', (user_id,))
        return {'message': 'User Deleted Successfully', 'status': 200}
    except Exception as error:
        return {'message': str(error), 'status': 400}
    finally:
        conn.close()

def delete_Admin(admin_id):
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM Admin WHERE admin_id = ?', (admin_id,))
        return {'message': 'Admin Deleted Successfully', 'status': 200}
    except Exception as error:
        return {'message': str(error), 'status': 400}
    finally:
        conn.close()

def delete_Product(Product_id):
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM Products WHERE Product_id = ?', (Product_id,))
        return {'message': 'Product deleted successfully', 'status': 200}
    except Exception as error:
        return {'message': str(error), 'status': 400}
    finally:
        conn.close()

def delete_Order(Order_id):
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM Order_Details WHERE Order_id = ?', (Order_id,))
        return {'message': 'Order deleted successfully', 'status': 200}
    except Exception as error:
        return {'message': str(error), 'status': 400}
    finally:
        conn.close()

def delete_SellHistory(Sell_id):
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM Sell_History WHERE Sell_id = ?', (Sell_id,))
        return {'message': 'Deleted successfully', 'status': 200}
    except Exception as error:
        return {'message': str(error), 'status': 400}
    finally:
        conn.close()
