from flask import Flask,jsonify,request,render_template
from createTableOperation import *
from addOperation import *
from auth_user import *
from updateOperation import *
from readOperation import *
from deleteOperation import *
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, create_refresh_token
from role_required import *
from datetime import timedelta
import random,time
from verification import*
from otp_store import *



# here we are using flask library need to create an instance 

app = Flask(__name__)  
        # flask instance created succesfully 

app.config['JWT_SECRET_KEY'] = 'your-secret-key'  # use a strong secret in production
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
jwt = JWTManager(app)





@app.route('/dox', methods=['GET'])  #ye root ek method on krne ko bol rha hai
def dox():
    return render_template('dox.html')


# need to define route (root 
#   @isinstance.route('/',methods=['GET'])  / -> define root 
@app.route('/')  #ye root ek method on krne ko bol rha hai
def hello_world():
    return "Hello World"

@app.route('/admin/refreshToken', methods=['POST'])
@jwt_required(refresh=True)
def refresh_token():
    admin_id = get_jwt_identity()
    
    # Generate a new short-lived access token
    new_access_token = create_access_token(identity=admin_id)
    
    return jsonify({"access_token": new_access_token})


@app.route('/admin/create', methods=['POST'])
def create_admin():
    try:
        email = request.form['email']
        name = request.form['name']
        password = request.form['password']
        phoneNumber =  request.form['phoneNumber']
        role = "admin"
        response = createAdmin(email=email, name=name, password=password,phoneNumber=phoneNumber, role=role)
        return response
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})


@app.route('/admin/login', methods = ['POST'])         # taking information from user that's why here post is used 
def login_Admin():
    try:
        email = request.form['email']           # requesting email from user
        password = request.form['password']     # requesting password from user
        auth_result = authenticate_admin(email=email, password=password)                   # for login email and password is necessary  
        if auth_result:
            admin_id, role = auth_result
            # generate otp
            otp = random.randint(100000, 999999)
            expiry = time.time() + 300  # 5 minutes expiry
            otp_store[admin_id] = {"otp": otp, "expiry": expiry}

            # Send OTP via email (use your send_email or send_otp_email function)
            send_otp_email(to_email=email, otp=otp)  # or send_otp_email(email, otp)
            
            return jsonify({'status':200, 'admin_id': admin_id, 'role': role, 'message': 'OTP sent to your email'})
        else:
            return jsonify({'status':401,'message': 'Invalid email or password'})
    except Exception as error:
        return jsonify({'message' : str(error), "status" : 400})
    

@app.route('/admin/verifyOtp', methods=['POST'])
def verify_admin_otp():
    try:
        admin_id = request.form['admin_id']
        otp = request.form['otp']
        if admin_id not in otp_store:
            return jsonify({'status' : 400, 'message': 'No OTP request found '})
        stored_otp = otp_store[admin_id]['otp']
        expiry = otp_store[admin_id]['expiry']

        if time.time() > expiry:
            del otp_store[admin_id]
            return jsonify({'status' : 400, 'message': 'OTP expired'})
        
        if int(otp) == stored_otp:
            # OTP correct → create JWT
            # You can store role from your database lookup or pass it along
            _,role = authenticate_admin_by_id(admin_id)
            access_token = create_access_token(identity=admin_id,additional_claims={"role": role})
            refresh_token = create_refresh_token(identity=admin_id)
            
            #remove otp from store
            del otp_store[admin_id]
            return jsonify({'status' : 200, 'access_token': access_token, 'refresh_token': refresh_token, 'role':role})
        else:
            return jsonify({'status' : 400, 'message': 'Invalid OTP'})
    except Exception as error:
        return jsonify({'status' : 400, 'message': str(error)})

@app.route('/admin/getAllAdmins', methods = ['GET'])           # GET method is used so that admin fetch all users 
@role_required(["admin"])   # only admin can access
def get_All_Admins():
    try:
        admins = getAllAdmins()  # this will return dictonaries of users 
        return jsonify({'admins': admins, 'message': "Admins fetched Successfully",'status': 200})  # here we are returning the users in json format
    
    except Exception as error:
        return jsonify({'admins':[],'message': str(error), 'status': 400})

# these routes for create user 

@app.route('/user/create', methods=['POST'])             # requesting information from user
def create_user():
    try:
        name = request.form['name']
        password = request.form['password']
        phoneNumber =  request.form['phoneNumber']
        email = request.form['email']
        pincode = request.form['pincode']
        address = request.form['address']
        # request header for role
        role = "user" # default
        if request.headers.get("Admin") == "admin":
            role = "admin"
                                                # after requesting from form passes all the parameter to the function
        response = createUser(name=name,password=password,phoneNumber=phoneNumber,email=email, pincode=pincode, address= address, role = role)

        return response
    except Exception as e:
        return jsonify({'message': str(e), "status" : 400})

