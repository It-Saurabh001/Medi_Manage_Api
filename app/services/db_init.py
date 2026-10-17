import os
import sqlite3
from werkzeug.security import generate_password_hash

def get_db():
    db_name = os.getenv("DATABASE_NAME", "My_Medical_Shope.db")
    return sqlite3.connect(db_name)

def migrate_passwords():
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, password FROM Users")
            users = cursor.fetchall()

            for user_id, pwd in users:
                if not (pwd.startswith("pbkdf2:") or pwd.startswith("scrypt:")):
                    hashed = generate_password_hash(pwd)
                    cursor.execute("UPDATE Users SET password = ? WHERE id = ?", (hashed, user_id))
    finally:
        conn.close()

def updateTable():
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()
            try:
                cursor.execute("ALTER TABLE Admin ADD COLUMN role VARCHAR(20) DEFAULT 'admin'")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE Admin ADD COLUMN image_url VARCHAR(1000) DEFAULT NULL")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE Users ADD COLUMN image_url VARCHAR(1000) DEFAULT NULL")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE Products ADD COLUMN image_url VARCHAR(1000) DEFAULT NULL")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE Order_Details ADD COLUMN image_url VARCHAR(1000) DEFAULT NULL")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute("ALTER TABLE Sell_History ADD COLUMN image_url VARCHAR(1000) DEFAULT NULL")
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute('''
                    UPDATE Order_Details
                    SET image_url = (
                        SELECT Products.image_url FROM Products WHERE Products.Product_id = Order_Details.product_id
                    )
                    WHERE image_url IS NULL
                ''')
            except sqlite3.OperationalError:
                pass

            try:
                cursor.execute('''
                    UPDATE Sell_History
                    SET image_url = (
                        SELECT Products.image_url FROM Products WHERE Products.Product_id = Sell_History.product_id
                    )
                    WHERE image_url IS NULL
                ''')
            except sqlite3.OperationalError:
                pass
    finally:
        conn.close()

def createTable():
    conn = get_db()
    try:
        with conn:
            cursor = conn.cursor()

            # Admin table
            cursor.execute('''
CREATE TABLE IF NOT EXISTS Admin(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id TEXT UNIQUE,
    password TEXT,
    date_of_account_creation DATE,
    name TEXT,
    email TEXT UNIQUE,
    phone_number TEXT UNIQUE DEFAULT NULL,                    
    role VARCHAR(20) DEFAULT 'admin',
    image_url VARCHAR(1000) DEFAULT NULL
)
''')

            # Users table
            cursor.execute('''
CREATE TABLE IF NOT EXISTS Users(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id VARCHAR(255) UNIQUE,    
    password VARCHAR(255),
    date_of_account_creation DATE,
    isApproved BOOLEAN,
    block BOOLEAN,
    name VARCHAR(255),
    address VARCHAR(255),
    email VARCHAR(255) UNIQUE,
    phone_number VARCHAR(255),
    pin_code VARCHAR(255),
    role VARCHAR(20) DEFAULT 'user',
    image_url VARCHAR(1000) DEFAULT NULL
)
''')

            # Products table
            cursor.execute('''
CREATE TABLE IF NOT EXISTS Products(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    Product_id VARCHAR(255) UNIQUE,
    name VARCHAR(255),
    price FLOAT,
    category VARCHAR(255),
    stock INTEGER,
    image_url VARCHAR(1000) DEFAULT NULL
)
''')

            # Order_Details table
            cursor.execute('''
CREATE TABLE IF NOT EXISTS Order_Details(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    Order_id VARCHAR(255) UNIQUE,
    user_id VARCHAR(255),
    product_id VARCHAR(255),
    isApproved BOOLEAN,
    quantity INTEGER,
    date_of_order_creation DATE,
    price FLOAT,
    total_amount FLOAT,
    product_name VARCHAR(255),
    user_name VARCHAR(255),
    message VARCHAR(1000),
    category VARCHAR(255),
    sold BOOLEAN,
    image_url VARCHAR(1000) DEFAULT NULL
)
''')

            # Sell_History table
            cursor.execute('''
CREATE TABLE IF NOT EXISTS Sell_History(
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    Sell_id VARCHAR(255) UNIQUE,                        
    product_id VARCHAR(255),
    Order_id VARCHAR(255),
    isApproved BOOLEAN,
    quantity INTEGER,
    Remaining_stock INTEGER,
    date_of_sell DATE,
    total_amount FLOAT,
    price FLOAT,
    product_name VARCHAR(255),
    user_id VARCHAR(255),
    user_name VARCHAR(255),
    image_url VARCHAR(1000) DEFAULT NULL
)
''')
    finally:
        conn.close()