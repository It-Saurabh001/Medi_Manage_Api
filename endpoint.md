You are a Senior Flask API documentation engineer. Document my Flask backend's API contract by reading the actual code in this workspace, and write the result to response.md in the project root.

PROJECT CONTEXT

- Medical store management REST API: Flask, sqlite3, flask-jwt-extended, Cloudinary image upload, OTP email.
- Consumed by a Kotlin Android admin app (Retrofit with Response<T> and Gson-style data classes).
- Routes are in app/routes/\*.py (blueprints). If the project is not refactored, they are in main.py or main_legacy.py. Business logic is in app/services/, DB schema in app/services/db_init.py (or createTableOperation.py), response and error helpers in app/utils/responses.py and app/errors.py.

STRICT TOKEN RULES (HIGHEST PRIORITY)

1. No filler, greetings, or restating my request.
2. Do not print the contents of response.md in chat. Write it to the file only.
3. Do not echo source code back. Refer to files by path and function name.
4. Write the file in chunks: create it with the header sections, then append endpoint sections in groups of at most 8. Do not rewrite the whole file for small fixes; patch only the affected section.
5. Do not re-read files already read. No bonus sections beyond those listed.
6. If you cannot access the code, ask me ONCE (single list) which files to paste, then wait.

SOURCE-OF-TRUTH RULES

1. Derive everything from code: route decorators, request.form / request.files / request.args / request.get_json usage, decorators (jwt_required, role_required, etc.), and the return statements in routes AND in the service functions they call.
2. Document EVERY distinct return path of an endpoint (each success shape and each error shape), not only the happy path.
3. Never invent keys, status codes, or types. If something cannot be determined from the code, write UNVERIFIED and state what is missing.
4. Use dummy values only. Never include real emails, tokens, passwords, OTPs, or data from the database file. Never read or print values from .env.
5. If you run code to confirm response shapes, use the Flask test client with the testing config and a temporary database. Never touch My_Medical_Shope.db and never send real emails. If you cannot run code, skip this and rely on static analysis.

KOTLIN APP CHECKLIST
Verify each of these 30 endpoints exists with the same HTTP method and path (Retrofit paths have no leading slash). Report any missing, renamed, or method-mismatched endpoint.
POST admin/refreshToken (Authorization header)
POST admin/create | POST admin/login | POST admin/verifyOtp | POST admin/delete | PATCH admin/update
POST admin/requestAdminPasswordReset | POST admin/resetAdminPasswordWithOtp
GET admin/getAllAdmins | GET admin/getAllUsers | POST admin/user/getSpecificUser
PATCH admin/approveUser | POST admin/deleteUser | PATCH admin/updateUser
GET admin/user/getAllProducts | POST admin/addProduct (multipart) | POST admin/user/getSpecificProduct
PATCH admin/updateProduct (multipart) | POST admin/deleteProduct
GET admin/getAllOrders | POST admin/user/getOrdersByUserId | POST admin/user/orderById
PATCH admin/updateOrder | PATCH admin/approveOrder | POST admin/deleteOrder
POST admin/recordSell | GET admin/getSellHistory | POST admin/user/getSellHistoryByUserId
POST admin/getproductsellhistory | POST admin/deleteSellHistory

STEPS

STEP 1: DISCOVER ROUTES

- List ALL routes in the backend (not only the 30 above), including health and user-side routes. For each: method, full URL, handler function, source file.
- Mark which ones the Kotlin app uses (Y/N) and flag Kotlin endpoints that have no matching route.

STEP 2: GLOBAL CONVENTIONS

- Base URL and port used in development (from run scripts or config).
- Authentication: how tokens are issued, header format, access vs refresh token, token lifetimes, claims used for role checks.
- Request content types used (form-urlencoded, multipart, JSON).
- The standard response envelope (keys that appear in every response) and how it is built.
- Table of global error responses: status code, trigger, JSON body. Include 401 and 422 JWT errors (missing, expired, invalid token), 404 unknown URL, 405, 500.

STEP 3: PER-ENDPOINT DOCUMENTATION
Use this exact structure for every endpoint, ordered as in the index:

### <n>. <METHOD> <url> : <short name>

- **Auth:** none | access token | refresh token. **Role:** admin | user | both
- **Request:** content type, then a table: Field | Type | Required | Notes (include query params, form fields, file parts, headers)
- **Success response:** HTTP status, then a fenced json example containing EVERY key the code can return, with dummy values. Below it, a note on types and any key that is optional or conditional.
- **Error responses:** table: HTTP status | Condition | Body
- **Side effects:** DB writes, email/OTP sent, Cloudinary upload, state changes (or "none")
- **Source:** file : function
- **Kotlin app:** used (Retrofit function name) | not used

STEP 4: KOTLIN INTEGRATION NOTES

- For each endpoint the app uses: every response key with JSON type and whether it can be null or missing (so I can mark Kotlin fields nullable).
- Inconsistent response key names across endpoints (for example users, admins, product, order, sell_history).
- Type quirks: how isApproved, block, sold, quantity, price are sent in requests and returned in responses (bool vs 0/1 vs string).
- Form field naming quirks (for example Product_id, Order_id, Sell_id, phoneNumber vs phone_number).
- Mismatches between the Retrofit interface and the backend: method, path, field name, missing or extra fields.
- Which HTTP statuses each endpoint can return, and whether the error body always contains status and message.

STEP 5: LEGACY COMPARISON (only if the old code exists: \_archive/main_legacy.py or git history)

- Table: Endpoint | Legacy behavior | Current behavior | Impact on Kotlin app. Include only endpoints where behavior differs (HTTP status on errors, removed fields, whitelisted fields, 404 handling).
- If no legacy source exists, write one line saying the comparison was skipped.

STEP 6: WRITE response.md
Use this structure:

# API Response Reference

## 1. Overview and Global Conventions

## 2. Global Error Responses

## 3. Endpoint Index (table: # | Method | URL | Auth | Role | Kotlin app)

## 4. Endpoint Details

## 5. Kotlin Integration Notes

## 6. Legacy vs Current Differences

## 7. UNVERIFIED Items

- Section 7 lists every UNVERIFIED item with the file or information needed to resolve it.
- Use valid Markdown with fenced json blocks and language tags.

FINAL REPLY
After the file is written, reply with ONLY: file path, total endpoints documented, number of Kotlin endpoints matched / missing / mismatched, number of UNVERIFIED items.

BEGIN
Start with STEP 1.
