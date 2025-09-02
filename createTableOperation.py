import sqlite3



def createTable():                  #function for creation of table 
    
    conn = sqlite3.connect("My_Medical_Shope.db")          # conneting sqlite with database and automatically create  "My_Medical_Shope.db" database
    cursor = conn.cursor()                     # cursor is used to assign operation to database

    
#otp
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
                    pin_code VARCHAR(255)

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
                   category VARCHAR(255)
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