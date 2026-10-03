import os
import sqlite3
import time
from werkzeug.security import check_password_hash, generate_password_hash
from app.services.email_service import send_otp_email, generate_otp
from app.services.otp_service import store_otp, verify_and_consume_otp, otp_store

QUERIES = {
    "user": {
        "by_email": "SELECT user_id, password, role FROM Users WHERE email = ?",
        "by_id": "SELECT user_id, role FROM Users WHERE user_id = ?",
        "update_pw": "UPDATE Users SET password = ? WHERE user_id = ?",
        "id_col": "user_id"
    },
    "admin": {
        "by_email": "SELECT admin_id, password, role FROM Admin WHERE email = ?",
        "by_id": "SELECT admin_id, role FROM Admin WHERE admin_id = ?",
        "update_pw": "UPDATE Admin SET password = ? WHERE admin_id = ?",
        "id_col": "admin_id"
    }
}

def get_db_connection():
    db_name = os.getenv("DATABASE_NAME", "My_Medical_Shope.db")
    conn = sqlite3.connect(db_name)
    conn.row_factory = sqlite3.Row
    return conn

def _get_user_by_email(email, user_type):
    if user_type not in QUERIES:
        return None
    query = QUERIES[user_type]["by_email"]

    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(query, (email,))
            return cursor.fetchone()
    finally:
        conn.close()

def authenticate(email, password, user_type):
    """Return (user_id, role) on success, or None on failure."""
    user = _get_user_by_email(email, user_type)
    if user and check_password_hash(user["password"], password):
        id_column = QUERIES[user_type]["id_col"]
        return user[id_column], user["role"]
    return None

def request_password_reset(email, user_type):
    user = _get_user_by_email(email, user_type)
    if not user:
        return {"message": "Email not registered", "status": 404}

    id_column = QUERIES[user_type]["id_col"]
    user_id = user[id_column]

    otp = generate_otp()
    otp_store[user_id] = {"otp": otp, "expiry": time.time() + 300}

    if send_otp_email(to_email=email, otp=otp):
        return {"message": f"OTP {otp} sent to your email", "user_id": user_id, "status": 200}
    else:
        return {"message": "Failed to send OTP email (check SMTP server).", "user_id": user_id, "status": 500}

def reset_password_with_otp(user_id, otp, new_password, user_type):
    if user_id not in otp_store:
        return {"message": "No OTP request found or OTP expired", "status": 400}

    stored_otp = otp_store[user_id]["otp"]
    expiry = otp_store[user_id]["expiry"]

    if time.time() > expiry:
        del otp_store[user_id]
        return {"message": "OTP expired", "status": 400}

    if str(otp) == str(stored_otp):
        hashed_password = generate_password_hash(new_password)
        query = QUERIES[user_type]["update_pw"]

        conn = get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(query, (hashed_password, user_id))
        finally:
            conn.close()

        del otp_store[user_id]
        return {"message": "Password reset successful", "status": 200}
    else:
        return {"message": "Invalid OTP", "status": 400}

def get_user_by_id(user_id, user_type):
    if user_type not in QUERIES:
        return None, None
    query = QUERIES[user_type]["by_id"]

    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(query, (user_id,))
            user = cursor.fetchone()
            if user:
                id_column = QUERIES[user_type]["id_col"]
                return user[id_column], user["role"]
            return None, None
    finally:
        conn.close()
