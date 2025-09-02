import sqlite3,secrets
from flask import jsonify


def update_approve_user(userId, approve):

    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute('UPDATE Users SET isApproved = ? WHERE user_id=?',(approve,userId))

    conn.commit()
    conn.close()

def add_api_key_column():
    try:
        conn = sqlite3.connect("My_Medical_Shope.db")  # Database connect karo
        cursor = conn.cursor()
        
        # Naya column add karne ke liye SQL query
        cursor.execute("ALTER TABLE Users ADD COLUMN api_key TEXT UNIQUE;")

        conn.commit()
        conn.close()

        return {"message": "API key column added successfully", "status": 200}

    except Exception as error:
        return {"message": str(error), "status": 400}



def update_user_details(user_id,updateUser : dict):
    conn = sqlite3.connect("My_Medical_Shope.db")

    cursor =conn.cursor()
    count = 0
    for key , value in updateUser.items():              # taking all the items from dictonary where all the key and value stored 
        if key == 'name':
            cursor.execute('UPDATE Users SET name = ? WHERE user_id = ?',(value, user_id))
            count = count+1
        elif key == 'password':
            cursor.execute('UPDATE Users SET password = ? WHERE user_id = ?',(value, user_id))
            count +=1
        elif key == 'date_of_account_creation':
            cursor.execute('UPDATE Users SET date_of_account_creation = ? WHERE user_id = ?',(value, user_id))
            count +=1
        elif key == 'isApproved':
            cursor.execute('UPDATE Users SET isApproved = ? WHERE user_id = ?',(value, user_id))
            count +=1
        elif key == 'block':
            cursor.execute('UPDATE Users SET block = ? WHERE user_id = ?',(value, user_id))
            count +=1
        elif key == 'address':
            cursor.execute('UPDATE Users SET address = ? WHERE user_id = ?',(value, user_id))
            count +=1
        elif key == 'email':
            cursor.execute('UPDATE Users SET email = ? WHERE user_id = ?',(value, user_id))
            count +=1
        elif key == 'phone_number':
            cursor.execute('UPDATE Users SET phone_number = ? WHERE user_id = ?',(value, user_id))
            count +=1
        elif key == 'pin_code':
            cursor.execute('UPDATE Users SET pin_code = ? WHERE user_id = ?',(value, user_id))
            count +=1
        
    conn.commit()
    conn.close()
    return count


# Products table update and delete operation
def update_product(Product_id, updateProduct : dict):
    try:
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()
        for key, value in updateProduct.items():
            if key == 'name':
                cursor.execute('UPDATE Products SET name = ? WHERE Product_id = ?', (value, Product_id))
            elif key == 'price':
                cursor.execute('UPDATE Products SET price = ? WHERE Product_id = ?', (value, Product_id))
            elif key == 'category':
                cursor.execute('UPDATE Products SET category = ? WHERE Product_id = ?', (value, Product_id))
            elif key == 'stock':
                cursor.execute('UPDATE Products SET stock = ? WHERE Product_id = ?', (value, Product_id))

        conn.commit()
        conn.close()
        return jsonify({'message': 'Product updated successfully', 'status': 200})
    except Exception as error:
        return jsonify({'message': str(error), 'status': 400})

# Order table update operation 
def update_Order(Order_id, updateOrder : dict):
    try:
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()
        for key, value in updateOrder.items():
            if key == 'isApproved':
                cursor.execute('UPDATE Order_Details SET isApproved = ? WHERE Order_id = ?', (value, Order_id))
            elif key == 'quantity':
                cursor.execute('UPDATE Order_Details SET quantity = ? WHERE Order_id = ?', (value, Order_id))
            elif key == 'price':
                cursor.execute('UPDATE Order_Details SET price = ? WHERE Order_id = ?', (value, Order_id))
            elif key == 'total_amount':
                cursor.execute('UPDATE Order_Details SET total_amount = ? WHERE Order_id = ?', (value, Order_id))
            elif key == 'product_name':
                cursor.execute('UPDATE Order_Details SET product_name = ? WHERE Order_id = ?', (value, Order_id))
            elif key == 'message':
                cursor.execute('UPDATE Order_Details SET message = ? WHERE Order_id = ?', (value, Order_id))
            
        conn.commit()
        conn.close()
        return jsonify({'message': 'Order updated successfully', 'status': 200})
    except Exception as error:
        return jsonify({'message': str(error), 'status': 400})


def approve_Order(Order_id,isApproved : int):
    try:
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()
        
        
        cursor.execute('UPDATE Order_Details SET isApproved = ? WHERE Order_id = ?', (isApproved, Order_id))
        

        conn.commit()
        conn.close()
        # if affected_rows > 0:
        return jsonify({'message': 'Order updated successfully', 'status': 200})
        # return jsonify({'message': 'Order not found  ', 'status': 404})
    except Exception as error:
        return jsonify({'message': str(error), 'status': 400})



