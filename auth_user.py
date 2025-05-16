import sqlite3


def authenticate_user(email, password):
    
    conn = sqlite3.connect("My_Medical_Shope.db")           # database se connect / open
    cursor = conn.cursor()                                  # curson ko open kr rhe jisme saare data aayege 

    cursor.execute("SELECT * FROM Users WHERE email = ? AND password = ?",(email, password))            # Users tables se sabhi row ko fetch krege jiske email and password match krega 

    user = cursor.fetchone()      # cursor ke pass sare data aayege tab usme se fetch one krege 

    conn.close()

    return user
