from flask import Flask,jsonify,request,render_template
from createTableOperation import createTable
from addOperation import createUser,addProduct,createOrder,record_Sell,addAvailableProduct
from auth_user import authenticate_user
from updateOperation import update_approve_user,add_api_key_column,update_user_details,update_product,update_Order,approve_Order,updateAvailableproduct
from readOperation import getAllUsers,getOrderById,getSpecificUser,getAllProducts,getspecificproduct,getAllOrders,getUserOrders,getSellHistory,getUserSellHistory,getProductSellHistory,get_Available_Products,getAvailableProductByCategory
from deleteOperation import delete_User,delete_Product,delete_Order


# here we are using flask library need to create an instance 

app = Flask(__name__)  
        # flask instance created succesfully 
@app.route('/dox', methods=['GET'])  #ye root ek method on krne ko bol rha hai
def dox():
    return render_template('dox.html')


# need to define route (root 
#   @isinstance.route('/',methods=['GET'])  / -> define root 
@app.route('/')  #ye root ek method on krne ko bol rha hai
def hello_world():
    return "Hello World"


@app.route('/user',methods=['GET'])  #ye root ek method on krne ko bol rha hai
                                 #  '/'-> here single / define the end point and after end point need to define function
                                 # route ko jo bhi output dena hoga us function ko define kr dege 
def hello():                     # yha par method ko define kr rhe hai 
    return jsonify( {'name': 'Saurabh', 'phonenumber':4234242332}  )

@app.route('/addApiKeyColumn', methods=['GET'])
def add_api_key():
    response = add_api_key_column()
    return jsonify(response)






# these routes for create user 

@app.route('/createUser', methods=['POST'])             # requesting information from user
def create_user():
    try:
        name = request.form['name']
        password = request.form['password']
        phoneNumber =  request.form['phoneNumber']
        email = request.form['email']
        pincode = request.form['pincode']
        address = request.form['address']
                                                # after requesting from form passes all the parameter to the function
        response = createUser(name=name,password=password,phoneNumber=phoneNumber,email=email, pincode=pincode, address= address)

        return response
    except Exception as e:
        return jsonify({'message': str(e), "status" : 400})


@app.route('/login', methods = ['POST'])         # taking information from user that's why here post is used 
def login_user():
    try:
        email = request.form['email']           # requesting email from user
        password = request.form['password']     # requesting password from user

        user = authenticate_user(email=email, password=password)                   # for login email and password is necessary  
        if user:
            return jsonify({'status':200 ,'message':  str(user[1])})
        else:
            return jsonify({'status':401,'message': 'Invalid email or password'})
    except Exception as error:
        return jsonify({'message' : str(error), "status" : 400})


@app.route('/getAllUsers', methods = ['GET'])           # GET method is used so that admin fetch all users 
def get_All_Users():
    try:
        users = getAllUsers()  # this will return dictonaries of users 
        return jsonify({'users': users, 'message': "Users fetched Successfully",'status': 200})  # here we are returning the users in json format
    
    except Exception as error:
        return jsonify({'users':[],'message': str(error), 'status': 400})


@app.route('/getSpecificUser',methods=['POST'])           
def get_Specific_User():
    try:
        userId = request.form['user_id']
        user = getSpecificUser(userId= userId)
        return jsonify({'user': user, 'message': "User fetched Successfully", 'status': 200})  # here we are returning the users in json format
    except Exception as error:
        return jsonify({'user': user,'message': str(error)+ " mistacks are there", 'status':400})


@app.route('/approveUser', methods=['PATCH'])
def approve_User():
    try:
        userId = request.form['user_id']                # taking user_id from user
        approve = request.form['isApproved']            # taking isApproved section from user so that changes are made 
        
        approveUser = update_approve_user(userId = userId, approve = approve)

        return jsonify({"message": "User Approved", "status": 200})
    except Exception as error:
        return jsonify({"message":str(error), 'status':400 })


@app.route('/updateUser', methods = ['PATCH'])
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
    


# as retrofit does not accept delete method with parameter 
#  so we are using post method instead of delete method 

@app.route('/deleteUser', methods = ['POST'])
def delete_user():
    try:
        user_id = request.form['user_id']
        delete = delete_User(user_id)
        return jsonify({"message": "User Deleted Successfully", "status": 200})
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})

#prduct add
#product specific 
#product all
#pruduct update


@app.route('/addProduct', methods = ['POST'])
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

@app.route('/getAppProducts', methods = ['GET'])
def get_all_products():
    try: 
        products= getAllProducts()  # function to get all products from database
        return jsonify({'products': products, 'message': "Products fetched Successfully", 'status': 200})  # here we are returning the users in json format
    
    except Exception as error:
        return jsonify({'products':[],"message": str(error), 'status': 400})

@app.route('/getSpecificProduct', methods = ['POST'])
def get_specific_product():
    try:
        Product_id = request.form['Product_id']  # taking product id from user
        product = getspecificproduct(Product_id= Product_id)  # function to get specific product from database
        return jsonify({'product': product, 'message': "Product fetched Successfully", 'status': 200})  # here we are returning the users in json format    
    
    except Exception as error:
        return jsonify({'product':[],"message": str(error), 'status': 400})

@app.route('/updateProduct', methods = ['PATCH'])
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

@app.route('/deleteProduct', methods = ['POST'])
def delete_product():
    try:
        Product_id = request.form['Product_id']  # taking product id from user
        response = delete_Product(Product_id)  # function to delete product from database
        return response
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})



# Order table operation

@app.route('/createOrder', methods=['POST'])
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