@app.route('/user/requestUserPasswordReset', methods=['POST'])
def request_user_password_reset():
    try:
        email = request.form['email']
        response = request_user_pswd_reset(email)
        return response
    except Exception as error:
        return jsonify({'status': 400, 'message': str(error)})
    
@app.route('/user/resetUserPasswordWithOtp', methods=['POST'])
def reset_user_password_with_otp():
    try:
        user_id = request.form['user_id']
        otp = request.form['otp']
        new_password = request.form['new_password']
        response = reset_password_with_otp(user_id, otp, new_password)
        return response
    except Exception as error:
        return jsonify({'status': 400, 'message': str(error)})

@app.route('/admin/requestAdminPasswordReset', methods=['POST'])
def request_admin_password_reset():
    try:
        email = request.form['email']
        response = request_admin_pswd_reset(email)
        return response
    except Exception as error:
        return jsonify({'status': 400, 'admin_id':None,'message': str(error)})
    
@app.route('/admin/resetAdminPasswordWithOtp', methods=['POST'])
def reset_admin_password_with_otp():
    try:
        admin_id = request.form['admin_id']
        otp = request.form['otp']
        new_password = request.form['new_password']
        response = reset_admin_pswd_with_otp(admin_id, otp, new_password)
        return response
    except Exception as error:
        return jsonify({'status': 400, 'message': str(error)})

@app.route('/user/login', methods=['POST'])
def login_user():
    try:
        email = request.form['email']
        password = request.form['password']
        auth_result = authenticate_user(email=email, password=password)
        if auth_result:
            user_id, role = auth_result
            otp = random.randint(100000, 999999)
            expiry = time.time() + 300  # 5 minutes expiry
            user_otp_store[user_id] = {"otp": otp, "expiry": expiry}
            send_otp_email(to_email=email, otp=otp)
            return jsonify({ 'user_id': user_id, 'role': role, 'message': 'OTP sent to your email','status': 200})
        else:
            return jsonify({'user_id': None, 'message': 'Invalid email or password','status': 401})
    except Exception as error:
        return jsonify({'user_id': None,'message': str(error), "status": 400})
    
@app.route('/user/verifyUserOtp', methods=['POST'])
def verify_user_otp():
    try:
        user_id = request.form['user_id']
        otp = request.form['otp']
        if user_id not in user_otp_store:
            return jsonify({'status': 400, 'message': 'No OTP request found'})
        stored_otp = user_otp_store[user_id]['otp']
        expiry = user_otp_store[user_id]['expiry']

        if time.time() > expiry:
            del user_otp_store[user_id]
            return jsonify({'status': 400, 'message': 'OTP expired'})

        if int(otp) == stored_otp:
            # OTP correct → create JWT
            # Get role from DB if needed
            _, role = authenticate_user_by_id(user_id)
            access_token = create_access_token(identity=user_id, additional_claims={"role": role})
            refresh_token = create_refresh_token(identity=user_id)
            del user_otp_store[user_id]
            return jsonify({'status': 200, 'access_token': access_token, 'refresh_token': refresh_token, 'role': role})
        else:
            return jsonify({'status': 400, 'message': 'Invalid OTP'})
    except Exception as error:
        return jsonify({'status': 400, 'message': str(error)})

@app.route('/admin/getAllUsers', methods = ['GET'])           # GET method is used so that admin fetch all users 
@role_required(["admin"])   # only admin can access
def get_All_Users():
    try:
        users = getAllUsers()  # this will return dictonaries of users 
        return jsonify({'users': users, 'message': "Users fetched Successfully",'status': 200})  # here we are returning the users in json format
    
    except Exception as error:
        return jsonify({'users':[],'message': str(error), 'status': 400})




@app.route('/admin/user/getSpecificUser',methods=['POST'])  
@role_required(["admin", "user"])
def get_Specific_User():
    try:
        userId = request.form['user_id']
        user = getSpecificUser(userId= userId)
        return jsonify({'user': user, 'message': "User fetched Successfully", 'status': 200})  # here we are returning the users in json format
    except Exception as error:
        return jsonify({'user': user,'message': str(error)+ " mistacks are there", 'status':400})


@app.route('/admin/approveUser', methods=['PATCH'])
@role_required(["admin"])
def approve_User():
    try:
        userId = request.form['user_id']                # taking user_id from user
        approve = request.form['isApproved']            # taking isApproved section from user so that changes are made 
        
        approveUser = update_approve_user(userId = userId, approve = approve)

        return jsonify({"message": "User Approved", "status": 200})
    except Exception as error:
        return jsonify({"message":str(error), 'status':400 })


