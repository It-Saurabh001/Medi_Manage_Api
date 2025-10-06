import sqlite3,random,time
from werkzeug.security import check_password_hash, generate_password_hash
from verification import send_otp_email
from flask import jsonify
from otp_store import *


def authenticate_user(email, password):
    
    conn = sqlite3.connect("My_Medical_Shope.db")           # database se connect / open
    cursor = conn.cursor()                                  # curson ko open kr rhe jisme saare data aayege 

    cursor.execute("SELECT user_id,password, role FROM Users WHERE email = ?",(email,))            # Users tables se sabhi row ko fetch krege jiske email and password match krega 
    user = cursor.fetchone()      # cursor ke pass sare data aayege tab usme se fetch one krege 
    conn.close()
    if user :
        user_id,stored_password, role = user
         # Verify plain password against hashed password
        if check_password_hash(stored_password, password):
            return user_id, role  # return user id if authenticated
    return None  # return None if not authenticated


## request for reset user password 
def request_user_pswd_reset(email):
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM Users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    if not user:
        return {'status': 404, 'message': 'Email not registered'}
    user_id = user[0]
    otp = random.randint(100000, 999999)
    expiry = time.time() + 300  # 5 min
    user_otp_store[user_id] = {"otp": otp, "expiry": expiry}
    send_otp_email(to_email=email, otp=otp)
    return {'status': 200, 'user_id': user_id, 'message': 'OTP sent to your email'}

## reset password after opt matched

def reset_password_with_otp(user_id, otp, new_password):
    if user_id not in user_otp_store:
        return {'status': 400, 'message': 'No OTP request found'}
    stored_otp = user_otp_store[user_id]['otp']
    expiry = user_otp_store[user_id]['expiry']

    if time.time() > expiry:
        del user_otp_store[user_id]
        return {'status': 400, 'message': 'OTP expired'}

    if int(otp) == stored_otp:
        hashed_password = generate_password_hash(new_password)
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE Users SET password = ? WHERE user_id = ?", (hashed_password, user_id))
        conn.commit()
        conn.close()
        del user_otp_store[user_id]
        return {'status': 200, 'message': 'Password reset successful'}
    else:
        return {'status': 400, 'message': 'Invalid OTP'}



def authenticate_admin(email, password):
    
    conn = sqlite3.connect("My_Medical_Shope.db")           # database se connect / open
    cursor = conn.cursor()                                  # curson ko open kr rhe jisme saare data aayege 

    cursor.execute("SELECT admin_id,password, role FROM Admin WHERE email = ?",(email,))            # Users tables se sabhi row ko fetch krege jiske email and password match krega 

    user = cursor.fetchone()      # cursor ke pass sare data aayege tab usme se fetch one krege 

    conn.close()
    if user :
        user_id,stored_password, role = user
         # Verify plain password against hashed password
        if check_password_hash(stored_password, password):
            return user_id, role  # return admin id if authenticated

    return None  # return None if not authenticated

## request for reset user password 
def request_admin_pswd_reset(email):
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute("SELECT admin_id FROM Admin WHERE email = ?", (email,))
    admin = cursor.fetchone()
    conn.close()
    if not admin:
        return {'status': 404, 'message': 'Email not registered'}
    admin_id = admin[0]
    otp = random.randint(100000, 999999)
    expiry = time.time() + 300  # 5 min
    otp_store[admin_id] = {"otp": otp, "expiry": expiry}
    send_otp_email(to_email=email, otp=otp)
    return {'status': 200, 'admin_id': admin_id, 'message': 'OTP sent to your email'}

## reset password after opt matched

def reset_admin_pswd_with_otp(admin_id, otp, new_password):
    if admin_id not in otp_store:
        return {'status': 400, 'message': 'No OTP request found'}
    stored_otp = otp_store[admin_id]['otp']
    expiry = otp_store[admin_id]['expiry']

    if time.time() > expiry:
        del otp_store[admin_id]
        return {'status': 400, 'message': 'OTP expired'}

    if int(otp) == stored_otp:
        hashed_password = generate_password_hash(new_password)
        conn = sqlite3.connect("My_Medical_Shope.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE Admin SET password = ? WHERE admin_id = ?", (hashed_password, admin_id))
        conn.commit()
        conn.close()
        del otp_store[admin_id]
        return {'status': 200, 'message': 'Password reset successful'}
    else:
        return {'status': 400, 'message': 'Invalid OTP'}





def authenticate_admin_by_id(admin_id):
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute("SELECT admin_id, role FROM Admin WHERE admin_id = ?", (admin_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return user[0], user[1]
    return None, None




def authenticate_user_by_id(user_id):
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, role FROM Users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return user[0], user[1]
    return None, None