@app.route('/getAllOrders', methods=['GET'])
def get_all_orders():
    try:
        orders = getAllOrders()  # function to get all orders from database
        return jsonify({'orders': orders, 'message': "Orders fetched Successfully", 'status': 200})  # here we are returning the users in json format
    
    
    except Exception as error:
        return jsonify({"orders":[],"message": str(error), 'status': 400})
    
@app.route('/getUserOrders', methods=['POST'])
def get_user_orders():
    try:
        user_id = request.form['user_id']  # taking user id from user
        order = getUserOrders(user_id=user_id)  # function to get all orders of a specific user from database
        return jsonify({'order': order, 'message': "Order fetched Successfully", 'status': 200})  # here we are returning the users in json format
    except Exception as error:
        return jsonify({"order":[],"message": str(error), 'status': 400})

@app.route('/getOrderById', methods=['POST'])
def get_order_by_id():
    try:
        Order_id = request.form['Order_id']  # taking order id from user
        order = getOrderById(Order_id=Order_id)  # function to get specific order from database
        return jsonify({'order': order, 'message': "Order fetched Successfully", 'status': 200})  # here we are returning the users in json format
    
    except Exception as error:
        return jsonify({"order":[],"message": str(error), 'status': 400})

@app.route('/updateOrder', methods=['PATCH'])
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


@app.route('/approveOrder', methods=['PATCH'])
def approve_order():
    try:
        Order_id = request.form['Order_id']  # taking order id from user
        isApproved = request.form['isApproved']  # taking isApproved section from user so that changes are made
        response = approve_Order(Order_id=Order_id, isApproved= isApproved)  # function to approve order in database
        return response
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})


@app.route('/deleteOrder', methods=['POST'])
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


# sell history table 
@app.route('/recordSell', methods=['POST'])
def record_sell():
    try:
        Product_id = request.form['Product_id']  # taking product id from user
        quantity = int(request.form['quantity'])  # taking quantity from user   
        user_id = request.form['user_id']  # taking user id from user
        response = record_Sell(Product_id=Product_id, quantity=quantity, user_id=user_id)  # function to record sell in database
        return response
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})


@app.route('/getSellHistory', methods=['GET'])
def get_sell_history():
    try:
        sell_history = getSellHistory()  # function to get all sell history from database
        return jsonify({'sell_history': sell_history, 'message': "Sell History fetched Successfully", 'status': 200})  # here we are returning the users in json format 
    
    except Exception as error:
        return jsonify({"sell_history":[],"message": str(error), 'status': 400})
    
@app.route('/getusersellhistory', methods=['POST'])
def get_user_sell_history():
    try:
        user_id = request.form['user_id']  # taking user id from user
        sell_history = getUserSellHistory(user_id=user_id)  # function to get all sell history of a specific user from database
        return jsonify({'sell_history': sell_history, 'message': "Sell History fetched Successfully", 'status': 200})  # here we are returning the users in json format
    except Exception as error:
        return jsonify({"sell_history":[],"message": str(error), 'status': 400})



@app.route('/getproductsellhistory', methods=['POST'])
def get_product_sell_history():
    try:
        Product_id = request.form['Product_id']  # taking product id from user
        response = getProductSellHistory(Product_id=Product_id)  # function to get all sell history of a specific product from database
        return jsonify({'sell_history': response, 'message': "Sell History fetched Successfully", 'status': 200})
    except Exception as error:
        return jsonify({"sell_history":[],"message": str(error), 'status': 400})


# Available product table operation

@app.route('/addavailableproducts', methods=['POST'])
def add_available_product():
    try:
        Product_id = request.form['Product_id']  # taking product id from user
        Product_name = request.form['Product_name']  # taking product name from user
        category = request.form['category']  # taking category from user
        price = float(request.form['price'])  # taking price from user
        stock = int(request.form['stock'])  # taking stock from user
        user_id = request.form['user_id']  # taking user id from user
        user_name = request.form['user_name']  # taking user name from user

        response = addAvailableProduct(Product_id=Product_id, product_name=Product_name, category=category, price=price, stock=stock,user_id=user_id,user_name=user_name)  # function to add available product in database
        return jsonify({"message": 'Available Products Added Successfully','availableproducts' : response, 'status': 400})
    except Exception as error:
        return jsonify({"message": str(error),'availableproducts' : [], 'status': 400})


@app.route('/getAvailableProducts', methods=['GET'])
def get_available_products():
    try:
        available_product = get_Available_Products()  # function to get all available products from database
        return jsonify({'message': "Available Products fetched Successfully",'available_product': available_product,  'status': 200})  # here we are returning the users in json format
    
    except Exception as error:
        return jsonify({"message": str(error),"available_product":[], 'status': 400})

@app.route('/getavailableproductbycategory', methods=['POST'])
def get_available_product_by_category():
    try:
        category = request.form['category']  # taking category from user
        available_product = getAvailableProductByCategory(category=category)  # function to get all available products of a specific category from database
        return jsonify({'message': "Available Products fetched Successfully",'available_product': available_product,  'status': 200})  # here we are returning the users in json format
    except Exception as error:
        return jsonify({"message": str(error),"available_product":[], 'status': 400})

@app.route('/updateavailableproduct', methods=['PATCH'])
def update_available_product():
    try:
        Product_id = request.form['Product_id']  # taking product id from user
        updateProduct = {}  # list/dictonary to store the key value pair of all the fields
        for key, value in request.form.items():
            if key != 'Product_id':
                updateProduct[key] = value
        response = updateAvailableproduct(Product_id=Product_id, updateProduct=updateProduct)  # function to update available product in database
        return response
    except Exception as error:
        return jsonify({"message": str(error), 'status': 400})


if __name__ == '__main__':

    createTable()

    app.run(debug=True)  