@app.route('/admin/updateUser', methods = ['PATCH'])
@role_required(["admin", "user"])
def update_user():
    try:
        user_id =  request.form['user_id']              # this function will run on user side and some accessability provided to admin 
        updateUser = {}        # list/dictonary to store the key value pair of all the fields 
        for key, value in request.form.items():             # requesting all the  section of the form so that changes are made where required 
            if key != 'user_id':
                updateUser[key] = value
        
        count = update_user_details(user_id,updateUser)
        return jsonify({"message": "User Updated Successfully", "status": 200})
    except Exception as error:
        return jsonify({'message': str(error),'status' : 400})
    

@app.route('/admin/update', methods = ['PATCH'])
@role_required(["admin"])
def update_admin():
    try:
        admin_id =  request.form['admin_id']              # this function will run on admin side
        updateAdmin = {}        # list/dictonary to store the key value pair of all the fields 
        for key, value in request.form.items():             # requesting all the  section of the form so that changes are made where required 
            if key != 'user_id':
                updateAdmin[key] = value
        
        count = update_admin_details(admin_id,updateAdmin)
        return jsonify({"message": "Admin Updated Successfully", "status": 200})
    except Exception as error:
        return jsonify({'message': str(error),'status' : 400})
    


# as retrofit does not accept delete method with parameter 
#  so we are using post method instead of delete method 

@app.route('/admin/deleteUser', methods = ['POST'])
@role_required(["admin"])
def delete_user():
    try:
        user_id = request.form['user_id']
        delete = delete_User(user_id)
        return jsonify({"message": "User Deleted Successfully", "status": 200})
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})
    

@app.route('/admin/delete', methods = ['POST'])
@role_required(["admin"])
def delete_admin():
    try:
        admin_id = request.form['admin_id']
        delete = delete_Admin(admin_id)
        return jsonify({"message": "Admin Deleted Successfully", "status": 200})
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})
    

#prduct add
#product specific 
#product all
#pruduct update


@app.route('/admin/addProduct', methods = ['POST'])
@role_required(["admin"])
def add_product():
    try:
        name = request.form['name']
        price = float(request.form['price'])
        category = request.form['category']
        stock = int(request.form['stock'])

        response = addProduct(name=name, price=price, category=category, stock=stock)  # function to add product in database
        return response
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})

#admin & user
@app.route('/admin/user/getAllProducts', methods = ['GET'])
@role_required(["admin", "user"])
def get_all_products():
    try: 
        products= getAllProducts()  # function to get all products from database
        return jsonify({'products': products, 'message': "Products fetched Successfully", 'status': 200})  # here we are returning the users in json format
    
    except Exception as error:
        return jsonify({'products':[],"message": str(error), 'status': 400})

#user & admin
@app.route('/admin/user/getSpecificProduct', methods = ['POST'])
@role_required(["admin", "user"])
def get_specific_product():
    try:
        Product_id = request.form['Product_id']  # taking product id from user
        product = getspecificproduct(Product_id= Product_id)  # function to get specific product from database
        return jsonify({'product': product, 'message': "Product fetched Successfully", 'status': 200})  # here we are returning the users in json format    
    
    except Exception as error:
        return jsonify({'product':[],"message": str(error), 'status': 400})
#admin
@app.route('/admin/updateProduct', methods = ['PATCH'])    # isme mai hi available product manage krna hai no need of new product table
@role_required(["admin"])
def update__product():
    try:
        Product_id = request.form['Product_id']  # taking product id from use 
        updateProduct = {}  # list/dictonary to store the key value pair of all the fields
        for key , value in request.form.items():
            if key != 'Product_id':
                updateProduct[key] = value
        response = update_product(Product_id= Product_id, updateProduct= updateProduct)  # function to update product in database
        return response     
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})
#admin
@app.route('/admin/deleteProduct', methods = ['POST'])
@role_required(["admin"])
def delete_product():
    try:
        Product_id = request.form['Product_id']  # taking product id from user
        response = delete_Product(Product_id)  # function to delete product from database
        return response
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})



# Order table operation
#user
@app.route('/user/createOrder', methods=['POST'])
@role_required(["admin", "user"])
def create_order():
    try:
        user_id = request.form['user_id']
        Product_id = request.form['Product_id']
        quantity = int(request.form['quantity'])
        message = request.form.get('message', '')  # optional message field

        response = createOrder(user_id=user_id, Product_id=Product_id, quantity=quantity, message=message)  # function to create order in database
        return response
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})  

#admin
@app.route('/admin/getAllOrders', methods=['GET'])
@role_required(["admin"])
def get_all_orders():
    try:
        orders = getAllOrders()  # function to get all orders from database
        return jsonify({'orders': orders, 'message': "Orders fetched Successfully", 'status': 200})  # here we are returning the users in json format
    
    
    except Exception as error:
        return jsonify({"orders":[],"message": str(error), 'status': 400})
