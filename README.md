# Medi_Manage_Api

A RESTful API for medical shop management, built with Python Flask and SQLite. This project provides endpoints for managing users, products, orders, available stock, and sales history, supporting both admin and user roles.

---

## Table of Contents

- [Project Overview](#project-overview)
- [Architecture](#architecture)
- [Features](#features)
- [API Endpoints](#api-endpoints)
- [Database Schema](#database-schema)
- [Modules & Code Structure](#modules--code-structure)
- [Technologies Used](#technologies-used)
- [Getting Started](#getting-started)
- [Error Handling](#error-handling)
- [Contributing](#contributing)
- [License](#license)

---

## Project Overview

Medi_Manage_Api is designed to manage the operations of a medical shop, including user registration, product management, order processing, inventory management, and sales tracking. The backend exposes a set of RESTful endpoints for CRUD operations on users, products, and orders, with role-based access and approval flows.

---

## Architecture

- **Backend Framework:** Python Flask for REST API development.
- **Database:** SQLite for lightweight, file-based storage.
- **Templates:** HTML templates for basic documentation or simple UI endpoints.
- **Code Organization:** Modular Python files for operations (create, update, read, delete, authentication).

**Design Highlights:**
- Layered architecture separating routing, business logic, and database operations.
- Use of UUID as unique identifiers for users and admins.
- Try-catch blocks for robust error handling.
- Modularized endpoints for scalability and maintainability.

---

## Features

### User Management
- User signup and login
- Fetching single or all users
- Approve, update, and delete users
- Unique API key generation for users (column added via `/addApiKeyColumn`)

### Product Management
- Add, fetch, update, and delete products
- Fetch specific product by ID

### Order Management
- Create orders
- Fetch all orders or specific orders by user or ID
- Approve, update, and delete orders

### Inventory & Sales
- Manage available products and their categories
- Record and fetch sales history (by user, product, or total)

---

## API Endpoints

> **Note:** All endpoints use JSON for request/response unless otherwise specified.

### User Endpoints
- `POST /createUser` - Register a new user
- `POST /login` - User authentication
- `GET /getAllUsers` - Fetch all users (admin)
- `POST /getSpecificUser` - Fetch a single user by ID
- `PATCH /approveUser` - Approve a user (admin)
- `PATCH /updateUser` - Update user details
- `POST /deleteUser` - Delete a user

### Product Endpoints
- `POST /addProduct` - Add a new product
- `GET /getAppProducts` - Fetch all products
- `POST /getSpecificProduct` - Fetch product by ID
- `PATCH /updateProduct` - Update product details
- `POST /deleteProduct` - Delete a product

### Order Endpoints
- `POST /createOrder` - Create a new order
- `GET /getAllOrders` - Fetch all orders
- `POST /getUserOrders` - Fetch orders for a user
- `POST /getOrderById` - Fetch order by ID
- `PATCH /approveOrder` - Approve an order
- `PATCH /updateOrder` - Update order details
- `POST /deleteOrder` - Delete an order

### Sales & Inventory
- `POST /recordSell` - Record a product sale
- `GET /getSellHistory` - Fetch all sales history
- `POST /getusersellhistory` - Fetch sales history for a user
- `POST /getproductsellhistory` - Fetch sales history for a product

### Utility
- `GET /addApiKeyColumn` - Add API key column to users table (one-time setup)
- `GET /dox` - Simple HTML documentation endpoint

---

## Database Schema

**Main Tables:**
- `Users`: Stores user information, approval status, API key
- `Products`: Stores product details
- `Orders`: Stores order details, links to users and products
- `SellHistory`: Tracks sales by user and product

**Operations:**
- All database operations use a cursor for transaction management.
- Commit and close connections after each operation to ensure data integrity.

---

## Modules & Code Structure

- `main.py`: Flask app with all route definitions.
- `createTableOperation.py`: Functions to create and update database tables.
- `addOperation.py`: Functions to add users, products, orders, and sales.
- `updateOperation.py`: Functions to update user/product/order details, approval, and API key column.
- `readOperation.py`: Functions to fetch users, products, orders, and sales data.
- `deleteOperation.py`: Functions to delete users, products, and orders.
- `templates/`: Contains simple HTML templates for documentation or UI (`dox.html`).

---

## Technologies Used

- **Python**: Core language.
- **Flask**: For web server and API routes.
- **SQLite**: Database for persistent storage.
- **HTML**: For minimal documentation template.

---

## Getting Started

1. **Clone the repository:**
   ```bash
   git clone https://github.com/It-Saurabh001/Medi_Manage_Api.git
   cd Medi_Manage_Api
   ```

2. **Install dependencies:**
   ```bash
   pip install flask
   ```

3. **Run the app:**
   ```bash
   python main.py
   ```
   - The server will run in debug mode on localhost.

4. **Setup Database:**
   - On first run, tables are created automatically.
   - To add the API key column to users, visit `/addApiKeyColumn` endpoint once.

---

## Error Handling

- All endpoints use try-except blocks to handle exceptions.
- Errors are returned as JSON with an appropriate message and status code.
- Database connections are properly closed after each transaction to avoid locks.

---

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for review.

---

## License

[MIT License](LICENSE)

---

## Acknowledgements

- Inspired by practical medical shop management needs.
- Designed for modularity and extensibility.

---

**Contact:**  
For queries or issues, please open an [issue](https://github.com/It-Saurabh001/Medi_Manage_Api/issues) or contact the repository owner.
