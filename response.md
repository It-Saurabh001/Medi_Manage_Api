# API Response Reference

## 1. Overview and Global Conventions

- **Base URL & Port:** `http://localhost:5000` (development server runs on port 5000 via `scripts/dev/run_dev.ps1` or `python -m flask --app wsgi run --port 5000`).
- **Authentication:**
  - Token issuance: JWTs generated via `flask_jwt_extended` using HMAC-SHA256.
  - Header format: Standard HTTP bearer format: `Authorization: Bearer <token>`.
  - Token types:
    - **Access Token:** Short-lived (1 hour: `JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)`), required for protected operations.
    - **Refresh Token:** Long-lived (30 days: `JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)`), used exclusively at `/admin/refreshToken`.
  - Identity & Claims: Token identity holds `admin_id` or `user_id`. Claims dictionary contains `{"role": "admin"}` or `{"role": "user"}` verified by `@role_required`.
- **Request Content Types:**
  - Form Fields: `application/x-www-form-urlencoded` or `multipart/form-data` accessed via `request.form`.
  - File Uploads: `multipart/form-data` accessed via `request.files` (`image` part for Cloudinary uploads).
- **Response Envelope Structure:**
  - Every API endpoint returns a JSON payload containing at minimum:
    - `status` (integer): HTTP status code (e.g. 200, 201, 400, 401, 403, 404, 500).
    - `message` (string): Human-readable operational description or error details.
  - Success responses embed entity payload keys (e.g., `admins`, `users`, `products`, `product`, `orders`, `order`, `sell_history`, `access_token`, etc.).

---

## 2. Global Error Responses

Global exceptions and JWT authentication failures return standard JSON envelopes handled by `app/errors.py` and `flask_jwt_extended`:

| HTTP Status                   | Trigger Condition                                                            | JSON Body Example                                            |
| :---------------------------- | :--------------------------------------------------------------------------- | :----------------------------------------------------------- |
| **400 Bad Request**           | Missing mandatory request parameters or type parsing failure                 | `{"status": 400, "message": "Bad Request"}`                  |
| **401 Unauthorized**          | Missing `Authorization` header, invalid token, or expired JWT                | `{"status": 401, "message": "Missing Authorization Header"}` |
| **403 Forbidden**             | Authenticated user lacks required role (e.g., non-admin calling admin route) | `{"status": 403, "message": "Access Forbidden"}`             |
| **404 Not Found**             | Unregistered endpoint URL or requested resource ID does not exist            | `{"status": 404, "message": "Resource Not Found"}`           |
| **405 Method Not Allowed**    | Incorrect HTTP verb used for registered route (e.g. GET instead of POST)     | `{"status": 405, "message": "Method Not Allowed"}`           |
| **422 Unprocessable Entity**  | Malformed JWT payload or header structure failure                            | `{"status": 422, "message": "Unprocessable Entity"}`         |
| **500 Internal Server Error** | Uncaught backend exception (in production mode)                              | `{"status": 500, "message": "Internal Server Error"}`        |

---

## 3. Endpoint Index

| #   | Method  | URL                                  | Auth            | Role   | Kotlin App                          |
| :-- | :------ | :----------------------------------- | :-------------- | :----- | :---------------------------------- |
| 1   | `GET`   | `/health`                            | None            | Public | Not used                            |
| 2   | `GET`   | `/`                                  | None            | Public | Not used                            |
| 3   | `GET`   | `/dox`                               | None            | Public | Not used                            |
| 4   | `POST`  | `/admin/refreshToken`                | Refresh Token   | Admin  | `admin/refreshToken`                |
| 5   | `POST`  | `/admin/login`                       | None            | Public | `admin/login`                       |
| 6   | `POST`  | `/admin/verifyOtp`                   | None            | Public | `admin/verifyOtp`                   |
| 7   | `POST`  | `/admin/requestAdminPasswordReset`   | None            | Public | `admin/requestAdminPasswordReset`   |
| 8   | `POST`  | `/admin/resetAdminPasswordWithOtp`   | None            | Public | `admin/resetAdminPasswordWithOtp`   |
| 9   | `POST`  | `/user/create`                       | Optional Header | Public | Not used                            |
| 10  | `POST`  | `/user/login`                        | None            | Public | Not used                            |
| 11  | `POST`  | `/user/verifyUserOtp`                | None            | Public | Not used                            |
| 12  | `POST`  | `/user/requestUserPasswordReset`     | None            | Public | Not used                            |
| 13  | `POST`  | `/user/resetUserPasswordWithOtp`     | None            | Public | Not used                            |
| 14  | `POST`  | `/admin/create`                      | Access Token    | Admin  | `admin/create`                      |
| 15  | `GET`   | `/admin/getAllAdmins`                | Access Token    | Admin  | `admin/getAllAdmins`                |
| 16  | `GET`   | `/admin/getAllUsers`                 | Access Token    | Admin  | `admin/getAllUsers`                 |
| 17  | `POST`  | `/admin/user/getSpecificUser`        | Access Token    | Both   | `admin/user/getSpecificUser`        |
| 18  | `PATCH` | `/admin/approveUser`                 | Access Token    | Admin  | `admin/approveUser`                 |
| 19  | `PATCH` | `/admin/updateUser`                  | Access Token    | Both   | `admin/updateUser`                  |
| 20  | `PATCH` | `/admin/update`                      | Access Token    | Admin  | `admin/update`                      |
| 21  | `POST`  | `/admin/deleteUser`                  | Access Token    | Admin  | `admin/deleteUser`                  |
| 22  | `POST`  | `/admin/delete`                      | Access Token    | Admin  | `admin/delete`                      |
| 23  | `POST`  | `/admin/addProduct`                  | Access Token    | Admin  | `admin/addProduct`                  |
| 24  | `GET`   | `/admin/user/getAllProducts`         | Access Token    | Both   | `admin/user/getAllProducts`         |
| 25  | `POST`  | `/admin/user/getSpecificProduct`     | Access Token    | Both   | `admin/user/getSpecificProduct`     |
| 26  | `PATCH` | `/admin/updateProduct`               | Access Token    | Admin  | `admin/updateProduct`               |
| 27  | `POST`  | `/admin/deleteProduct`               | Access Token    | Admin  | `admin/deleteProduct`               |
| 28  | `POST`  | `/user/createOrder`                  | Access Token    | Both   | Not used                            |
| 29  | `GET`   | `/admin/getAllOrders`                | Access Token    | Admin  | `admin/getAllOrders`                |
| 30  | `POST`  | `/admin/user/getOrdersByUserId`      | Access Token    | Both   | `admin/user/getOrdersByUserId`      |
| 31  | `POST`  | `/admin/user/orderById`              | Access Token    | Both   | `admin/user/orderById`              |
| 32  | `PATCH` | `/admin/updateOrder`                 | Access Token    | Admin  | `admin/updateOrder`                 |
| 33  | `PATCH` | `/admin/approveOrder`                | Access Token    | Admin  | `admin/approveOrder`                |
| 34  | `POST`  | `/admin/deleteOrder`                 | Access Token    | Admin  | `admin/deleteOrder`                 |
| 35  | `POST`  | `/admin/recordSell`                  | Access Token    | Admin  | `admin/recordSell`                  |
| 36  | `GET`   | `/admin/getSellHistory`              | Access Token    | Admin  | `admin/getSellHistory`              |
| 37  | `POST`  | `/admin/user/getSellHistoryByUserId` | Access Token    | Both   | `admin/user/getSellHistoryByUserId` |
| 38  | `POST`  | `/admin/getproductsellhistory`       | Access Token    | Both   | `admin/getproductsellhistory`       |
| 39  | `POST`  | `/admin/deleteSellHistory`           | Access Token    | Admin  | `admin/deleteSellHistory`           |

