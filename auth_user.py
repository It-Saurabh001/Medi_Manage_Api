import sqlite3
import time
import random
from werkzeug.security import check_password_hash, generate_password_hash
from verification import send_otp_email
from flask import jsonify

# NOTE: It's recommended to use a more persistent and scalable OTP store in a production environment, such as Redis or a database table.
otp_store = {}

# NOTE: Database connection should be managed in a central place, for example, using Flask's application context.
# This is a simplified example.
def get_db_connection():
    conn = sqlite3.connect("My_Medical_Shope.db")
    conn.row_factory = sqlite3.Row
    return conn

def generate_otp():
    return str(random.randint(100000, 999999))

def _get_user_by_email(email, user_type):
    table_name = "Users" if user_type == "user" else "Admin"
    id_column = "user_id" if user_type == "user" else "admin_id"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {id_column}, password, role FROM {table_name} WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return user

def authenticate(email, password, user_type):
    """Return (user_id, role) on success, or None on failure."""
    user = _get_user_by_email(email, user_type)
    if user and check_password_hash(user['password'], password):
        id_column = "user_id" if user_type == "user" else "admin_id"
        return user[id_column], user['role']
    return None

def request_password_reset(email, user_type):
    user = _get_user_by_email(email, user_type)
    if not user:
        return jsonify({'message': 'Email not registered','status': 404})

    id_column = "user_id" if user_type == "user" else "admin_id"
    user_id = user[id_column]
    
    otp = generate_otp()
    expiry = time.time() + 300  # 5 minutes
    otp_store[user_id] = {"otp": otp, "expiry": expiry}

    subject = "Your Password Reset OTP"
    body = f"Your OTP for password reset is: {otp}. It will expire in 5 minutes."
    
    # send_otp_email returns True on success, False on failure
    if send_otp_email(to_email=email, otp=otp):
        return jsonify({'message': f'OTP {otp} sent to your email', 'user_id': user_id,'status': 200})
    else:
        # Keep OTP in memory (debug) and inform the client the email failed
        return jsonify({'message': 'Failed to send OTP email (check SMTP server). OTP has been logged on server for debugging.', 'user_id': user_id,'status': 500})

def reset_password_with_otp(user_id, otp, new_password, user_type):
    if user_id not in otp_store:
        return jsonify({'message': 'No OTP request found or OTP expired','status': 400})

    stored_otp = otp_store[user_id]['otp']
    expiry = otp_store[user_id]['expiry']

    if time.time() > expiry:
        del otp_store[user_id]
        return jsonify({'message': 'OTP expired','status': 400})

    # Compare as strings to avoid type mismatch (stored_otp may be string)
    if str(otp) == str(stored_otp):
        hashed_password = generate_password_hash(new_password)
        table_name = "Users" if user_type == "user" else "Admin"
        id_column = "user_id" if user_type == "user" else "admin_id"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE {table_name} SET password = ? WHERE {id_column} = ?", (hashed_password, user_id))
        conn.commit()
        conn.close()
        
        del otp_store[user_id]
        return jsonify({'message': 'Password reset successful','status': 200})
    else:
        return jsonify({'message': 'Invalid OTP','status': 400})

def get_user_by_id(user_id, user_type):
    table_name = "Users" if user_type == "user" else "Admin"
    id_column = "user_id" if user_type == "user" else "admin_id"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT {id_column}, role FROM {table_name} WHERE {id_column} = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return user[id_column], user['role']
    return None, None
