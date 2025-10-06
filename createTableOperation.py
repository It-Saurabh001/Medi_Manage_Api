import sqlite3
from werkzeug.security import generate_password_hash

def migrate_passwords():
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()

    cursor.execute("SELECT id, password FROM Users")
    users = cursor.fetchall()

    for user_id, pwd in users:
        # if password is not hashed (doesn't start with 'pbkdf2' or 'scrypt')
        if not (pwd.startswith("pbkdf2:") or pwd.startswith("scrypt:")):
            hashed = generate_password_hash(pwd)
            cursor.execute("UPDATE Users SET password=? WHERE id=?", (hashed, user_id))
            print(f"Updated password for user_id={user_id}")

    conn.commit()
    conn.close()

def updateTable():
    conn = sqlite3.connect("My_Medical_Shope.db")
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE Admin ADD COLUMN role VARCHAR(20) DEFAULT 'admin'")
    except sqlite3.OperationalError:
        print("Column sold alerady exists in Order_Details table")

   
    conn.commit()
    conn.close()



def createTable():                  #function for creation of table 
    
    conn = sqlite3.connect("My_Medical_Shope.db")          # conneting sqlite with database and automatically create  "My_Medical_Shope.db" database
    cursor = conn.cursor()                     # cursor is used to assign operation to database

    # amin table
    cursor.execute('''
CREATE TABLE IF NOT EXISTS Admin(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id TEXT UNIQUE,
                    password TEXT,
                    date_of_account_creation DATE,
                    name TEXT,
                    email TEXT UNIQUE,
                    phone_number TEXT UNIQUE DEFAULT NULL,                    
                    role VARCHAR(20) DEFAULT 'admin'
                    )
''')    


    #User table creation 
    cursor.execute('''

CREATE TABLE IF NOT EXISTS Users(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id VARCHAR(255),    
                    password VARCHAR(255),
                    date_of_account_creation DATE,
                    isApproved BOOLEAN,
                    block BOOLEAN,
                    name VARCHAR(255),
                    address VARCHAR(255),
                    email VARCHAR(255),
                    phone_number VARCHAR(255),
                    pin_code VARCHAR(255),
                    role VARCHAR(20) DEFAULT 'user'

                   )
''')                          # user id ko uuid se generate krege jo ki sbke liye unique hoti hai

    # multiple table create kr rhe hai jisse ek baar function  call krege table create ho jayegi

    # Products table creation
    cursor.execute('''

CREATE TABLE IF NOT EXISTS Products(
                   id INTEGER PRIMARY  KEY AUTOINCREMENT,
                   Product_id VARCHAR(255),
                   name VARCHAR(255),
                   price FLOAT,
                   category VARCHAR(255),
                   stock INTEGER(255)
                   )
''')


    # Order_ Details table creation
    cursor.execute('''
CREATE TABLE IF NOT EXISTS Order_Details(
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   Order_id VARCHAR(255),
                   user_id VARCHAR(255),
                   product_id VARCHAR(255),
                   isApproved BOOLEAN,
                   quantity INTEGER(255),
                   date_of_order_creation DATE,
                   price FLOAT,
                   total_amount FLOAT,
                   product_name VARCHAR(255),
                   user_name VARCHAR(255),
                   message VARCHAR(1000),
                   category VARCHAR(255),
                   sold BOOLEAN
                   )
                   
''')
    


    # Sell_History table creation 
    cursor.execute('''

CREATE TABLE IF NOT EXISTS Sell_History(
                   id INTEGER PRIMARY KEY AUTOINCREMENT, 
                   Sell_id VARCHAR(255),                        
                   product_id VARCHAR(255),
                   Order_id VARCHAR(255),
                   isApproved BOOLEAN,
                   quantity INTEGER(255),
                   Remaining_stock INTEGER(255),
                   date_of_sell DATE,
                   total_amount FLOAT,
                   price FLOAT,
                   product_name VARCHAR(255),
                   user_id VARCHAR(255),
                   user_name VARCHAR(255)
                   )
                   
''')
    
   
    conn.commit()           # it show now table is created 
    conn.close()            #affter creation of table sqlite get closed