---

## 4. Endpoint Details

### 1. GET /health : Health Check

- **Auth:** none. **Role:** public
- **Request:** No body or parameters.
- **Success response:** HTTP 200
  ```json
  {
    "status": "healthy",
    "service": "Medi_Manage_Api"
  }
  ```
  _Note: Returns service availability indicator._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 500 | Application crash | `{"status": 500, "message": "Internal Server Error"}` |
- **Side effects:** none
- **Source:** `app/routes/health.py` : `health`
- **Kotlin app:** not used

### 2. GET / : Root Greeting

- **Auth:** none. **Role:** public
- **Request:** No body or parameters.
- **Success response:** HTTP 200 (Text)
  ```text
  Hello World
  ```
- **Error responses:** None.
- **Side effects:** none
- **Source:** `app/routes/user.py` : `hello_world`
- **Kotlin app:** not used

### 3. GET /dox : API Documentation UI

- **Auth:** none. **Role:** public
- **Request:** No body or parameters.
- **Success response:** HTTP 200 (HTML document rendering `app/templates/dox.html`).
- **Error responses:** None.
- **Side effects:** none
- **Source:** `app/routes/user.py` : `dox`
- **Kotlin app:** not used

### 4. POST /admin/refreshToken : Refresh Admin JWT Token

- **Auth:** refresh token. **Role:** admin
- **Request:** `application/json` or headers only.
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <refresh_token>` |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Token refreshed successfully",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "role": "admin"
  }
  ```
  _Note: `access_token` and `refresh_token` are non-null strings; `role` is string._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 401 | Missing, malformed, or expired refresh token | `{"message": "Token has expired", "status": 401}` |
- **Side effects:** none
- **Source:** `app/routes/auth.py` : `refresh_token`
- **Kotlin app:** used (`admin/refreshToken`)

### 5. POST /admin/login : Admin Login & Request OTP

- **Auth:** none. **Role:** public
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `email` | String | Yes | Registered admin email address |
  | `password` | String | Yes | Raw plaintext password |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "OTP sent to your email",
    "admin_id": "AID1a2b3c4d",
    "role": "admin"
  }
  ```
  _Note: OTP is generated and dispatched to `email` via SMTP; not returned in response._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 401 | Email not found or password incorrect | `{"status": 401, "message": "Invalid email or password"}` |
  | 400 | Missing `email` or `password` in form payload | `{"status": 400, "message": "'email'"}` |
- **Side effects:** Stores 6-digit OTP in memory/Redis with 300s TTL; sends transactional email via configured SMTP provider.
- **Source:** `app/routes/auth.py` : `login_Admin`
- **Kotlin app:** used (`admin/login`)

### 6. POST /admin/verifyOtp : Verify Admin OTP & Issue Tokens

- **Auth:** none. **Role:** public
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `admin_id` | String | Yes | Admin identifier returned by `/admin/login` |
  | `otp` | String | Yes | 6-digit OTP code received via email |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "OTP verified successfully",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "role": "admin"
  }
  ```
  _Note: Returns active JWT access and refresh token pair._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | No OTP found for `admin_id` | `{"status": 400, "message": "No OTP request found "}` |
  | 400 | OTP code timestamp exceeded 300s TTL | `{"status": 400, "message": "OTP expired"}` |
  | 400 | Submitted OTP code does not match stored OTP | `{"status": 400, "message": "Invalid OTP"}` |
  | 400 | Missing `admin_id` or `otp` field | `{"status": 400, "message": "'admin_id'"}` |
- **Side effects:** Consumes and removes stored OTP key from memory/Redis store.
- **Source:** `app/routes/auth.py` : `verify_admin_otp`
- **Kotlin app:** used (`admin/verifyOtp`)

### 7. POST /admin/requestAdminPasswordReset : Request Admin Password Reset

- **Auth:** none. **Role:** public
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `email` | String | Yes | Admin email address to receive reset code |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "OTP 123456 sent to your email",
    "user_id": "AID1a2b3c4d"
  }
  ```
  _Note: `user_id` contains the `admin_id` of the matching admin account._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 404 | Email is not registered in Admin table | `{"status": 404, "message": "Email not registered"}` |
  | 500 | SMTP delivery failure | `{"status": 500, "user_id": "AID1a2b3c4d", "message": "Failed to send OTP email (check SMTP server)."}` |
  | 400 | Missing `email` form parameter | `{"status": 400, "admin_id": null, "message": "'email'"}` |
- **Side effects:** Stores OTP with 300s TTL; sends email to admin via SMTP provider.
- **Source:** `app/routes/auth.py` : `request_admin_password_reset`
- **Kotlin app:** used (`admin/requestAdminPasswordReset`)

### 8. POST /admin/resetAdminPasswordWithOtp : Reset Admin Password With OTP

- **Auth:** none. **Role:** public
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `admin_id` | String | Yes | Admin identifier |
  | `otp` | String | Yes | 6-digit OTP code received via email |
  | `new_password`| String | Yes | New raw password to set |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Password reset successful"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | No OTP found or expired | `{"status": 400, "message": "No OTP request found or OTP expired"}` |
  | 400 | OTP code timestamp exceeded 300s TTL | `{"status": 400, "message": "OTP expired"}` |
  | 400 | Incorrect OTP code | `{"status": 400, "message": "Invalid OTP"}` |
  | 400 | Missing form parameters | `{"status": 400, "message": "'admin_id'"}` |
- **Side effects:** Hashes `new_password` with Werkzeug and updates `Admin.password` in SQLite; deletes OTP from store.
- **Source:** `app/routes/auth.py` : `reset_admin_password_with_otp`
- **Kotlin app:** used (`admin/resetAdminPasswordWithOtp`)

### 9. POST /user/create : User Registration

- **Auth:** none (optional header `Admin: admin` grants admin role). **Role:** public
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Admin` | Header | No | Optional; if value equals `"admin"`, creates account with admin role |
  | `name` | String | Yes | Full name of the user |
  | `password` | String | Yes | Raw plaintext password |
  | `email` | String | Conditional | Required if `phoneNumber` is not provided |
  | `phoneNumber`| String | Conditional | Required if `email` is not provided |
  | `address` | String | No | Residential address |
  | `pincode` | String | No | Postal code / PIN code |
  | `image` | File (Binary) | No | Optional user profile picture uploaded to Cloudinary (`MediAdminApp/Users`) |
  | `image_url` | String | No | Optional direct image URL string fallback |
- **Success response:** HTTP 201
  ```json
  {
    "status": 201,
    "message": "User created with role user and user id = $UID1a2b3c4d "
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing `name` or `password` | `{"status": 400, "message": "Name and Password are mandatory"}` |
  | 400 | Both `email` and `phoneNumber` are missing | `{"status": 400, "message": "Please provide either Email or Phone Number"}` |
  | 409 | Email already exists in Users table | `{"status": 409, "message": "Email already registered"}` |
  | 409 | Phone number already exists in Users table | `{"status": 409, "message": "Phone number already registered"}` |
  | 400 | General database error | `{"status": 400, "message": "<error>"}` |
- **Side effects:** Uploads profile image to Cloudinary (if provided); hashes password with Werkzeug; inserts new row into `Users` table with `isApproved=False`, `block=False`, and `image_url`.
- **Source:** `app/routes/user.py` : `create_user`
- **Kotlin app:** not used

### 10. POST /user/login : User Login & Request OTP

- **Auth:** none. **Role:** public
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `email` | String | Yes | Registered user email address |
  | `password` | String | Yes | Raw plaintext password |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "OTP 123456 sent to your email",
    "user_id": "UID1a2b3c4d",
    "role": "user"
  }
  ```
  _Note: OTP is generated and dispatched to `email` via SMTP._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 401 | Email not registered or incorrect password | `{"status": 401, "user_id": null, "message": "Invalid email or password"}` |
  | 400 | Missing `email` or `password` in form | `{"status": 400, "user_id": null, "message": "'email'"}` |