#admin & user
@app.route('/admin/user/getOrdersByUserId', methods=['POST'])
@role_required(["admin", "user"])
def get_user_orders():
    try:
        user_id = request.form['user_id']  # taking user id from user
        order = getUserOrders(user_id=user_id)  # function to get all orders of a specific user from database
        return jsonify({'order': order, 'message': "Order fetched Successfully", 'status': 200})  # here we are returning the users in json format
    except Exception as error:
        return jsonify({"order":[],"message": str(error), 'status': 400})
#admin & user
@app.route('/admin/user/orderById', methods=['POST'])
@role_required(["admin", "user"])
def get_order_by_id():
    try:
        Order_id = request.form['Order_id']  # taking order id from user
        order = getOrderById(Order_id=Order_id)  # function to get specific order from database
        return jsonify({'order': order, 'message': "Order fetched Successfully", 'status': 200})  # here we are returning the users in json format
    
    except Exception as error:
        return jsonify({"order":[],"message": str(error), 'status': 400})
#admin
@app.route('/admin/updateOrder', methods=['PATCH'])
@role_required(["admin"])
def update_order():
    try:
        Order_id = request.form['Order_id']  # taking order id from user
        updateOrder = {}  # list/dictonary to store the key value pair of all the fields
        for key, value in request.form.items():
            if key != 'Order_id':
                updateOrder[key] = value
        response = update_Order(Order_id=Order_id, updateOrder=updateOrder)  # function to update order in database
        return response
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})

#admin  but 
@app.route('/admin/approveOrder', methods=['PATCH'])
@role_required(["admin"])
def approve_order():
    try:
        Order_id = request.form['Order_id']  # taking order id from user
        isApproved = request.form['isApproved']  # taking isApproved section from user so that changes are made
        if (isApproved == "true"):
            isApproved = 1
        elif isApproved == "false":
            isApproved = 0
        response = approve_Order(Order_id=Order_id, isApproved= isApproved)  # function to approve order in database
        return response
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})


@app.route('/admin/deleteOrder', methods=['POST'])
@role_required(["admin"])
def delete_order():
    try:
        Order_id = request.form['Order_id']  # taking order id from user
        response = delete_Order(Order_id)  # function to delete order from database
        return response
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})

# columns  for available stocks 
# user id
# user Name
# product id 
# product name 
# category 
# price 
# stock 

#call this route as soon as order placed
# sell history table creation admin
@app.route('/admin/recordSell', methods=['POST'])
@role_required(["admin"])
def record_sell():
    try:
        Order_id = request.form.get('Order_id')

        response = record_Sell(Order_id=Order_id)  # function to record sell in database
        return response
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})

# admin
@app.route('/admin/getSellHistory', methods=['GET'])
@role_required(["admin"])
def get_sell_history():
    try:
        sell_history = getSellHistory()  # function to get all sell history from database
        return jsonify({'sell_history': sell_history, 'message': "Sell History fetched Successfully", 'status': 200})  # here we are returning the users in json format 
    
    except Exception as error:
        return jsonify({"sell_history":[],"message": str(error), 'status': 400})
    #user & #admin
@app.route('/admin/user/getSellHistoryByUserId', methods=['POST'])
@role_required(["admin", "user"])
def get_user_sell_history():
    try:
        user_id = request.form['user_id']  # taking user id from user
        sell_history = getUserSellHistory(user_id=user_id)  # function to get all sell history of a specific user from database
        return jsonify({'sell_history': sell_history, 'message': "Sell History fetched Successfully", 'status': 200})  # here we are returning the users in json format
    except Exception as error:
        return jsonify({"sell_history":[],"message": str(error), 'status': 400})

#update no

@app.route('/admin/getproductsellhistory', methods=['POST'])
@role_required(["admin", "user"])
def get_product_sell_history():
    try:
        Product_id = request.form['Product_id']  # taking product id from user
        response = getProductSellHistory(Product_id=Product_id)  # function to get all sell history of a specific product from database
        return jsonify({'sell_history': response, 'message': "Sell History fetched Successfully", 'status': 200})
    except Exception as error:
        return jsonify({"sell_history":[],"message": str(error), 'status': 400})


#updateStock route

@app.route('/admin/deleteSellHistory', methods=['POST'])
@role_required(["admin"])
def delete_sell_history():
    try:
        Sell_id = request.form['Sell_id']  # taking sell id from user
        response = delete_SellHistory(Sell_id)  # function to delete sell history from database
        return response

    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})



if __name__ == '__main__':

    # updateTable()
    createTable()
    # migrate_passwords()

    # app.run( debug=True)
    app.run( host="0.0.0.0",port=5000,debug=True)