- **Side effects:** Stores OTP with 300s TTL; sends transactional email via SMTP provider.
- **Source:** `app/routes/auth.py` : `login_user`
- **Kotlin app:** not used

### 11. POST /user/verifyUserOtp : Verify User OTP & Issue Tokens

- **Auth:** none. **Role:** public
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `user_id` | String | Yes | User identifier returned from `/user/login` |
  | `otp` | String | Yes | 6-digit OTP code received via email |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "OTP Verified Successfully",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "role": "user"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | No OTP found for `user_id` | `{"status": 400, "message": "No OTP request found"}` |
  | 400 | OTP code timestamp exceeded 300s TTL | `{"status": 400, "message": "OTP expired"}` |
  | 400 | Incorrect OTP code | `{"status": 400, "message": "Invalid OTP", "access_token": null, "refresh_token": null, "role": "user"}` |
  | 400 | Missing `user_id` or `otp` field | `{"status": 400, "message": "'user_id'", "access_token": null, "refresh_token": null, "role": "user"}` |
- **Side effects:** Deletes OTP from store; generates JWT access and refresh tokens.
- **Source:** `app/routes/auth.py` : `verify_user_otp`
- **Kotlin app:** not used

### 12. POST /user/requestUserPasswordReset : Request User Password Reset

- **Auth:** none. **Role:** public
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `email` | String | Yes | User email address |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "OTP 123456 sent to your email",
    "user_id": "UID1a2b3c4d"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 404 | Email not registered in Users table | `{"status": 404, "message": "Email not registered"}` |
  | 500 | SMTP delivery failure | `{"status": 500, "user_id": "UID1a2b3c4d", "message": "Failed to send OTP email (check SMTP server)."}` |
  | 400 | Missing `email` form parameter | `{"status": 400, "message": "'email'"}` |
- **Side effects:** Stores OTP with 300s TTL; sends reset email.
- **Source:** `app/routes/auth.py` : `request_user_password_reset`
- **Kotlin app:** not used

### 13. POST /user/resetUserPasswordWithOtp : Reset User Password With OTP

- **Auth:** none. **Role:** public
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `user_id` | String | Yes | User identifier |
  | `otp` | String | Yes | 6-digit OTP code received via email |
  | `new_password`| String | Yes | New raw password to set |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Password reset successful"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | No OTP found or expired | `{"status": 400, "message": "No OTP request found or OTP expired"}` |
  | 400 | OTP code timestamp exceeded 300s TTL | `{"status": 400, "message": "OTP expired"}` |
  | 400 | Incorrect OTP code | `{"status": 400, "message": "Invalid OTP"}` |
  | 400 | Missing form parameters | `{"status": 400, "message": "'user_id'"}` |
- **Side effects:** Hashes `new_password` and updates `Users.password` in SQLite; deletes OTP from store.
- **Source:** `app/routes/auth.py` : `reset_user_password_with_otp`
- **Kotlin app:** not used

### 14. POST /admin/create : Create Admin Account

- **Auth:** access token. **Role:** admin
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` (role must be `admin`) |
  | `email` | String | Yes | Admin email address |
  | `name` | String | Yes | Full name |
  | `password` | String | Yes | Raw plaintext password |
  | `phoneNumber`| String | Yes | Contact phone number |
  | `image` | File (Binary) | No | Optional admin profile picture uploaded to Cloudinary (`MediAdminApp/Admins`) |
  | `image_url` | String | No | Optional direct image URL string fallback |
- **Success response:** HTTP 201
  ```json
  {
    "status": 201,
    "message": "Admin created with role admin and admin id = $AID1a2b3c4d "
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 409 | Email already exists in Admin table | `{"status": 409, "message": "Email already registered"}` |
  | 400 | Missing form parameters | `{"status": 400, "message": "'email'"}` |
  | 401 | Missing or invalid access token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Caller role is not admin | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Uploads profile image to Cloudinary (if provided); hashes password; inserts new record into `Admin` table with `role='admin'` and `image_url`.
- **Source:** `app/routes/admin.py` : `create_admin`
- **Kotlin app:** used (`admin/create`)

### 15. GET /admin/getAllAdmins : Get All Admin Accounts

- **Auth:** access token. **Role:** admin
- **Request:** Headers only.
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Admins fetched Successfully",
    "admins": [
      {
        "id": 1,
        "admin_id": "AID1a2b3c4d",
        "date_of_account_creation": "2026-10-03",
        "name": "Jane Admin",
        "email": "admin@example.com",
        "phone_number": "1234567890",
        "role": "admin",
        "image_url": null
      }
    ]
  }
  ```
  _Note: `phone_number` can be null or string; passwords are never returned._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Query execution error | `{"status": 400, "admins": [], "message": "<error>"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** none
- **Source:** `app/routes/admin.py` : `get_All_Admins`
- **Kotlin app:** used (`admin/getAllAdmins`)

### 16. GET /admin/getAllUsers : Get All Registered Users

- **Auth:** access token. **Role:** admin
- **Request:** Headers only.
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Users fetched Successfully",
    "users": [
      {
        "id": 1,
        "user_id": "UID1a2b3c4d",
        "date_of_account_creation": "2026-10-03",
        "isApproved": true,
        "block": false,
        "name": "John Customer",
        "address": "456 Elm St",
        "email": "customer@example.com",
        "phone_number": "9876543210",
        "pin_code": "10001",
        "role": "user",
        "image_url": null
      }
    ]
  }
  ```
  _Note: `isApproved` and `block` are boolean; `address`, `email`, `phone_number`, `pin_code` may be null; passwords are never returned._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Query execution error | `{"status": 400, "users": [], "message": "<error>"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** none
- **Source:** `app/routes/admin.py` : `get_All_Users`
- **Kotlin app:** used (`admin/getAllUsers`)

### 17. POST /admin/user/getSpecificUser : Get Specific User Details

- **Auth:** access token. **Role:** both (`admin`, `user`)
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `user_id` | String | Yes | Unique ID of user to retrieve |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "User fetched Successfully",
    "user": {
      "id": 1,
      "user_id": "UID1a2b3c4d",
      "date_of_account_creation": "2026-10-03",
      "isApproved": 1,
      "block": 0,
      "name": "John Customer",
      "address": "456 Elm St",
      "email": "customer@example.com",
      "phone_number": "9876543210",
      "pin_code": "10001",
      "role": "user",
      "image_url": null
    }
  }
  ```
  _Note: `isApproved` and `block` are returned as raw DB values (0/1 or boolean); `address`, `email`, `phone_number`, `pin_code` may be null; `password` is excluded._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 404 | User ID not found | `{"status": 404, "user": null, "message": "User not found"}` |
  | 400 | Missing `user_id` parameter or DB error | `{"status": 400, "user": null, "message": "'user_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Forbidden | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** none
- **Source:** `app/routes/user.py` : `get_specific_user`
- **Kotlin app:** used (`admin/user/getSpecificUser`)

### 18. PATCH /admin/approveUser : Update User Approval Status

- **Auth:** access token. **Role:** admin
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `user_id` | String | Yes | Target user identifier |
  | `isApproved` | String / Int / Bool | Yes | Approval flag (`"true"`, `"false"`, `1`, `0`) |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "User Approved"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing form parameters | `{"status": 400, "message": "'user_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Updates `Users.isApproved` in SQLite database.
- **Source:** `app/routes/admin.py` : `approve_User`
- **Kotlin app:** used (`admin/approveUser`)

### 19. PATCH /admin/updateUser : Update User Profile Details

- **Auth:** access token. **Role:** both (`admin`, `user`)
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `user_id` | String | Yes | Target user identifier |
  | `name` | String | No | Updated full name |
  | `address` | String | No | Updated residential address |
  | `phone_number` | String | No | Updated contact number |
  | `pin_code` | String | No | Updated PIN code |
  | `image` | File (Binary) | No | Optional replacement profile image uploaded to Cloudinary (`MediAdminApp/Users`) |
  | `image_url` | String | No | Updated profile picture / avatar URL string fallback |
  | `password` | String | No | New raw password (automatically hashed) |
  | `isApproved` | String / Int | No | Admin-only editable field |
  | `block` | String / Int | No | Admin-only editable field |
  | `role` | String | No | Admin-only editable field |
  | `date_of_account_creation` | String | No | Admin-only editable field |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "User Updated Successfully"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing `user_id` or DB error | `{"status": 400, "message": "'user_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Forbidden | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Uploads new profile picture to Cloudinary (if provided); hashes password if provided; updates `Users` columns (including `image_url`). Privilege escalation protection prevents non-admins from modifying `role`, `isApproved`, or `block`, while allowing `image` file and `image_url` alongside standard profile fields.
- **Source:** `app/routes/admin.py` : `update_user`
- **Kotlin app:** used (`admin/updateUser`)

### 20. PATCH /admin/update : Update Admin Details

- **Auth:** access token. **Role:** admin
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `admin_id` | String | Yes | Target admin identifier |
  | `name` | String | No | Updated full name |
  | `password` | String | No | New raw password (automatically hashed) |
  | `email` | String | No | Updated email address |
  | `phone_number` | String | No | Updated phone number |
  | `image` | File (Binary) | No | Optional replacement admin image uploaded to Cloudinary (`MediAdminApp/Admins`) |
  | `image_url` | String | No | Updated admin profile picture / avatar URL string fallback |
  | `date_of_account_creation` | String | No | Creation date override |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Admin Updated Successfully"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing `admin_id` or DB error | `{"status": 400, "message": "'admin_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Uploads new admin image to Cloudinary (if provided); hashes password if provided; updates `Admin` table in SQLite (including `image_url`).
- **Source:** `app/routes/admin.py` : `update_admin`
- **Kotlin app:** used (`admin/update`)

### 21. POST /admin/deleteUser : Delete User Account

- **Auth:** access token. **Role:** admin
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `user_id` | String | Yes | Target user ID to delete |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "User Deleted Successfully"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing `user_id` or DB error | `{"status": 400, "message": "'user_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Deletes user record from `Users` table.
- **Source:** `app/routes/admin.py` : `delete_user`
- **Kotlin app:** used (`admin/deleteUser`)

### 22. POST /admin/delete : Delete Admin Account

- **Auth:** access token. **Role:** admin
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `admin_id` | String | Yes | Target admin ID to delete |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Admin Deleted Successfully"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing `admin_id` or DB error | `{"status": 400, "message": "'admin_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Deletes admin record from `Admin` table.
- **Source:** `app/routes/admin.py` : `delete_admin`
- **Kotlin app:** used (`admin/delete`)

### 23. POST /admin/addProduct : Add New Product with Image

- **Auth:** access token. **Role:** admin
- **Request:** `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `name` | String | Yes | Product trade name |
  | `price` | Float | Yes | Unit selling price (e.g. `12.50`) |
  | `category` | String | Yes | Product classification category |
  | `stock` | Integer | Yes | Initial inventory count (e.g. `50`) |
  | `image` | File (Binary) | No | Optional image file uploaded to Cloudinary |
- **Success response:** HTTP 201
  ```json
  {
    "status": 201,
    "message": "PROD_1a2b3c4d"
  }
  ```
  _Note: `message` contains the newly generated `Product_id` string._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing parameters or invalid numeric format | `{"status": 400, "message": "'name'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Uploads image to Cloudinary (if provided); inserts new record into `Products` table.
- **Source:** `app/routes/product.py` : `add_product`
- **Kotlin app:** used (`admin/addProduct`)

### 24. GET /admin/user/getAllProducts : Get All Products

- **Auth:** access token. **Role:** both (`admin`, `user`)
- **Request:** Headers only.
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Products fetched Successfully",
    "products": [
      {
        "id": 1,
        "Product_id": "PROD_1a2b3c4d",
        "name": "Paracetamol 500mg",
        "price": 5.99,
        "category": "Pain Relief",
        "stock": 100,
        "image_url": "https://res.cloudinary.com/demo/image/upload/v1/sample.jpg"
      }
    ]
  }
  ```
  _Note: `Product_id` uses PascalCase; `image_url` is null if no image was uploaded._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Query execution error | `{"status": 400, "products": [], "message": "<error>"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Forbidden | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** none
- **Source:** `app/routes/product.py` : `get_all_products`
- **Kotlin app:** used (`admin/user/getAllProducts`)

### 25. POST /admin/user/getSpecificProduct : Get Specific Product Details

- **Auth:** access token. **Role:** both (`admin`, `user`)
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `Product_id` | String | Yes | Unique product identifier (PascalCase parameter) |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Product fetched Successfully",
    "product": {
      "id": 1,
      "Product_id": "PROD_1a2b3c4d",
      "name": "Paracetamol 500mg",
      "price": 5.99,
      "category": "Pain Relief",
      "stock": 100,
      "image_url": "https://res.cloudinary.com/demo/image/upload/v1/sample.jpg"
    }
  }
  ```
  _Note: `Product_id` uses PascalCase; `image_url` is null if no image was uploaded._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 404 | Product not found | `{"status": 404, "product": null, "message": "Product not found"}` |
  | 400 | Missing `Product_id` or query error | `{"status": 400, "product": [], "message": "'Product_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Forbidden | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** none
- **Source:** `app/routes/product.py` : `get_specific_product`
- **Kotlin app:** used (`admin/user/getSpecificProduct`)

### 26. PATCH /admin/updateProduct : Update Product Details & Image

- **Auth:** access token. **Role:** admin
- **Request:** `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `Product_id` | String | Yes | Target product identifier |
  | `name` | String | No | Updated product name |
  | `price` | Float | No | Updated unit price |
  | `category` | String | No | Updated classification category |
  | `stock` | Integer | No | Updated inventory count |
  | `image` | File (Binary) | No | Replacement product image uploaded to Cloudinary (`MediAdminApp/Products`) |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Product updated successfully"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing `Product_id` or DB error | `{"status": 400, "message": "'Product_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Uploads new image to Cloudinary (if provided); updates matching `Products` row in SQLite.
- **Source:** `app/routes/product.py` : `update__product`
- **Kotlin app:** used (`admin/updateProduct`)

### 27. POST /admin/deleteProduct : Delete Product

- **Auth:** access token. **Role:** admin
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `Product_id` | String | Yes | Target product identifier to delete |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Product deleted successfully"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing `Product_id` or DB error | `{"status": 400, "message": "'Product_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Deletes record from `Products` table.
- **Source:** `app/routes/product.py` : `delete_product`
- **Kotlin app:** used (`admin/deleteProduct`)

### 28. POST /user/createOrder : Create Order

- **Auth:** access token. **Role:** both (`admin`, `user`)
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `user_id` | String | Yes | Ordering user identifier |
  | `Product_id` | String | Yes | Target product identifier |
  | `quantity` | Integer | Yes | Number of units |
  | `message` | String | No | Custom note or prescription instructions (default: `""`) |
- **Success response:** HTTP 201
  ```json
  {
    "status": 201,
    "message": "ORD1a2b3c4d"
  }
  ```
  _Note: `message` contains the newly created `Order_id`._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 404 | Product not found in database | `{"status": 404, "message": "Product not found"}` |
  | 404 | User not found in database | `{"status": 404, "message": "User not found"}` |
  | 400 | Missing parameters or integer parse failure | `{"status": 400, "message": "'user_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Forbidden | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Inserts new record into `Order_Details` table with `isApproved=0`, `sold=0`, `total_amount=price * quantity`, automatically snapshotting and persisting `image_url` from `Products`.
- **Source:** `app/routes/order.py` : `create_order`
- **Kotlin app:** not used

### 29. GET /admin/getAllOrders : Get All Orders

- **Auth:** access token. **Role:** admin
- **Request:** Headers only.
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Orders fetched Successfully",
    "orders": [
      {
        "id": 1,
        "order_id": "ORD1a2b3c4d",
        "user_id": "UID1a2b3c4d",
        "product_id": "PROD_1a2b3c4d",
        "isApproved": false,
        "quantity": 2,
        "date_of_order_creation": "2026-10-03",
        "price": 5.99,
        "total_amount": 11.98,
        "product_name": "Paracetamol 500mg",
        "user_name": "John Customer",
        "message": "Please deliver in afternoon",
        "category": "Pain Relief",
        "sold": false,
        "image_url": "https://res.cloudinary.com/daphwrye8/image/upload/sample.jpg"
      }
    ]
  }
  ```
  _Note: Order items contain lowercase `order_id` and `product_id` keys; `isApproved` and `sold` are booleans._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Query execution error | `{"status": 400, "orders": [], "message": "<error>"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** none
- **Source:** `app/routes/order.py` : `get_all_orders`
- **Kotlin app:** used (`admin/getAllOrders`)

### 30. POST /admin/user/getOrdersByUserId : Get Orders by User ID

- **Auth:** access token. **Role:** both (`admin`, `user`)
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `user_id` | String | Yes | Target user identifier |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Order fetched Successfully",
    "order": [
      {
        "id": 1,
        "order_id": "ORD1a2b3c4d",
        "user_id": "UID1a2b3c4d",
        "product_id": "PROD_1a2b3c4d",
        "isApproved": false,
        "quantity": 2,
        "date_of_order_creation": "2026-10-03",
        "price": 5.99,
        "total_amount": 11.98,
        "product_name": "Paracetamol 500mg",
        "user_name": "John Customer",
        "message": "Please deliver in afternoon",
        "category": "Pain Relief",
        "sold": false,
        "image_url": "https://res.cloudinary.com/daphwrye8/image/upload/sample.jpg"
      }
    ]
  }
  ```
  _Note: Root JSON key is singular `"order"`, containing an array of order records._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Query execution error | `{"status": 400, "order": [], "message": "<error>"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Forbidden | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** none
- **Source:** `app/routes/order.py` : `get_user_orders`
- **Kotlin app:** used (`admin/user/getOrdersByUserId`)

### 31. POST /admin/user/orderById : Get Order by Order ID

- **Auth:** access token. **Role:** both (`admin`, `user`)
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `Order_id` | String | Yes | Unique order identifier (PascalCase parameter) |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Order fetched Successfully",
    "order": {
      "id": 1,
      "order_id": "ORD1a2b3c4d",
      "user_id": "UID1a2b3c4d",
      "product_id": "PROD_1a2b3c4d",
      "isApproved": false,
      "quantity": 2,
      "date_of_order_creation": "2026-10-03",
      "price": 5.99,
      "total_amount": 11.98,
      "product_name": "Paracetamol 500mg",
      "user_name": "John Customer",
      "message": "Please deliver in afternoon",
      "category": "Pain Relief",
      "sold": false,
      "image_url": "https://res.cloudinary.com/daphwrye8/image/upload/sample.jpg"
    }
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 404 | Order not found | `{"status": 404, "order": null, "message": "Order not found"}` |
  | 400 | Missing `Order_id` or query error | `{"status": 400, "order": [], "message": "'Order_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Forbidden | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** none
- **Source:** `app/routes/order.py` : `get_order_by_id`
- **Kotlin app:** used (`admin/user/orderById`)

### 32. PATCH /admin/updateOrder : Update Order Details

- **Auth:** access token. **Role:** admin
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `Order_id` | String | Yes | Target order identifier |
  | `quantity` | Integer | No | Updated quantity |
  | `price` | Float | No | Updated unit price |
  | `total_amount` | Float | No | Updated total amount |
  | `product_name` | String | No | Updated product name |
  | `message` | String | No | Updated order message |
  | `isApproved` | Integer / Bool | No | Updated approval status |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Order updated successfully"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing `Order_id` or DB error | `{"status": 400, "message": "'Order_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Updates fields in `Order_Details` table.
- **Source:** `app/routes/order.py` : `update_order`
- **Kotlin app:** used (`admin/updateOrder`)

### 33. PATCH /admin/approveOrder : Approve or Reject Order

- **Auth:** access token. **Role:** admin
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `Order_id` | String | Yes | Target order identifier |
  | `isApproved` | String / Integer | Yes | Approval state (`"true"`/`1` to approve, `"false"`/`0` to reject) |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Order updated successfully"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing form parameters or DB error | `{"status": 400, "message": "'Order_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Converts `"true"`/`"false"` to `1`/`0` and updates `Order_Details.isApproved` in SQLite.
- **Source:** `app/routes/order.py` : `approve_order`
- **Kotlin app:** used (`admin/approveOrder`)

### 34. POST /admin/deleteOrder : Delete Order

- **Auth:** access token. **Role:** admin
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `Order_id` | String | Yes | Target order identifier to delete |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Order deleted successfully"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing `Order_id` or DB error | `{"status": 400, "message": "'Order_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Deletes record from `Order_Details` table.
- **Source:** `app/routes/order.py` : `delete_order`
- **Kotlin app:** used (`admin/deleteOrder`)

### 35. POST /admin/recordSell : Record Product Sale from Order

- **Auth:** access token. **Role:** admin
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `Order_id` | String | Yes | Order identifier for which sale is being fulfilled |
- **Success response:** HTTP 201 (or HTTP 200 if already recorded)
  ```json
  {
    "status": 201,
    "message": "SELL1a2b3c4d"
  }
  ```
  _(Alternative if duplicate: `{"status": 200, "message": "Sell record already exists for this order"}`)_
  _Note: `message` contains the newly generated `Sell_id` string on initial creation._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 404 | Order not found | `{"status": 404, "message": "Order not found"}` |
  | 404 | Associated product not found | `{"status": 404, "message": "Product not found"}` |
  | 400 | Order has not been approved (`isApproved=0`) | `{"status": 400, "message": "Order not approved by admin"}` |
  | 400 | Product inventory `stock < quantity` | `{"status": 400, "message": "Not enough stock available"}` |
  | 400 | Missing `Order_id` parameter or DB error | `{"status": 400, "message": "<error>"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Deducts `quantity` from `Products.stock`; inserts new sale row into `Sell_History` table carrying forward `image_url` from order/product.
- **Source:** `app/routes/admin.py` : `record_sell`
- **Kotlin app:** used (`admin/recordSell`)

### 36. GET /admin/getSellHistory : Get Complete Sales History

- **Auth:** access token. **Role:** admin
- **Request:** Headers only.
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Sell History fetched Successfully",
    "sell_history": [
      {
        "id": 1,
        "Sell_id": "SELL1a2b3c4d",
        "product_id": "PROD_1a2b3c4d",
        "Order_id": "ORD1a2b3c4d",
        "isApproved": true,
        "quantity": 2,
        "remaining_stock": 98,
        "date_of_sell": "2026-10-03",
        "price": 5.99,
        "total_amount": 11.98,
        "product_name": "Paracetamol 500mg",
        "user_id": "UID1a2b3c4d",
        "user_name": "John Customer",
        "image_url": "https://res.cloudinary.com/daphwrye8/image/upload/sample.jpg"
      }
    ]
  }
  ```
  _Note: Key names include PascalCase `Sell_id` and `Order_id`, lowercase `product_id`, `remaining_stock` (lowercase 'r'), and `isApproved` as boolean._
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Query execution error | `{"status": 400, "sell_history": [], "message": "<error>"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** none
- **Source:** `app/routes/admin.py` : `get_sell_history`
- **Kotlin app:** used (`admin/getSellHistory`)

### 37. POST /admin/user/getSellHistoryByUserId : Get Sales History by User ID

- **Auth:** access token. **Role:** both (`admin`, `user`)
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `user_id` | String | Yes | Target user identifier |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Sell History fetched Successfully",
    "sell_history": [
      {i[6,]
        "id": 1,
        "Sell_id": "SELL1a2b3c4d",
        "product_id": "PROD_1a2b3c4d",
        "Order_id": "ORD1a2b3c4d",
        "isApproved": true,
        "quantity": 2,
        "remaining_stock": 98,
        "date_of_sell": "2026-10-03",
        "price": 5.99,
        "total_amount": 11.98,
        "product_name": "Paracetamol 500mg",
        "user_id": "UID1a2b3c4d",
        "user_name": "John Customer",
        "image_url": "https://res.cloudinary.com/daphwrye8/image/upload/sample.jpg"
      }
    ]
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Query execution error | `{"status": 400, "sell_history": [], "message": "<error>"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Forbidden | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** none
- **Source:** `app/routes/admin.py` : `get_user_sell_history`
- **Kotlin app:** used (`admin/user/getSellHistoryByUserId`)

### 38. POST /admin/getproductsellhistory : Get Sales History by Product ID

- **Auth:** access token. **Role:** both (`admin`, `user`)
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `Product_id` | String | Yes | Target product identifier (PascalCase parameter) |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Sell History fetched Successfully",
    "sell_history": [
      {
        "id": 1,
        "Sell_id": "SELL1a2b3c4d",
        "product_id": "PROD_1a2b3c4d",
        "Order_id": "ORD1a2b3c4d",
        "isApproved": true,
        "quantity": 2,
        "remaining_stock": 98,
        "date_of_sell": "2026-10-03",
        "price": 5.99,
        "total_amount": 11.98,
        "product_name": "Paracetamol 500mg",
        "user_id": "UID1a2b3c4d",
        "user_name": "John Customer",
        "image_url": "https://res.cloudinary.com/daphwrye8/image/upload/sample.jpg"
      }
    ]
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Query execution error | `{"status": 400, "sell_history": [], "message": "<error>"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Forbidden | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** none
- **Source:** `app/routes/admin.py` : `get_product_sell_history`
- **Kotlin app:** used (`admin/getproductsellhistory`)

### 39. POST /admin/deleteSellHistory : Delete Sales History Entry

- **Auth:** access token. **Role:** admin
- **Request:** `application/x-www-form-urlencoded` or `multipart/form-data`
  | Field | Type | Required | Notes |
  | :--- | :--- | :--- | :--- |
  | `Authorization` | Header | Yes | Format: `Bearer <access_token>` |
  | `Sell_id` | String | Yes | Target sale identifier to delete (PascalCase parameter) |
- **Success response:** HTTP 200
  ```json
  {
    "status": 200,
    "message": "Deleted successfully"
  }
  ```
- **Error responses:**
  | HTTP Status | Condition | Body |
  | :--- | :--- | :--- |
  | 400 | Missing `Sell_id` or DB error | `{"status": 400, "message": "'Sell_id'"}` |
  | 401 | Missing or invalid token | `{"status": 401, "message": "Missing Authorization Header"}` |
  | 403 | Non-admin caller | `{"status": 403, "message": "Access Forbidden"}` |
- **Side effects:** Deletes record from `Sell_History` table.
- **Source:** `app/routes/admin.py` : `delete_sell_history`
- **Kotlin app:** used (`admin/deleteSellHistory`)

---

## 5. Kotlin Integration Notes

### A. Nullability and Data Type Contract (30 Consumed Endpoints)

| Endpoint                            | Key                                 | JSON Type      | Nullable? | Notes for Kotlin / Retrofit DTO                      |
| :---------------------------------- | :---------------------------------- | :------------- | :-------- | :--------------------------------------------------- |
| `admin/refreshToken`                | `access_token`                      | String         | No        | Non-null JWT bearer string                           |
| `admin/refreshToken`                | `refresh_token`                     | String         | No        | Non-null JWT refresh string                          |
| `admin/refreshToken`                | `role`                              | String         | No        | `"admin"`                                            |
| `admin/login`                       | `admin_id`                          | String         | No        | Format: `"AID..."`                                   |
| `admin/login`                       | `role`                              | String         | No        | `"admin"`                                            |
| `admin/verifyOtp`                   | `access_token`                      | String         | No        | Active JWT access token                              |
| `admin/verifyOtp`                   | `refresh_token`                     | String         | No        | Active JWT refresh token                             |
| `admin/verifyOtp`                   | `role`                              | String         | No        | `"admin"`                                            |
| `admin/requestAdminPasswordReset`   | `user_id`                           | String         | No        | Holds target `admin_id`                              |
| `admin/getAllAdmins`                | `admins[].id`                       | Int            | No        | Primary key ID                                       |
| `admin/getAllAdmins`                | `admins[].admin_id`                 | String         | No        | Unique admin ID                                      |
| `admin/getAllAdmins`                | `admins[].date_of_account_creation` | String         | No        | Format: `"YYYY-MM-DD"`                               |
| `admin/getAllAdmins`                | `admins[].name`                     | String         | No        | Full name                                            |
| `admin/getAllAdmins`                | `admins[].email`                    | String         | No        | Email address                                        |
| `admin/getAllAdmins`                | `admins[].phone_number`             | String         | **Yes**   | `null` if not provided during creation               |
| `admin/getAllAdmins`                | `admins[].role`                     | String         | No        | Default `"admin"`                                    |
| `admin/getAllAdmins`                | `admins[].image_url`                | String         | **Yes**   | Profile picture URL, `null` if none                  |
| `admin/getAllUsers`                 | `users[].id`                        | Int            | No        | Primary key ID                                       |
| `admin/getAllUsers`                 | `users[].user_id`                   | String         | No        | Unique user ID                                       |
| `admin/getAllUsers`                 | `users[].date_of_account_creation`  | String         | No        | Format: `"YYYY-MM-DD"`                               |
| `admin/getAllUsers`                 | `users[].isApproved`                | Boolean        | No        | Explicit boolean (`true`/`false`)                    |
| `admin/getAllUsers`                 | `users[].block`                     | Boolean        | No        | Explicit boolean (`true`/`false`)                    |
| `admin/getAllUsers`                 | `users[].name`                      | String         | No        | Full name                                            |
| `admin/getAllUsers`                 | `users[].address`                   | String         | **Yes**   | `null` if omitted                                    |
| `admin/getAllUsers`                 | `users[].email`                     | String         | **Yes**   | `null` if user registered with phone                 |
| `admin/getAllUsers`                 | `users[].phone_number`              | String         | **Yes**   | `null` if user registered with email                 |
| `admin/getAllUsers`                 | `users[].pin_code`                  | String         | **Yes**   | `null` if omitted                                    |
| `admin/getAllUsers`                 | `users[].role`                      | String         | No        | `"user"` or `"admin"`                                |
| `admin/getAllUsers`                 | `users[].image_url`                 | String         | **Yes**   | Profile picture URL, `null` if none                  |
| `admin/user/getSpecificUser`        | `user`                              | UserDto        | **Yes**   | `null` on 404 Not Found (contains `image_url`)       |
| `admin/user/getAllProducts`         | `products[].id`                     | Int            | No        | Primary key ID                                       |
| `admin/user/getAllProducts`         | `products[].Product_id`             | String         | No        | **PascalCase** key in JSON                           |
| `admin/user/getAllProducts`         | `products[].name`                   | String         | No        | Trade name                                           |
| `admin/user/getAllProducts`         | `products[].price`                  | Double         | No        | Unit price                                           |
| `admin/user/getAllProducts`         | `products[].category`               | String         | No        | Category name                                        |
| `admin/user/getAllProducts`         | `products[].stock`                  | Int            | No        | Available units                                      |
| `admin/user/getAllProducts`         | `products[].image_url`              | String         | **Yes**   | `null` if product has no Cloudinary image            |
| `admin/user/getSpecificProduct`     | `product`                           | ProductDto     | **Yes**   | `null` on 404 Not Found                              |
| `admin/getAllOrders`                | `orders[].id`                       | Int            | No        | Primary key ID                                       |
| `admin/getAllOrders`                | `orders[].order_id`                 | String         | No        | **Lowercase** snake_case key                         |
| `admin/getAllOrders`                | `orders[].user_id`                  | String         | No        | User ID                                              |
| `admin/getAllOrders`                | `orders[].product_id`               | String         | No        | **Lowercase** snake_case key                         |
| `admin/getAllOrders`                | `orders[].isApproved`               | Boolean        | No        | Boolean approval flag                                |
| `admin/getAllOrders`                | `orders[].quantity`                 | Int            | No        | Order quantity                                       |
| `admin/getAllOrders`                | `orders[].date_of_order_creation`   | String         | No        | Format: `"YYYY-MM-DD"`                               |
| `admin/getAllOrders`                | `orders[].price`                    | Double         | No        | Unit price at purchase                               |
| `admin/getAllOrders`                | `orders[].total_amount`             | Double         | No        | `price * quantity`                                   |
| `admin/getAllOrders`                | `orders[].product_name`             | String         | No        | Product title                                        |
| `admin/getAllOrders`                | `orders[].user_name`                | String         | No        | Customer name                                        |
| `admin/getAllOrders`                | `orders[].message`                  | String         | No        | Prescription notes (empty string if none)            |
| `admin/getAllOrders`                | `orders[].category`                 | String         | No        | Category                                             |
| `admin/getAllOrders`                | `orders[].sold`                     | Boolean        | No        | Fulfillment indicator                                |
| `admin/getAllOrders`                | `orders[].image_url`                | String         | **Yes**   | Cloudinary URL bound by `product_id`, `null` if none |
| `admin/user/getOrdersByUserId`      | `order`                             | List<OrderDto> | No        | **Note singular key name `"order"` for list**        |
| `admin/user/orderById`              | `order`                             | OrderDto       | **Yes**   | `null` on 404 Not Found (contains `image_url`)       |
| `admin/getSellHistory`              | `sell_history[].id`                 | Int            | No        | Primary key ID                                       |
| `admin/getSellHistory`              | `sell_history[].Sell_id`            | String         | No        | **PascalCase** key (`"SELL..."`)                     |
| `admin/getSellHistory`              | `sell_history[].product_id`         | String         | No        | **Lowercase** key (`"PROD_..."`)                     |
| `admin/getSellHistory`              | `sell_history[].Order_id`           | String         | No        | **PascalCase** key (`"ORD..."`)                      |
| `admin/getSellHistory`              | `sell_history[].isApproved`         | Boolean        | No        | Boolean approval flag                                |
| `admin/getSellHistory`              | `sell_history[].quantity`           | Int            | No        | Quantity sold                                        |
| `admin/getSellHistory`              | `sell_history[].remaining_stock`    | Int            | No        | **Lowercase 'r'** key                                |
| `admin/getSellHistory`              | `sell_history[].date_of_sell`       | String         | No        | Format: `"YYYY-MM-DD"`                               |
| `admin/getSellHistory`              | `sell_history[].price`              | Double         | No        | Unit price                                           |
| `admin/getSellHistory`              | `sell_history[].total_amount`       | Double         | No        | Total transaction revenue                            |
| `admin/getSellHistory`              | `sell_history[].product_name`       | String         | No        | Product title                                        |
| `admin/getSellHistory`              | `sell_history[].user_id`            | String         | No        | Customer ID                                          |
| `admin/getSellHistory`              | `sell_history[].user_name`          | String         | No        | Customer name                                        |
| `admin/getSellHistory`              | `sell_history[].image_url`          | String         | **Yes**   | Cloudinary URL bound by `product_id`, `null` if none |
| `admin/user/getSellHistoryByUserId` | `sell_history`                      | List<SellDto>  | No        | Same shape as `admin/getSellHistory`                 |
| `admin/getproductsellhistory`       | `sell_history`                      | List<SellDto>  | No        | Same shape as `admin/getSellHistory`                 |

---

### B. Inconsistent Response Key Names Across Endpoints

1. **Plural Collections vs. Singular Exception:**
   - Most collections use plural nouns: `admins`, `users`, `products`, `orders`, `sell_history`.
   - **Critical Exception:** `POST /admin/user/getOrdersByUserId` returns key `"order"` containing a `List<OrderDto>`. Kotlin DTO must use:
     ```kotlin
     data class UserOrdersResponse(
         val status: Int,
         val message: String,
         @SerializedName("order") val orders: List<OrderDto> = emptyList()
     )
     ```
2. **Single Entity Keys:**
   - Single item responses use singular nouns: `"user"` on `getSpecificUser`, `"product"` on `getSpecificProduct`, and `"order"` on `orderById`.
3. **Casing Inconsistencies in Item Fields:**
   - Product items use PascalCase for the ID: `Product_id`.
   - Order items use lowercase snake_case for IDs: `order_id` and `product_id`.
   - Sell history items mix PascalCase and snake_case: `Sell_id` and `Order_id` (PascalCase), alongside `product_id` and `remaining_stock` (lowercase snake_case).

---

### C. Type Quirks (Request Sending vs. Response Serialization)

- **Booleans (`isApproved`, `block`, `sold`):**
  - **In Requests:** Endpoints (`/admin/approveUser`, `/admin/approveOrder`) accept strings (`"true"`, `"false"`, `"1"`, `"0"`).
  - **In Responses:** List endpoints (`getAllUsers`, `getAllOrders`, `getSellHistory`) cast values to standard JSON booleans (`true` / `false`).
  - **In `getSpecificUser`:** Returns raw SQLite column value (which can be integer `1`/`0` or boolean). Kotlin parser should handle either or register a lenient Boolean type adapter.
- **Amounts and Quantities:**
  - `price` and `total_amount` are returned as Double (floating-point numbers).
  - `stock`, `quantity`, and `remaining_stock` are returned as Integer.

---

### D. Form Field Naming Quirks in Requests

- **PascalCase Parameters:**
  - `Product_id` must be sent with capital 'P': `POST /admin/user/getSpecificProduct`, `PATCH /admin/updateProduct`, `POST /admin/deleteProduct`, `POST /admin/getproductsellhistory`.
  - `Order_id` must be sent with capital 'O': `POST /admin/user/orderById`, `PATCH /admin/updateOrder`, `PATCH /admin/approveOrder`, `POST /admin/deleteOrder`, `POST /admin/recordSell`.
  - `Sell_id` must be sent with capital 'S': `POST /admin/deleteSellHistory`.
- **camelCase vs snake_case:**
  - `phoneNumber` (camelCase) is required when posting to `POST /admin/create` and `POST /user/create`, but the database and JSON responses return `phone_number` (snake_case).
  - `pincode` (all lowercase, no underscore) is sent in `POST /user/create`, while `pin_code` (snake_case) is returned in user responses.
- **Profile Image Updates (`image_url`):**
  - `image_url` can be passed as a form parameter to `PATCH /admin/updateUser` (editable by both admin and the user themselves) and `PATCH /admin/update` (admin only) to update profile/avatar URLs.

---

### E. Retrofit Interface Mismatch Verification

- **Path & Method Verification:** All 30 endpoints declared in the Kotlin checklist match backend routes and HTTP methods with 100% accuracy.
- **Multipart Form Uploads:** `POST admin/addProduct`, `PATCH admin/updateProduct`, `POST admin/create`, `PATCH admin/update`, `POST user/create`, and `PATCH admin/updateUser` all support `@Multipart` with `@Part image: MultipartBody.Part?` and `@Part` / `@Field` parameters for direct Cloudinary image uploads from device.
- **Unified Error Handling:** Every error status (400, 401, 403, 404, 500) returns a consistent JSON body containing `status: Int` and `message: String`. Retrofit can safely deserialize `response.errorBody()` with:
  ```kotlin
  data class ApiErrorResponse(
      val status: Int,
      val message: String
  )
  ```

---

## 6. Legacy vs Current Differences

The following table summarizes all behavioral differences between `_archive/main_legacy.py` and the current production codebase, detailing their impact on the Kotlin Android app:

| Endpoint                                                                                                                                                   | Legacy Behavior                                                                                                         | Current Refactored Behavior                                                                                                                                                                                                                                                                                                      | Impact on Kotlin Android App                                                                                                                                                     |
| :--------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **All Endpoints (Error States)**                                                                                                                           | Returned HTTP 200 OK headers with error details in JSON body: `return jsonify({'message': str(error), 'status': 400})`. | Returns standard HTTP error codes: `return jsonify(payload), 400` (or 401, 403, 404, 500).                                                                                                                                                                                                                                       | `response.isSuccessful` now correctly evaluates to `false` on failure; client error interceptors and `response.errorBody()` trigger as expected.                                 |
| **`PATCH /admin/updateUser`**                                                                                                                              | Stored updated password in raw plaintext; allowed non-admin callers to set `role`, `isApproved`, and `block`.           | Automatically hashes passwords via Werkzeug; strictly whitelists non-admin fields (`name`, `address`, `phone_number`, `pin_code`, `image_url`, `password`).                                                                                                                                                                      | Admin app can safely update user passwords and profile pictures; non-admin users cannot accidentally or maliciously escalate privileges.                                         |
| **`GET /admin/getAllUsers`**                                                                                                                               | Included `"password": user[2]` in user objects.                                                                         | Completely removed password field from SELECT and JSON serialization; includes `image_url`.                                                                                                                                                                                                                                      | If Kotlin `UserDto` declared `val password: String`, mark it nullable `val password: String? = null` or remove it. Declare `val image_url: String? = null` for avatar rendering. |
| **`GET /admin/getAllAdmins`**                                                                                                                              | Included `"password": admin[2]` in admin objects.                                                                       | Completely removed password field from SELECT and JSON serialization; includes `image_url`.                                                                                                                                                                                                                                      | If Kotlin `AdminDto` declared `val password: String`, mark it nullable or remove it. Declare `val image_url: String? = null` for avatar rendering.                               |
| **`POST /admin/user/getSpecificUser`**                                                                                                                     | Included `"password"` in JSON; crashed with `TypeError: NoneType` (500) if user ID did not exist.                       | Omitted password; returns HTTP 404 with `{"status": 404, "user": null, "message": "User not found"}` on missing user; includes `image_url`.                                                                                                                                                                                      | App receives clean HTTP 404 response instead of unhandled 500 server crash when viewing non-existent user.                                                                       |
| **`POST /admin/user/getSpecificProduct`**                                                                                                                  | Crashed with 500 error on non-existent `Product_id`.                                                                    | Returns HTTP 404 with `{"status": 404, "product": null, "message": "Product not found"}`.                                                                                                                                                                                                                                        | App receives clean HTTP 404 response instead of unhandled 500 error.                                                                                                             |
| **`POST /admin/user/orderById`**                                                                                                                           | Crashed with 500 error on non-existent `Order_id`.                                                                      | Returns HTTP 404 with `{"status": 404, "order": null, "message": "Order not found"}`.                                                                                                                                                                                                                                            | App receives clean HTTP 404 response instead of unhandled 500 error.                                                                                                             |
| **`POST /admin/recordSell`**                                                                                                                               | Unhandled crash if `Order_id` was missing or unapproved.                                                                | Returns HTTP 404 if order not found, HTTP 400 if order is not approved (`isApproved=0`), and HTTP 400 if stock is insufficient.                                                                                                                                                                                                  | Explicit error messages allow Android app to display contextual error toast/dialogs.                                                                                             |
| **Admin & User Profile Images (`getAllAdmins`, `getAllUsers`, `getSpecificUser`, `createAdmin`, `createUser`, `updateUser`, `update`)**                    | `Admin` and `Users` tables lacked profile image storage and file upload handlers.                                       | Added `image_url VARCHAR(1000) DEFAULT NULL` column to `Admin` and `Users`; exposed in read queries; creation (`POST admin/create`, `POST user/create`) and update (`PATCH admin/updateUser`, `PATCH admin/update`) endpoints now follow the exact same Cloudinary upload workflow as product images (`request.files['image']`). | Android app can upload images from device via `@Multipart` or send URL strings to create and update admin/user profiles.                                                         |
| **Order & Sell History Endpoints (`getAllOrders`, `getOrdersByUserId`, `orderById`, `getSellHistory`, `getSellHistoryByUserId`, `getproductsellhistory`)** | Did not include `image_url` property in response payloads.                                                              | Performs JOIN with `Products` by `product_id` (with fallback to `Order_Details.image_url` / `Sell_History.image_url`) and returns `"image_url"`.                                                                                                                                                                                 | Add `val image_url: String? = null` to `OrderDto` and `SellDto` in Kotlin Android app to render product thumbnails directly on Order and History screens.                        |

---

## 7. UNVERIFIED Items

_None._

All 39 backend endpoints, 30 Kotlin-consumed contracts, request parameter types, response envelope schemas, database column definitions, and error conditions were verified directly from active source code in `app/routes/`, `app/services/`, and `app/errors.py`.
