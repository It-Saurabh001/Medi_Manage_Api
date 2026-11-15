# API Response Reference

_Single source of truth for the mobile team. Updated in Part 3 (final) on 2026-11-14 against the live `url_map` and `app/openapi/*.py`; admin signup added on 2026-11-15. All examples were captured from the running code (Flask test client) unless marked `(unverified)`; JWTs are shortened with `...`._

## 1. Overview and Global Conventions

### Base URL & versioning
- Base URL: `https://<host>` (dev: `http://localhost:5000`). Every API endpoint lives under the prefix **`/api/v1`** (config `API_PREFIX`). Only `/health`, `/health/ready`, `/api/docs` (Swagger UI) and the legacy `/dox` redirect are outside it.
- Trailing slashes are accepted. Paths are plural, lowercase, kebab-case; non-CRUD actions are `POST` sub-resources (`/orders/{order_id}/approve`).
- A breaking change will get a new prefix (`/api/v2`); `/api/v1` stays stable.
- `GET /api/v1` lists the public links; `GET /api/v1/openapi.json` is the machine-readable contract (when docs are enabled).

### Auth flow
1. `POST /api/v1/auth/login` `{email, password, account_type}` -> 200 `{account_id, otp_required: true, otp_expires_in}`. A 6-digit OTP is emailed (never returned).
2. `POST /api/v1/auth/verify-otp` `{account_id, otp, account_type}` -> 200 `{access_token, refresh_token, token_type: "Bearer", expires_in, role, account_type, account_id}`.
3. Call APIs with `Authorization: Bearer <access_token>` (access token lifetime `expires_in`, 3600 s by default).
4. On **401 `TOKEN_EXPIRED`**: call `POST /api/v1/auth/refresh` once with `Authorization: Bearer <refresh_token>`, store BOTH new tokens (the old refresh token is revoked), retry the request. If refresh fails (401/403) clear tokens and go to login.
5. `POST /api/v1/auth/logout` with the access token and `{refresh_token}` in the body revokes both.
- 401 `TOKEN_INVALID` = revoked/malformed token (do not refresh; go to login). 403 `ACCOUNT_BLOCKED` / `ACCOUNT_NOT_APPROVED` can come from login, verify-otp and refresh.
- Signup (`POST /api/v1/users`) creates an unapproved customer; an admin must call `POST /api/v1/users/{user_id}/approve` before login works.
- Admin signup (`POST /api/v1/admins/register`, admin app "Create account"): the very first admin is created approved and becomes the **owner** (`is_owner: true`). Every later admin starts with `is_approved: false` and login returns 403 `ACCOUNT_NOT_APPROVED` until an existing admin calls `POST /api/v1/admins/{admin_id}/approve`. Show a signup-code field when `GET /app-config` returns `admin_signup.code_required: true`.

### Admin signup, owner and server settings
- **Owner:** the first registered admin (`is_owner: true`). The API cannot disable (`PATCH role=disabled`), unapprove or delete the owner: 403 `FORBIDDEN` "Owner account is protected". A DB unique index allows at most one owner. The first-admin check and the insert run in one locked transaction, so two simultaneous first signups cannot both become approved.
- **Last approved admin:** deleting or disabling the last approved, active admin returns 409 `CONFLICT` "At least one approved admin is required".
- **`ADMIN_SIGNUP_CODE` (env, strongly recommended in production):** when set, `POST /admins/register` must send a matching `signup_code` (constant-time compare). Otherwise the response is 403 `FORBIDDEN` "Invalid signup code". When it is empty, no code is needed, so **anyone who can reach the server can request an admin account**. That account still needs approval, except the very first one on an empty database. In production the server logs a warning at start-up when the code is not set. Share the code out of band; it is never returned, logged or written to the audit log.
- **Rate limit:** `POST /admins/register` allows `ADMIN_SIGNUP_RATE_LIMIT` requests (default 10) per client IP per `ADMIN_SIGNUP_RATE_WINDOW_SECONDS` (default 3600). After that it returns 429 `RATE_LIMITED` with a `Retry-After` header (seconds). Production counts in Redis (shared by all workers); development counts in memory. `0` disables the limit. Note: `/auth/login` itself has no IP rate limit (only the 5-attempt OTP limit applies).
- **Emergency recovery (CLI only, no HTTP):** `flask --app wsgi approve-admin --email <email> [--owner]` approves and re-activates that admin (role back to `admin`). `--owner` moves ownership to it. Audited as `admin.approve` by `system:cli`.
- **Existing databases:** the migration only adds `Admin.is_approved` (existing admins = approved) and `Admin.is_owner` (existing admins = not owner). No data is removed. On a database that already has admins, every signup needs approval; use the CLI `--owner` flag if you want to assign an owner.

### Standard response shapes
- Success: `{"status": 200, "message": "...", "data": {...} | [...] | null}`
- List: `{"status": 200, "message": "...", "data": [...], "pagination": {"limit": 20, "offset": 0, "total": 57}}`
- Error: `{"status": 400, "message": "...", "code": "VALIDATION_ERROR", "fields": {"email": "must be a valid email address"}}` (`fields` only when field-level details exist).
- `status` always equals the HTTP status. Keys are snake_case and never omitted (missing values are `null`); booleans are `true`/`false`; numbers are JSON numbers; timestamps are UTC ISO-8601 with `Z` (`2026-11-14T17:33:47Z`), dates are `YYYY-MM-DD`.
- Creates return **201** and a `Location` header with the absolute URL of the new resource.

### Headers
| Header | Direction | Use |
| :--- | :--- | :--- |
| `Authorization: Bearer <token>` | request | Access token (refresh token only for `/auth/refresh`). |
| `Content-Type` | request | `application/json`, or `multipart/form-data` / `application/x-www-form-urlencoded` (needed for file uploads). Other types -> 415. Malformed JSON -> 400. |
| `Idempotency-Key` | request | Optional on `POST /orders`, `POST /orders/{order_id}/sell`, `POST /products/{product_id}/stock/purchase`. Same key + same user + same endpoint replays the first response. |
| `Idempotent-Replayed: true` | response | Set on a replayed response. |
| `X-App-Version` | request | App semver (`1.4.0`). If the server has `MIN_APP_VERSION` and the header is lower -> 426 `UPGRADE_REQUIRED` (header `X-Min-App-Version`). Exempt: `/health*`, `/api/docs`, `/api/v1/app-config`. Requests without the header are not gated. |
| `Location` | response | Absolute URL of a created resource (201). |
| `Allow` | response | Sent with 405. |

### Pagination and `updated_since` sync
- Every list accepts `limit` (default 20, max 100; larger values are clamped), `offset` (default 0), `sort` (per-endpoint allow-list) and `order` (`asc`/`desc`). Invalid values -> 400 `VALIDATION_ERROR` with `fields`.
- Next page: `offset += limit` while `offset < pagination.total`.
- Incremental sync: `GET /products?updated_since=...`, `GET /orders?updated_since=...` and `GET /sales?updated_since=...` return rows changed at/after the UTC timestamp. Save the response time (or `server_time` from `/app-config`) and send it next time. `GET /users?updated_since=` filters by creation time (users have no `updated_at`).

### Upload rules
- Multipart file fields: `image` (products, users, admins: jpeg/png/webp) and `prescription` (orders: jpeg/png/webp/pdf).
- Max file size `uploads.max_upload_mb` (5 MB) and max request `uploads.max_request_bytes` (6 MB) from `/app-config`. Too large -> 413 `PAYLOAD_TOO_LARGE`; wrong type (checked by magic bytes) -> 415 `UNSUPPORTED_MEDIA_TYPE`.
- URL fields such as `image_url` cannot be written directly on accounts; upload a file instead.

### Enums (also served by `GET /api/v1/app-config`)
| Enum | Values |
| :--- | :--- |
| `schedule_type` | `OTC`, `H`, `H1`, `X`, `NARCOTIC` (prescription required for `H`, `H1`, `X`, `NARCOTIC`) |
| `dosage_form` | `Tablet`, `Capsule`, `Syrup`, `Injection`, `Ointment`, `Drops`, `Other` |
| order `status` | `pending`, `approved`, `sold`, `cancelled`, `returned` |
| `unit` (suggested) | `strip`, `bottle`, `tube`, `box`, `vial`, `sachet`, `piece`, `pack` |
| stock movement `reason` | `PURCHASE`, `SALE`, `ADJUSTMENT`, `EXPIRED_WRITEOFF`, `RETURN`, `CANCEL_RESTOCK` |
| `account_type` | `user`, `admin` |
| device `platform` | `android`, `ios` |
| admin `role` | `admin`, `disabled` (and `deleted` after soft delete) |
| admin flags | `is_approved` (false until approved after self-signup), `is_owner` (first registered admin; protected) |

Order transitions: `pending -> approved | cancelled` (approve / reject / cancel), `approved -> sold | cancelled` (sell / cancel), `sold -> returned` (return). Anything else -> 409 `INVALID_TRANSITION`.

---

## 2. Error Codes and Suggested Mobile Action

| code | HTTP | Suggested mobile action |
| :--- | :--- | :--- |
| `VALIDATION_ERROR` | 400 | Show `fields` messages next to the inputs; fix and resend. |
| `PRESCRIPTION_REQUIRED` | 400 | Ask for prescription upload and doctor name. |
| `UNAUTHORIZED` | 401 | No/invalid credentials; send the user to login. |
| `TOKEN_EXPIRED` | 401 | Call POST /auth/refresh once, then retry; on failure go to login. |
| `TOKEN_INVALID` | 401 | Token revoked or malformed; clear tokens and go to login. |
| `FORBIDDEN` | 403 | Role not allowed; hide the action. |
| `ACCOUNT_BLOCKED` | 403 | Show 'account blocked, contact the pharmacy'; log out. |
| `ACCOUNT_NOT_APPROVED` | 403 | Show 'awaiting approval'; allow retry later. |
| `NOT_FOUND` | 404 | Resource missing or not yours; refresh the list / go back. |
| `METHOD_NOT_ALLOWED` | 405 | Client bug: wrong HTTP method. |
| `CONFLICT` | 409 | Duplicate or state conflict; reload and show message. |
| `OUT_OF_STOCK` | 409 | Show available quantity from `fields.quantity`; let user reduce quantity. |
| `PRESCRIPTION_NOT_VERIFIED` | 409 | Admin: verify the prescription before selling. |
| `INVALID_TRANSITION` | 409 | Order state changed; reload the order. |
| `ALREADY_SOLD` | 409 | Order already sold; reload the order. |
| `BATCH_EXPIRED` | 409 | Pick a non-expired batch / correct the expiry date. |
| `PAYLOAD_TOO_LARGE` | 413 | File too large; compress or choose a smaller file. |
| `UNSUPPORTED_MEDIA_TYPE` | 415 | Wrong file/content type; use an allowed type. |
| `UPGRADE_REQUIRED` | 426 | Block the UI and open the store page to update the app. |
| `RATE_LIMITED` | 429 | Too many attempts; wait or request a new OTP. |
| `INTERNAL_ERROR` | 500 (also 502 when the OTP email cannot be sent, 503 from /health/ready) | Show a generic error and allow retry. |

Unknown routes return 404 `NOT_FOUND`; wrong methods 405 `METHOD_NOT_ALLOWED`. Exception text is never sent to clients.

---

## 3. Endpoint Index

| # | Method | Path | Role | Group |
| :-- | :--- | :--- | :--- | :--- |
| H1 | `GET` | `/health` | public | Health |
| H2 | `GET` | `/health/ready` | public | Health |
| H3 | `GET` | `/api/docs` | public (ENABLE_DOCS) | Docs |
| H4 | `GET` | `/dox` | public (ENABLE_DOCS) | Docs (legacy redirect) |
| 1 | `GET` | `/api/v1` | public (no token) | Meta & app bootstrap |
| 2 | `GET` | `/api/v1/app-config` | public (no token) | Meta & app bootstrap |
| 3 | `GET` | `/api/v1/openapi.json` | public (no token) | Meta & app bootstrap |
| 4 | `POST` | `/api/v1/auth/login` | public (no token) | Auth |
| 5 | `POST` | `/api/v1/auth/logout` | admin, user | Auth |
| 6 | `POST` | `/api/v1/auth/password-reset/confirm` | public (no token) | Auth |
| 7 | `POST` | `/api/v1/auth/password-reset/request` | public (no token) | Auth |
| 8 | `POST` | `/api/v1/auth/refresh` | admin, user | Auth |
| 9 | `POST` | `/api/v1/auth/verify-otp` | public (no token) | Auth |
| 10 | `GET` | `/api/v1/users` | admin | Users |
| 11 | `POST` | `/api/v1/users` | public (no token) | Users |
| 12 | `GET` | `/api/v1/users/me` | user | Users |
| 13 | `PATCH` | `/api/v1/users/me` | user | Users |
| 14 | `GET` | `/api/v1/users/{user_id}` | admin, user | Users |
| 15 | `PATCH` | `/api/v1/users/{user_id}` | admin | Users |
| 16 | `DELETE` | `/api/v1/users/{user_id}` | admin | Users |
| 17 | `POST` | `/api/v1/users/{user_id}/approve` | admin | Users |
| 18 | `POST` | `/api/v1/users/{user_id}/block` | admin | Users |
| 19 | `POST` | `/api/v1/users/{user_id}/unblock` | admin | Users |
| 20 | `GET` | `/api/v1/admins` | admin | Admins |
| 21 | `POST` | `/api/v1/admins` | admin | Admins |
| 22 | `GET` | `/api/v1/admins/{admin_id}` | admin | Admins |
| 23 | `PATCH` | `/api/v1/admins/{admin_id}` | admin | Admins |
| 24 | `DELETE` | `/api/v1/admins/{admin_id}` | admin | Admins |
| 25 | `POST` | `/api/v1/admins/register` | public (no token) | Admins |
| 26 | `POST` | `/api/v1/admins/{admin_id}/approve` | admin | Admins |
| 27 | `POST` | `/api/v1/devices` | admin, user | Devices |
| 28 | `DELETE` | `/api/v1/devices/{device_id}` | admin, user | Devices |
| 29 | `GET` | `/api/v1/product-categories` | admin, user | Products |
| 30 | `GET` | `/api/v1/products` | admin, user | Products |
| 31 | `POST` | `/api/v1/products` | admin | Products |
| 32 | `GET` | `/api/v1/products/by-barcode/{barcode}` | admin, user | Products |
| 33 | `GET` | `/api/v1/products/{product_id}` | admin, user | Products |
| 34 | `PATCH` | `/api/v1/products/{product_id}` | admin | Products |
| 35 | `POST` | `/api/v1/products/{product_id}/deactivate` | admin | Products |
| 36 | `POST` | `/api/v1/products/{product_id}/reactivate` | admin | Products |
| 37 | `GET` | `/api/v1/batches/{batch_id}` | admin | Batches & stock |
| 38 | `PATCH` | `/api/v1/batches/{batch_id}` | admin | Batches & stock |
| 39 | `POST` | `/api/v1/batches/{batch_id}/write-off` | admin | Batches & stock |
| 40 | `GET` | `/api/v1/products/{product_id}/batches` | admin | Batches & stock |
| 41 | `POST` | `/api/v1/products/{product_id}/batches` | admin | Batches & stock |
| 42 | `POST` | `/api/v1/products/{product_id}/stock/adjust` | admin | Batches & stock |
| 43 | `POST` | `/api/v1/products/{product_id}/stock/purchase` | admin | Batches & stock |
| 44 | `GET` | `/api/v1/stock-movements` | admin | Batches & stock |
| 45 | `GET` | `/api/v1/inventory/expired` | admin | Inventory alerts |
| 46 | `GET` | `/api/v1/inventory/low-stock` | admin | Inventory alerts |
| 47 | `GET` | `/api/v1/inventory/near-expiry` | admin | Inventory alerts |
| 48 | `GET` | `/api/v1/inventory/out-of-stock` | admin | Inventory alerts |
| 49 | `GET` | `/api/v1/orders` | admin, user (users only see their own resources; others return 404) | Orders |
| 50 | `POST` | `/api/v1/orders` | user | Orders |
| 51 | `GET` | `/api/v1/orders/{order_id}` | admin, user (users only see their own resources; others return 404) | Orders |
| 52 | `PATCH` | `/api/v1/orders/{order_id}` | admin, user (users only see their own resources; others return 404) | Orders |
| 53 | `POST` | `/api/v1/orders/{order_id}/approve` | admin | Orders |
| 54 | `POST` | `/api/v1/orders/{order_id}/cancel` | admin, user (users only see their own resources; others return 404) | Orders |
| 55 | `GET` | `/api/v1/orders/{order_id}/invoice` | admin, user (users only see their own resources; others return 404) | Orders |
| 56 | `POST` | `/api/v1/orders/{order_id}/prescription` | admin, user (users only see their own resources; others return 404) | Orders |
| 57 | `POST` | `/api/v1/orders/{order_id}/reject` | admin | Orders |
| 58 | `POST` | `/api/v1/orders/{order_id}/return` | admin | Orders |
| 59 | `POST` | `/api/v1/orders/{order_id}/sell` | admin | Orders |
| 60 | `POST` | `/api/v1/orders/{order_id}/verify-prescription` | admin | Orders |
| 61 | `GET` | `/api/v1/users/{user_id}/orders` | admin, user (users only see their own resources; others return 404) | Orders |
| 62 | `GET` | `/api/v1/sales` | admin | Sales |
| 63 | `GET` | `/api/v1/suppliers` | admin | Suppliers |
| 64 | `POST` | `/api/v1/suppliers` | admin | Suppliers |
| 65 | `GET` | `/api/v1/suppliers/{supplier_id}` | admin | Suppliers |
| 66 | `PATCH` | `/api/v1/suppliers/{supplier_id}` | admin | Suppliers |
| 67 | `POST` | `/api/v1/suppliers/{supplier_id}/deactivate` | admin | Suppliers |
| 68 | `GET` | `/api/v1/dashboard/summary` | admin | Reports & dashboard |
| 69 | `GET` | `/api/v1/reports/sales` | admin | Reports & dashboard |
| 70 | `GET` | `/api/v1/reports/top-products` | admin | Reports & dashboard |
| 71 | `GET` | `/api/v1/audit-logs` | admin | Audit |

---

## 4. Endpoint Details

#### Health & docs (outside `/api/v1`)

### H1. GET /health

- **Role/auth:** public (no token)
- **Purpose:** Liveness probe (no dependencies checked).
- **Headers:** none required (not gated by `X-App-Version`)
- **Path/query params:** none
- **Request body:** none
- **Success:** HTTP 200 (not wrapped in the standard envelope)
  ```json
  {
    "service": "Medi_Manage_Api",
    "status": "healthy"
  }
  ```
- **Errors:** none expected.
- **Notes:** For load balancers / uptime checks.

### H2. GET /health/ready

- **Role/auth:** public (no token)
- **Purpose:** Readiness probe: database reachable; Redis (OTP store) reachable when configured.
- **Headers:** none required
- **Path/query params:** none
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "checks": {
      "cache": "skipped",
      "database": "ok"
    },
    "service": "Medi_Manage_Api",
    "status": "ready"
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 503 | `INTERNAL_ERROR` | `{"status": 503, "message": "Service not ready: database unavailable", "code": "INTERNAL_ERROR"}` (unverified) |
- **Notes:** `cache` is `ok` when a Redis-backed store is configured.

### H3. GET /api/docs

- **Role/auth:** public (no token)
- **Purpose:** Swagger UI (HTML) for `/api/v1/openapi.json`.
- **Headers:** none
- **Path/query params:** none
- **Request body:** none
- **Success:** HTTP 200, `text/html` page.
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "Resource not found", "status": 404}` |
- **Notes:** 404 when `ENABLE_DOCS=false` (production default). Swagger UI assets load from jsDelivr (swagger-ui-dist 5.17.14).

### H4. GET /dox

- **Role/auth:** public (no token)
- **Purpose:** Legacy documentation URL; permanent redirect.
- **Headers:** none
- **Path/query params:** none
- **Request body:** none
- **Success:** HTTP 301 with `Location: /api/docs` (no JSON body).
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "Resource not found", "status": 404}` |
- **Notes:** Kept only as a redirect; use `/api/docs`.

#### Meta & app bootstrap

### 1. GET /api/v1

- **Role/auth:** public (no token)
- **Purpose:** API index: name, version and public links (built from the URL map)
- **Headers:** `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path/query params:** none
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "api_version": "v1",
      "links": [
        {
          "href": "/api/docs",
          "methods": [
            "GET"
          ],
          "rel": "docs.swagger_ui"
        },
        {
          "href": "/api/v1",
          "methods": [
            "GET"
          ],
          "rel": "meta.api_index"
        },
        {
          "href": "/api/v1/app-config",
          "methods": [
            "GET"
          ],
          "rel": "meta.app_config"
        },
        {
          "href": "/api/v1/auth/login",
          "methods": [
            "POST"
          ],
          "rel": "auth.login"
        },
        {
          "href": "/api/v1/auth/password-reset/confirm",
          "methods": [
            "POST"
          ],
          "rel": "auth.password_reset_confirm"
        },
        {
          "href": "/api/v1/auth/password-reset/request",
          "methods": [
            "POST"
          ],
          "rel": "auth.password_reset_request"
        },
        {
          "href": "/api/v1/auth/verify-otp",
          "methods": [
            "POST"
          ],
          "rel": "auth.verify_otp"
        },
        {
          "href": "/api/v1/openapi.json",
          "methods": [
            "GET"
          ],
          "rel": "meta.openapi_json"
        },
        {
          "href": "/api/v1/users",
          "methods": [
            "POST"
          ],
          "rel": "user.create_user"
        },
        {
          "href": "/health",
          "methods": [
            "GET"
          ],
          "rel": "health.health"
        },
        {
          "href": "/health/ready",
          "methods": [
            "GET"
          ],
          "rel": "health.ready"
        }
      ],
      "name": "Medi_Manage_Api",
      "version": "1.0.0"
    },
    "message": "Medi_Manage_Api v1",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 405 | `METHOD_NOT_ALLOWED` | `{"status": 405, "message": "Method not allowed", "code": "METHOD_NOT_ALLOWED"}` |
  | 426 | `UPGRADE_REQUIRED` | `{"status": 426, "message": "This app version is no longer supported; please update.", "code": "UPGRADE_REQUIRED", "fields": {"X-App-Version": "minimum supported version is 2.0.0"}}` |
- **Notes:** Public links only, built from the URL map.

### 2. GET /api/v1/app-config

- **Role/auth:** public (no token)
- **Purpose:** Client bootstrap: min_app_version, enums, upload limits, server_time (UTC), error codes
- **Headers:** `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path/query params:** none
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "admin_signup": {
        "code_required": false,
        "enabled": true
      },
      "api_prefix": "/api/v1",
      "api_version": "v1",
      "docs_enabled": true,
      "enums": {
        "account_types": [
          "user",
          "admin"
        ],
        "device_platforms": [
          "android",
          "ios"
        ],
        "dosage_forms": [
          "Tablet",
          "Capsule",
          "Syrup",
          "Injection",
          "Ointment",
          "Drops",
          "Other"
        ],
        "order_statuses": [
          "pending",
          "approved",
          "sold",
          "cancelled",
          "returned"
        ],
        "prescription_schedules": [
          "H",
          "H1",
          "NARCOTIC",
          "X"
        ],
        "schedule_types": [
          "OTC",
          "H",
          "H1",
          "X",
          "NARCOTIC"
        ],
        "stock_movement_reasons": [
          "PURCHASE",
          "SALE",
          "ADJUSTMENT",
          "EXPIRED_WRITEOFF",
          "RETURN",
          "CANCEL_RESTOCK"
        ],
        "units": [
          "strip",
          "bottle",
          "tube",
          "box",
          "vial",
          "sachet",
          "piece",
          "pack"
        ]
      },
      "error_codes": [
        "VALIDATION_ERROR",
        "NOT_FOUND",
        "UNAUTHORIZED",
        "TOKEN_EXPIRED",
        "TOKEN_INVALID",
        "FORBIDDEN",
        "ACCOUNT_BLOCKED",
        "ACCOUNT_NOT_APPROVED",
        "OUT_OF_STOCK",
        "PRESCRIPTION_REQUIRED",
        "PRESCRIPTION_NOT_VERIFIED",
        "INVALID_TRANSITION",
        "CONFLICT",
        "ALREADY_SOLD",
        "BATCH_EXPIRED",
        "UPGRADE_REQUIRED",
        "RATE_LIMITED",
        "PAYLOAD_TOO_LARGE",
        "UNSUPPORTED_MEDIA_TYPE",
        "METHOD_NOT_ALLOWED",
        "INTERNAL_ERROR"
      ],
      "min_app_version": null,
      "otp": {
        "expires_in": 300,
        "length": 6,
        "max_attempts": 5
      },
      "pagination": {
        "default_limit": 20,
        "max_limit": 100
      },
      "server_time": "2026-11-14T17:33:45Z",
      "uploads": {
        "allowed_mime_types": [
          "image/jpeg",
          "image/png",
          "image/webp",
          "application/pdf"
        ],
        "image_mime_types": [
          "image/jpeg",
          "image/png",
          "image/webp"
        ],
        "max_request_bytes": 6291456,
        "max_upload_mb": 5
      }
    },
    "message": "App configuration",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 405 | `METHOD_NOT_ALLOWED` | `{"status": 405, "message": "Method not allowed", "code": "METHOD_NOT_ALLOWED"}` |
- **Response fields (admin signup):**
  | Field | Type | Notes |
  | :--- | :--- | :--- |
  | `admin_signup.enabled` | boolean | always `true`: `POST /admins/register` is available |
  | `admin_signup.code_required` | boolean | `true` when the server sets `ADMIN_SIGNUP_CODE`; show a "Signup code" input and send it as `signup_code` |
- **Notes:** Public, exempt from the X-App-Version gate. Call on app start: compare `min_app_version`, cache enums, use `server_time` for clock skew. Use `admin_signup` to decide whether the admin app's "Create account" screen shows a signup-code field.

### 3. GET /api/v1/openapi.json

- **Role/auth:** public (no token)
- **Purpose:** This OpenAPI document (404 when ENABLE_DOCS is false)
- **Headers:** `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path/query params:** none
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "openapi": "3.0.3",
    "info": {
      "title": "Medi_Manage_Api",
      "version": "1.0.0"
    },
    "paths": {}
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "Resource not found", "code": "NOT_FOUND"}` |
- **Notes:** 404 NOT_FOUND when ENABLE_DOCS=false. The example is abbreviated.

#### Auth

### 4. POST /api/v1/auth/login

- **Role/auth:** public (no token)
- **Purpose:** Check credentials and email a 6-digit login OTP (never returned)
- **Headers:** `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `email` | string | required | max length 200 |
  | `password` | string | required | max length 128 |
  | `account_type` | string | optional | one of `user`, `admin`; default `"user"` |
  Example:
  ```json
  {
    "email": "priya@example.com",
    "password": "Priya#2026",
    "account_type": "user"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "account_id": "UID_06ade2a9b763",
      "account_type": "user",
      "otp_expires_in": 300,
      "otp_required": true
    },
    "message": "Verification code sent to your email",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "Validation failed", "code": "VALIDATION_ERROR", "fields": {"email": "is required"}}` |
  | 401 | `UNAUTHORIZED` | `{"code": "UNAUTHORIZED", "message": "Invalid email or password", "status": 401}` |
  | 403 | `ACCOUNT_BLOCKED` | `{"code": "ACCOUNT_BLOCKED", "message": "Account is blocked", "status": 403}` |
  | 403 | `ACCOUNT_NOT_APPROVED` | `{"code": "ACCOUNT_NOT_APPROVED", "message": "Account is not approved yet", "status": 403}` |
- **Notes:** OTP (6 digits, TTL `otp_expires_in` s) is emailed, never returned. Same 401 for unknown email and wrong password. Blocked/unapproved accounts are rejected before an OTP is sent. Admins send `account_type=admin`; a self-registered admin gets 403 `ACCOUNT_NOT_APPROVED` until approved via `POST /admins/{admin_id}/approve`.

### 5. POST /api/v1/auth/logout

- **Role/auth:** admin, user (Bearer access token)
- **Purpose:** Revoke the access token (and the refresh token if supplied)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `refresh_token` | string | optional | optional; also revokes this refresh token |
  Example:
  ```json
  {
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0eXBlIjoicmVmcmVzaCIsInN1YiI6IlVJRF8wNmFkZTJhOWI3NjMifQ.GP6EUTLeDlTG"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "revoked": [
        "access",
        "refresh"
      ]
    },
    "message": "Logged out",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "Validation failed", "code": "VALIDATION_ERROR", "fields": {"refresh_token": "invalid token"}}` |
  | 401 | `TOKEN_INVALID` | `{"code": "TOKEN_INVALID", "message": "Token has been revoked", "status": 401}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
- **Notes:** Revokes the access token's `jti` and, if `refresh_token` is sent, that refresh token too (Redis blocklist in prod, in-memory in dev/test). Further use -> 401 TOKEN_INVALID.

### 6. POST /api/v1/auth/password-reset/confirm

- **Role/auth:** public (no token)
- **Purpose:** Set a new password with the reset OTP
- **Headers:** `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `email` | string | required | - |
  | `otp` | string | required | min length 6; max length 6 |
  | `new_password` | string | required | min length 8; max length 128 |
  | `account_type` | string | optional | one of `user`, `admin`; default `"user"` |
  Example:
  ```json
  {
    "email": "priya@example.com",
    "otp": "144651",
    "new_password": "Priya#2026",
    "account_type": "user"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": null,
    "message": "Password has been reset. Please log in.",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"new_password": "must be at least 8 characters"}, "message": "Validation failed", "status": 400}` |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"otp": "request a new code"}, "message": "Verification code expired or not requested", "status": 400}` |
  | 429 | `RATE_LIMITED` | `{"status": 429, "message": "Too many incorrect attempts; request a new code", "code": "RATE_LIMITED"}` |
- **Notes:** Single-use reset OTP, max 5 attempts. Writes an audit entry `auth.password_reset`.

### 7. POST /api/v1/auth/password-reset/request

- **Role/auth:** public (no token)
- **Purpose:** Email a password-reset OTP (same response whether or not the account exists)
- **Headers:** `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `email` | string | required | - |
  | `account_type` | string | optional | one of `user`, `admin`; default `"user"` |
  Example:
  ```json
  {
    "email": "priya@example.com",
    "account_type": "user"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "otp_expires_in": 300
    },
    "message": "If an account exists for this email, a reset code has been sent.",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "Validation failed", "code": "VALIDATION_ERROR", "fields": {"email": "is required"}}` |
- **Notes:** Always 200 with the same body (no account enumeration). The emailed reset OTP works only at /auth/password-reset/confirm.

### 8. POST /api/v1/auth/refresh

- **Role/auth:** admin, user (Bearer REFRESH token)
- **Purpose:** Rotate tokens using the refresh token (Authorization: Bearer <refresh_token>)
- **Headers:** `Authorization: Bearer <refresh_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path/query params:** none
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ...",
      "account_id": "UID_06ade2a9b763",
      "account_type": "user",
      "expires_in": 3600,
      "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ...",
      "role": "user",
      "token_type": "Bearer"
    },
    "message": "Token refreshed",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"code": "TOKEN_INVALID", "message": "Token has been revoked", "status": 401}` |
  | 403 | `ACCOUNT_BLOCKED` | `{"status": 403, "message": "Account is blocked", "code": "ACCOUNT_BLOCKED"}` |
  | 403 | `ACCOUNT_NOT_APPROVED` | `{"status": 403, "message": "Account is not approved yet", "code": "ACCOUNT_NOT_APPROVED"}` |
- **Notes:** Send the REFRESH token as the bearer. Role, block and approval status are re-read from the DB. Rotation: the presented refresh token is revoked; store the new pair. Re-using an old refresh token -> 401 TOKEN_INVALID.

### 9. POST /api/v1/auth/verify-otp

- **Role/auth:** public (no token)
- **Purpose:** Verify the login OTP and issue access + refresh tokens
- **Headers:** `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `account_id` | string | required | - |
  | `otp` | string | required | min length 6; max length 6 |
  | `account_type` | string | optional | one of `user`, `admin`; default `"user"` |
  Example:
  ```json
  {
    "account_id": "UID_06ade2a9b763",
    "otp": "672170",
    "account_type": "user"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ...",
      "account_id": "UID_06ade2a9b763",
      "account_type": "user",
      "expires_in": 3600,
      "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ...",
      "role": "user",
      "token_type": "Bearer"
    },
    "message": "Login successful",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"otp": "incorrect; 4 attempt(s) left"}, "message": "Invalid verification code", "status": 400}` |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"otp": "request a new code"}, "message": "Verification code expired or not requested", "status": 400}` |
  | 403 | `ACCOUNT_BLOCKED` | `{"status": 403, "message": "Account is blocked", "code": "ACCOUNT_BLOCKED"}` |
  | 403 | `ACCOUNT_NOT_APPROVED` | `{"status": 403, "message": "Account is not approved yet", "code": "ACCOUNT_NOT_APPROVED"}` |
  | 429 | `RATE_LIMITED` | `{"status": 429, "message": "Too many incorrect attempts; request a new code", "code": "RATE_LIMITED"}` |
- **Notes:** Login OTP only (a password-reset OTP is rejected). Max 5 attempts per OTP; the 5th wrong attempt invalidates it (429 RATE_LIMITED) and a new login is needed. The OTP is single-use.

#### Users

### 10. GET /api/v1/users

- **Role/auth:** admin (Bearer access token)
- **Purpose:** List customers (paginated)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `q` | string | - | matches name, email or phone |
  | `is_approved` | boolean | - | - |
  | `is_blocked` | boolean | - | - |
  | `include_deleted` | boolean | default `false` | - |
  | `updated_since` | string (date-time) | - | Users have no updated_at column: filters by created_at >= value |
  | `limit` | integer | min 1; max 100; default `20` | - |
  | `offset` | integer | min 0; default `0` | - |
  | `sort` | string | one of `created_at`, `name`; default `"created_at"` | - |
  | `order` | string | one of `asc`, `desc`; default `"desc"` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [
      {
        "address": "12 MG Road, Pune",
        "created_at": "2026-11-14T17:33:47Z",
        "email": "priya@example.com",
        "image_url": null,
        "is_approved": true,
        "is_blocked": false,
        "is_deleted": false,
        "name": "Priya Sharma",
        "phone_number": "+919811111111",
        "pin_code": "411001",
        "role": "user",
        "user_id": "UID_06ade2a9b763"
      }
    ],
    "message": "Users fetched successfully",
    "pagination": {
      "limit": 2,
      "offset": 0,
      "total": 1
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "Invalid query parameters", "code": "VALIDATION_ERROR", "fields": {"is_approved": "must be true or false"}}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** Admin only. `updated_since` filters by account creation time (Users has no updated_at column). Deleted users hidden unless `include_deleted=true`.

### 11. POST /api/v1/users

- **Role/auth:** public (no token)
- **Purpose:** Customer signup (role is always `user`; account starts unapproved)
- **Headers:** `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `name` | string | required | min length 1; max length 200 |
  | `address` | string | optional | max length 500 |
  | `email` | string (email) | required | max length 200 |
  | `phone_number` | string | optional | pattern `^\+?[0-9]{7,15}$` |
  | `pin_code` | string | optional | pattern `^[0-9]{4,10}$` |
  | `image` | string (binary) | optional | multipart only; jpeg/png/webp |
  | `password` | string | required | min length 8; max length 128 |
  Example:
  ```json
  {
    "name": "Priya Sharma",
    "email": "priya@example.com",
    "password": "Priya#2026",
    "phone_number": "+919811111111",
    "address": "12 MG Road, Pune",
    "pin_code": "411001"
  }
  ```
- **Success:** HTTP 201
  ```json
  {
    "data": {
      "address": "12 MG Road, Pune",
      "created_at": "2026-11-14T17:33:47Z",
      "email": "priya@example.com",
      "image_url": null,
      "is_approved": false,
      "is_blocked": false,
      "is_deleted": false,
      "name": "Priya Sharma",
      "phone_number": "+919811111111",
      "pin_code": "411001",
      "role": "user",
      "user_id": "UID_06ade2a9b763"
    },
    "message": "Account created. An admin must approve it before you can log in.",
    "status": 201
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"email": "must be a valid email address", "password": "must be at least 8 characters"}, "message": "Validation failed", "status": 400}` |
  | 409 | `CONFLICT` | `{"code": "CONFLICT", "fields": {"email": "already registered"}, "message": "Email already registered", "status": 409}` |
  | 415 | `UNSUPPORTED_MEDIA_TYPE` | `{"status": 415, "message": "Unsupported file type", "code": "UNSUPPORTED_MEDIA_TYPE", "fields": {"image": "allowed types: image/jpeg, image/png, image/webp"}}` |
- **Notes:** Public signup. Role is always `user`; an `Admin` header is ignored; `role`/`is_approved`/`is_blocked`/`image_url` fields are rejected (400). Account starts unapproved: login returns 403 ACCOUNT_NOT_APPROVED until an admin approves. Optional `image` file (multipart). 201 + `Location`. `Location` header example: `http://localhost/api/v1/users/UID_06ade2a9b763`.

### 12. GET /api/v1/users/me

- **Role/auth:** user (Bearer access token)
- **Purpose:** Own customer profile
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path/query params:** none
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "address": "12 MG Road, Pune",
      "created_at": "2026-11-14T17:33:47Z",
      "email": "priya@example.com",
      "image_url": null,
      "is_approved": true,
      "is_blocked": false,
      "is_deleted": false,
      "name": "Priya Sharma",
      "phone_number": "+919811111111",
      "pin_code": "411001",
      "role": "user",
      "user_id": "UID_06ade2a9b763"
    },
    "message": "Profile fetched successfully",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"code": "TOKEN_EXPIRED", "message": "Token has expired", "status": 401}` |
  | 401 | `TOKEN_INVALID` | `{"code": "TOKEN_INVALID", "message": "Invalid token", "status": 401}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"code": "FORBIDDEN", "message": "Only customer accounts have a /users/me profile; admins use /admins/{admin_id}", "status": 403}` |
- **Notes:** Customer tokens only (admin tokens -> 403 FORBIDDEN).

### 13. PATCH /api/v1/users/me

- **Role/auth:** user (Bearer access token)
- **Purpose:** Update own profile (name, address, phone_number, pin_code; email/password need current_password)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `name` | string | optional | min length 1; max length 200 |
  | `address` | string | optional | max length 500 |
  | `email` | string (email) | optional | max length 200 |
  | `phone_number` | string | optional | pattern `^\+?[0-9]{7,15}$` |
  | `pin_code` | string | optional | pattern `^[0-9]{4,10}$` |
  | `image` | string (binary) | optional | multipart only; jpeg/png/webp |
  | `password` | string | optional | min length 8; max length 128 |
  | `current_password` | string | optional | required when email or password changes |
  Example:
  ```json
  {
    "address": "14 MG Road, Pune",
    "pin_code": "411002"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "address": "14 MG Road, Pune",
      "created_at": "2026-11-14T17:33:47Z",
      "email": "priya@example.com",
      "image_url": null,
      "is_approved": true,
      "is_blocked": false,
      "is_deleted": false,
      "name": "Priya Sharma",
      "phone_number": "+919811111111",
      "pin_code": "411002",
      "role": "user",
      "user_id": "UID_06ade2a9b763"
    },
    "message": "Profile updated",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"current_password": "required to change email or password"}, "message": "Validation failed", "status": 400}` |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"role": "cannot be changed here"}, "message": "Validation failed", "status": 400}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 409 | `CONFLICT` | `{"status": 409, "message": "Email already registered", "code": "CONFLICT", "fields": {"email": "already registered"}}` |
- **Notes:** Whitelist: name, address, phone_number, pin_code, image (multipart). Changing `email` or `password` requires `current_password`. Protected fields (role, is_approved, is_blocked, user_id, ...) -> 400.

### 14. GET /api/v1/users/{user_id}

- **Role/auth:** admin, user (Bearer access token)
- **Purpose:** Get a user (admin: any; user: own id only, else 404)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `user_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "address": "12 MG Road, Pune",
      "created_at": "2026-11-14T17:33:47Z",
      "email": "priya@example.com",
      "image_url": null,
      "is_approved": true,
      "is_blocked": false,
      "is_deleted": false,
      "name": "Priya Sharma",
      "phone_number": "+919811111111",
      "pin_code": "411001",
      "role": "user",
      "user_id": "UID_06ade2a9b763"
    },
    "message": "User fetched successfully",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "User not found", "status": 404}` |
- **Notes:** A user may read only their own id; other ids -> 404 NOT_FOUND. Admins also see soft-deleted users.

### 15. PATCH /api/v1/users/{user_id}

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Admin edits a user's profile fields
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path params:** `user_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `name` | string | optional | min length 1; max length 200 |
  | `address` | string | optional | max length 500 |
  | `email` | string (email) | optional | max length 200 |
  | `phone_number` | string | optional | pattern `^\+?[0-9]{7,15}$` |
  | `pin_code` | string | optional | pattern `^[0-9]{4,10}$` |
  | `image` | string (binary) | optional | multipart only; jpeg/png/webp |
  Example:
  ```json
  {
    "name": "Priya S"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "address": "14 MG Road, Pune",
      "created_at": "2026-11-14T17:33:47Z",
      "email": "priya@example.com",
      "image_url": null,
      "is_approved": true,
      "is_blocked": false,
      "is_deleted": false,
      "name": "Priya S",
      "phone_number": "+919811111111",
      "pin_code": "411002",
      "role": "user",
      "user_id": "UID_06ade2a9b763"
    },
    "message": "User updated",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"is_approved": "use the approve/block/unblock actions or the password-reset flow"}, "message": "Validation failed", "status": 400}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"code": "FORBIDDEN", "message": "Access Forbidden", "status": 403}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "User not found", "code": "NOT_FOUND"}` |
  | 409 | `CONFLICT` | `{"status": 409, "message": "Email already registered", "code": "CONFLICT", "fields": {"email": "already registered"}}` |
- **Notes:** Admin only. Password and status fields are rejected (use approve/block/unblock or the password-reset flow). Audited `user.update`.

### 16. DELETE /api/v1/users/{user_id}

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Soft-delete a user (role=deleted, blocked)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `user_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "address": "14 MG Road, Pune",
      "created_at": "2026-11-14T17:33:47Z",
      "email": "priya@example.com",
      "image_url": null,
      "is_approved": true,
      "is_blocked": true,
      "is_deleted": true,
      "name": "Priya S",
      "phone_number": "+919811111111",
      "pin_code": "411002",
      "role": "user",
      "user_id": "UID_06ade2a9b763"
    },
    "message": "User deleted",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "User not found", "status": 404}` |
- **Notes:** Soft delete (role=deleted, blocked). Repeating -> 404. Audited `user.delete`.

### 17. POST /api/v1/users/{user_id}/approve

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Approve a customer account
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `user_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "address": "12 MG Road, Pune",
      "created_at": "2026-11-14T17:33:47Z",
      "email": "priya@example.com",
      "image_url": null,
      "is_approved": true,
      "is_blocked": false,
      "is_deleted": false,
      "name": "Priya Sharma",
      "phone_number": "+919811111111",
      "pin_code": "411001",
      "role": "user",
      "user_id": "UID_06ade2a9b763"
    },
    "message": "User approved",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "User not found", "status": 404}` |
- **Notes:** Sets is_approved=true. Audited.

### 18. POST /api/v1/users/{user_id}/block

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Block a customer (login and refresh rejected)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `user_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "address": "14 MG Road, Pune",
      "created_at": "2026-11-14T17:33:47Z",
      "email": "priya@example.com",
      "image_url": null,
      "is_approved": true,
      "is_blocked": true,
      "is_deleted": false,
      "name": "Priya S",
      "phone_number": "+919811111111",
      "pin_code": "411002",
      "role": "user",
      "user_id": "UID_06ade2a9b763"
    },
    "message": "User blocked",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "User not found", "code": "NOT_FOUND"}` |
- **Notes:** Sets is_blocked=true; login and refresh then return 403 ACCOUNT_BLOCKED. Audited.

### 19. POST /api/v1/users/{user_id}/unblock

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Unblock a customer
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `user_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "address": "14 MG Road, Pune",
      "created_at": "2026-11-14T17:33:47Z",
      "email": "priya@example.com",
      "image_url": null,
      "is_approved": true,
      "is_blocked": false,
      "is_deleted": false,
      "name": "Priya S",
      "phone_number": "+919811111111",
      "pin_code": "411002",
      "role": "user",
      "user_id": "UID_06ade2a9b763"
    },
    "message": "User unblocked",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "User not found", "code": "NOT_FOUND"}` |
- **Notes:** Sets is_blocked=false. Audited.

#### Admins

### 20. GET /api/v1/admins

- **Role/auth:** admin (Bearer access token)
- **Purpose:** List admins (paginated; deleted admins hidden)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `q` | string | - | matches name or email |
  | `role` | string | one of `admin`, `disabled` | - |
  | `is_approved` | boolean | `true` / `false` | `false` = self-registered admins awaiting approval |
  | `limit` | integer | min 1; max 100; default `20` | - |
  | `offset` | integer | min 0; default `0` | - |
  | `sort` | string | one of `created_at`, `name`; default `"name"` | - |
  | `order` | string | one of `asc`, `desc`; default `"asc"` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [
      {
        "admin_id": "AID_68e297784b96",
        "created_at": "2026-11-14T17:33:46Z",
        "email": "asha@pharmacy.in",
        "image_url": null,
        "is_active": true,
        "is_approved": true,
        "is_owner": false,
        "name": "Asha Admin",
        "phone_number": "+919800000001",
        "role": "admin"
      }
    ],
    "message": "Admins fetched successfully",
    "pagination": {
      "limit": 2,
      "offset": 0,
      "total": 2
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "Invalid query parameters", "code": "VALIDATION_ERROR", "fields": {"role": "must be one of: admin, disabled"}}` |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"is_approved": "must be true or false"}, "message": "Invalid query parameters", "status": 400}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `UNAUTHORIZED` | `{"code": "UNAUTHORIZED", "message": "Missing or malformed authorization token", "status": 401}` |
  | 403 | `FORBIDDEN` | `{"code": "FORBIDDEN", "message": "Access Forbidden", "status": 403}` |
- **Notes:** Deleted admins are hidden. Pending-approvals screen: `GET /api/v1/admins?is_approved=false`. Every admin object includes `is_approved` and `is_owner`.

### 21. POST /api/v1/admins

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Create an admin
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `name` | string | required | min length 1; max length 200 |
  | `email` | string (email) | required | max length 200 |
  | `phone_number` | string | optional | pattern `^\+?[0-9]{7,15}$` |
  | `password` | string | required | min length 8; max length 128 |
  | `image` | string (binary) | optional | multipart only; jpeg/png/webp |
  Example:
  ```json
  {
    "name": "Asha Admin",
    "email": "asha@pharmacy.in",
    "password": "Secret#2026",
    "phone_number": "+919800000001"
  }
  ```
- **Success:** HTTP 201
  ```json
  {
    "data": {
      "admin_id": "AID_68e297784b96",
      "created_at": "2026-11-14T17:33:46Z",
      "email": "asha@pharmacy.in",
      "image_url": null,
      "is_active": true,
      "is_approved": true,
      "is_owner": false,
      "name": "Asha Admin",
      "phone_number": "+919800000001",
      "role": "admin"
    },
    "message": "Admin created",
    "status": 201
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"email": "must be a valid email address", "name": "is required", "password": "must be at least 8 characters"}, "message": "Validation failed", "status": 400}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 409 | `CONFLICT` | `{"code": "CONFLICT", "fields": {"email": "already registered"}, "message": "Email already registered", "status": 409}` |
- **Notes:** Optional `image` file (multipart). 201 + `Location`. Admins created here are approved (`is_approved: true`) and never the owner; `is_approved`/`is_owner` in the body -> 400. Audited `admin.create`. `Location` header example: `http://localhost/api/v1/admins/AID_68e297784b96`.

### 22. GET /api/v1/admins/{admin_id}

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Get an admin
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `admin_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "admin_id": "AID_68e297784b96",
      "created_at": "2026-11-14T17:33:46Z",
      "email": "asha@pharmacy.in",
      "image_url": null,
      "is_active": true,
      "is_approved": true,
      "is_owner": false,
      "name": "Asha Admin",
      "phone_number": "+919800000001",
      "role": "admin"
    },
    "message": "Admin fetched successfully",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "Admin not found", "status": 404}` |
- **Notes:** -

### 23. PATCH /api/v1/admins/{admin_id}

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Update an admin (email/password: owner only, with current_password; role=disabled demotes)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path params:** `admin_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `name` | string | optional | min length 1; max length 200 |
  | `email` | string (email) | optional | max length 200 |
  | `phone_number` | string | optional | pattern `^\+?[0-9]{7,15}$` |
  | `password` | string | optional | min length 8; max length 128 |
  | `image` | string (binary) | optional | multipart only; jpeg/png/webp |
  | `role` | string | optional | one of `admin`, `disabled` |
  | `current_password` | string | optional | required when you change your own email/password |
  Example:
  ```json
  {
    "name": "Asha K"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "admin_id": "AID_68e297784b96",
      "created_at": "2026-11-14T17:33:46Z",
      "email": "asha@pharmacy.in",
      "image_url": null,
      "is_active": true,
      "is_approved": true,
      "is_owner": false,
      "name": "Asha K",
      "phone_number": "+919800000001",
      "role": "admin"
    },
    "message": "Admin updated",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"password": "only the account owner can change this"}, "message": "Validation failed", "status": 400}` |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"current_password": "required to change email or password"}, "message": "Validation failed", "status": 400}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 403 | `FORBIDDEN` | `{"code": "FORBIDDEN", "message": "Owner account is protected", "status": 403}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "Admin not found", "code": "NOT_FOUND"}` |
  | 409 | `CONFLICT` | `{"code": "CONFLICT", "message": "At least one approved admin is required", "status": 409}` |
- **Notes:** Only the account itself can change its email/password (with `current_password`). `role=disabled` demotes (blocks). The owner (`is_owner: true`) cannot be demoted (403), and neither can the last approved, active admin (409). `is_approved` cannot be set here (400; use `POST /admins/{admin_id}/approve`) and `is_owner` cannot be changed. Audited.

### 24. DELETE /api/v1/admins/{admin_id}

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Soft-delete an admin (not the owner, not the last approved admin)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `admin_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "admin_id": "AID_664fc2b97efc",
      "created_at": "2026-11-14T17:33:47Z",
      "email": "ravi@pharmacy.in",
      "image_url": null,
      "is_active": false,
      "is_approved": true,
      "is_owner": false,
      "name": "Ravi Admin",
      "phone_number": null,
      "role": "deleted"
    },
    "message": "Admin deleted",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 403 | `FORBIDDEN` | `{"code": "FORBIDDEN", "message": "Owner account is protected", "status": 403}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "Admin not found", "code": "NOT_FOUND"}` |
  | 409 | `CONFLICT` | `{"code": "CONFLICT", "message": "At least one approved admin is required", "status": 409}` |
- **Notes:** Soft delete (role=deleted). The owner cannot be deleted (403 FORBIDDEN) and neither can the last approved, active admin (409 CONFLICT). Also use this to reject a pending (unapproved) admin signup. Audited.

### 25. POST /api/v1/admins/register

- **Role/auth:** public (no token)
- **Purpose:** Admin self-signup for the admin app's "Create account" screen. The first admin on an empty database is created approved and becomes the owner; every later admin is created unapproved.
- **Headers:** `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data` (multipart is required to send `image`)
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `name` | string | required | min length 1; max length 200 |
  | `email` | string (email) | required | valid email; max length 200; unique among admins (case-insensitive) |
  | `password` | string | required | min length 8; max length 128 (stored hashed) |
  | `phone_number` | string | optional | pattern `^\+?[0-9]{7,15}$`; unique among admins |
  | `image` | string (binary) | optional | multipart only; jpeg/png/webp; same size/type rules as other images |
  | `signup_code` | string | conditional | max length 200; required and must match when the server sets `ADMIN_SIGNUP_CODE` (`app-config` -> `admin_signup.code_required`) |
  | `role`, `is_approved`, `is_blocked`, `is_owner`, `is_active`, `admin_id`, `image_url` | - | rejected | 400 `VALIDATION_ERROR` "cannot be set at signup" |
  Example:
  ```json
  {
    "name": "Ravi Admin",
    "email": "ravi@pharmacy.in",
    "password": "Secret#2026",
    "signup_code": "<ADMIN_SIGNUP_CODE>"
  }
  ```
- **Success:** HTTP 201 (first admin on an empty database)
  ```json
  {
    "data": {
      "admin_id": "AID_7c3fdc30b2b7",
      "created_at": "2026-11-15T13:30:40Z",
      "email": "asha@pharmacy.in",
      "image_url": null,
      "is_active": true,
      "is_approved": true,
      "is_owner": true,
      "name": "Asha Admin",
      "phone_number": "+919800000001",
      "role": "admin"
    },
    "message": "Admin registered.",
    "status": 201
  }
  ```
  HTTP 201 (any later signup)
  ```json
  {
    "data": {
      "admin_id": "AID_6edcd98811a4",
      "created_at": "2026-11-15T13:30:41Z",
      "email": "ravi@pharmacy.in",
      "image_url": null,
      "is_active": true,
      "is_approved": false,
      "is_owner": false,
      "name": "Ravi Admin",
      "phone_number": null,
      "role": "admin"
    },
    "message": "Admin registered. Awaiting approval.",
    "status": 201
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"email": "must be a valid email address", "is_approved": "cannot be set at signup", "name": "is required", "password": "must be at least 8 characters", "role": "cannot be set at signup"}, "message": "Validation failed", "status": 400}` |
  | 403 | `FORBIDDEN` | `{"code": "FORBIDDEN", "message": "Invalid signup code", "status": 403}` |
  | 409 | `CONFLICT` | `{"code": "CONFLICT", "fields": {"email": "already registered"}, "message": "Email already registered", "status": 409}` |
  | 413 | `PAYLOAD_TOO_LARGE` | `{"status": 413, "message": "File too large", "code": "PAYLOAD_TOO_LARGE", "fields": {"image": "max 5 MB"}}` (unverified) |
  | 415 | `UNSUPPORTED_MEDIA_TYPE` | `{"status": 415, "message": "Unsupported file type", "code": "UNSUPPORTED_MEDIA_TYPE", "fields": {"image": "allowed types: image/jpeg, image/png, image/webp"}}` (unverified) |
  | 429 | `RATE_LIMITED` | `{"code": "RATE_LIMITED", "message": "Too many attempts; try again later", "status": 429}` (header `Retry-After: 3598`) |
- **Notes:** 201 + `Location` (e.g. `http://localhost/api/v1/admins/AID_6edcd98811a4`); `data` is the same admin object as `POST /admins`. No tokens are issued: send the user to the login screen after signup. When `is_approved` is `false`, show "awaiting approval"; login returns 403 `ACCOUNT_NOT_APPROVED` until an admin approves the account. Checks run in this order: rate limit (429), validation (400), signup code (403), duplicate (409), image (413/415). The first-admin check and the insert run in one locked transaction, so there is at most one owner. Rate-limited per client IP (`ADMIN_SIGNUP_RATE_LIMIT` per `ADMIN_SIGNUP_RATE_WINDOW_SECONDS`, default 10 per hour). Audited `admin.register`; the password and signup code are never logged. See "Admin signup, owner and server settings" in section 1.

### 26. POST /api/v1/admins/{admin_id}/approve

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Approve a self-registered admin so it can log in
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `admin_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "admin_id": "AID_6edcd98811a4",
      "created_at": "2026-11-15T13:30:41Z",
      "email": "ravi@pharmacy.in",
      "image_url": null,
      "is_active": true,
      "is_approved": true,
      "is_owner": false,
      "name": "Ravi Admin",
      "phone_number": null,
      "role": "admin"
    },
    "message": "Admin approved",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "Admin not found", "status": 404}` |
- **Notes:** Sets `is_approved=true`. Idempotent: approving an already-approved admin returns 200. Deleted admins return 404. Mirrors `POST /users/{user_id}/approve`. To reject a pending signup, use `DELETE /api/v1/admins/{admin_id}`. Audited `admin.approve`.

#### Devices

### 27. POST /api/v1/devices

- **Role/auth:** admin, user (Bearer access token)
- **Purpose:** Register or update this device's push token (upsert on token)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `token` | string | required | min length 8; max length 4096; FCM/APNs push token |
  | `platform` | string | required | one of `android`, `ios` |
  | `app_version` | string | optional | max length 32 |
  Example:
  ```json
  {
    "token": "fcm-token-abc123456",
    "platform": "android",
    "app_version": "1.4.0"
  }
  ```
- **Success:** HTTP 201
  ```json
  {
    "data": {
      "app_version": "1.4.0",
      "created_at": "2026-11-14T17:33:50Z",
      "device_id": "DEV_b15c145f32af",
      "is_active": true,
      "platform": "android",
      "updated_at": "2026-11-14T17:33:50Z",
      "user_id": "UID_06ade2a9b763"
    },
    "message": "Device registered",
    "status": 201
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"platform": "must be one of: android, ios", "token": "must be at least 8 characters"}, "message": "Validation failed", "status": 400}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
- **Notes:** Upsert on `token`: new token -> 201 'Device registered'; existing token -> 200 'Device updated' (re-assigned to the caller, re-activated). Storage only; push sending is not implemented yet. `Location` header example: `http://localhost/api/v1/devices/DEV_b15c145f32af`.

### 28. DELETE /api/v1/devices/{device_id}

- **Role/auth:** admin, user (Bearer access token)
- **Purpose:** Unregister one of your devices (soft delete: is_active=false)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `device_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "app_version": "1.5.0",
      "created_at": "2026-11-14T17:33:50Z",
      "device_id": "DEV_b15c145f32af",
      "is_active": false,
      "platform": "android",
      "updated_at": "2026-11-14T17:33:50Z",
      "user_id": "UID_06ade2a9b763"
    },
    "message": "Device unregistered",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "Device not found", "status": 404}` |
- **Notes:** Own devices only; other users' or already-removed devices -> 404. Soft delete (is_active=false).

#### Products

### 29. GET /api/v1/product-categories

- **Role/auth:** admin, user (Bearer access token)
- **Purpose:** List categories with product counts
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `sort` | string | one of `name`, `product_count`; default `"name"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [
      {
        "name": "Analgesic",
        "product_count": 1
      }
    ],
    "message": "Categories fetched successfully",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 2
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** -

### 30. GET /api/v1/products

- **Role/auth:** admin, user (Bearer access token)
- **Purpose:** List products
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `q` | string | - | matches name, generic_name, brand_name, barcode |
  | `category` | string | - | - |
  | `schedule_type` | string | one of `OTC`, `H`, `H1`, `X`, `NARCOTIC` | - |
  | `requires_prescription` | boolean | - | - |
  | `is_active` | boolean | - | admin only; users always get active products |
  | `in_stock` | boolean | - | - |
  | `updated_since` | string (date-time) | - | - |
  | `sort` | string | one of `name`, `price`, `mrp`, `stock`, `created_at`, `updated_at`; default `"name"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [
      {
        "barcode": "",
        "brand_name": "",
        "category": "General",
        "created_at": "2026-11-14T17:33:50Z",
        "dosage_form": "Tablet",
        "generic_name": "",
        "gst_percent": 12.0,
        "hsn_code": "",
        "image_url": null,
        "in_stock": false,
        "is_active": true,
        "manufacturer": "Unknown",
        "mrp": 125.0,
        "name": "Azithromycin 500mg",
        "pack_size": "",
        "price": 120.0,
        "product_id": "PROD_20f28a6512",
        "purchase_price": null,
        "reorder_level": 10,
        "requires_prescription": true,
        "schedule_type": "H",
        "sellable_stock": 0,
        "stock": 0,
        "storage_conditions": "",
        "strength": "",
        "unit": "strip",
        "updated_at": "2026-11-14T17:33:50Z"
      }
    ],
    "message": "Products fetched successfully",
    "pagination": {
      "limit": 2,
      "offset": 0,
      "total": 2
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 426 | `UPGRADE_REQUIRED` | `{"code": "UPGRADE_REQUIRED", "fields": {"X-App-Version": "minimum supported version is 2.0.0"}, "message": "This app version is no longer supported; please update.", "status": 426}` |
- **Notes:** Users see active products only and `purchase_price` is null for them.

### 31. POST /api/v1/products

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Create product (stock starts at 0)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `name` | string | required | max length 200 |
  | `generic_name` | string | optional | - |
  | `brand_name` | string | optional | - |
  | `manufacturer` | string | optional | - |
  | `category` | string | optional | - |
  | `dosage_form` | string | optional | - |
  | `strength` | string | optional | - |
  | `pack_size` | string | optional | - |
  | `unit` | string | optional | - |
  | `hsn_code` | string | optional | pattern `^[0-9]{4,8}$` |
  | `gst_percent` | number | optional | min 0; max 28 |
  | `price` | number | required | min 0 |
  | `mrp` | number | optional | min 0 |
  | `purchase_price` | number | optional | min 0 |
  | `schedule_type` | string | optional | - |
  | `requires_prescription` | boolean | optional | forced true for H/H1/X/NARCOTIC |
  | `storage_conditions` | string | optional | - |
  | `reorder_level` | integer | optional | min 0 |
  | `barcode` | string | optional | - |
  | `image` | string (binary) | optional | multipart only; jpeg/png/webp |
  Example:
  ```json
  {
    "name": "Paracetamol 500mg",
    "generic_name": "Paracetamol",
    "brand_name": "Calpol",
    "manufacturer": "GSK",
    "category": "Analgesic",
    "dosage_form": "Tablet",
    "strength": "500mg",
    "pack_size": "15 tablets",
    "unit": "strip",
    "hsn_code": "3004",
    "gst_percent": 12,
    "price": 30,
    "mrp": 32,
    "purchase_price": 22,
    "reorder_level": 10,
    "barcode": "8901234567890"
  }
  ```
- **Success:** HTTP 201
  ```json
  {
    "data": {
      "barcode": "8901234567890",
      "brand_name": "Calpol",
      "category": "Analgesic",
      "created_at": "2026-11-14T17:33:50Z",
      "dosage_form": "Tablet",
      "generic_name": "Paracetamol",
      "gst_percent": 12.0,
      "hsn_code": "3004",
      "image_url": null,
      "in_stock": false,
      "is_active": true,
      "manufacturer": "GSK",
      "mrp": 32.0,
      "name": "Paracetamol 500mg",
      "pack_size": "15 tablets",
      "price": 30.0,
      "product_id": "PROD_c7a36281e0",
      "purchase_price": 22.0,
      "reorder_level": 10,
      "requires_prescription": false,
      "schedule_type": "OTC",
      "sellable_stock": 0,
      "stock": 0,
      "storage_conditions": "",
      "strength": "500mg",
      "unit": "strip",
      "updated_at": "2026-11-14T17:33:50Z"
    },
    "message": "Product created",
    "status": 201
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"name": "is required", "price": "must be >= 0"}, "message": "Validation failed", "status": 400}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 409 | `CONFLICT` | `{"code": "CONFLICT", "fields": {"barcode": "already in use"}, "message": "Barcode already assigned to another product", "status": 409}` |
  | 413 | `PAYLOAD_TOO_LARGE` | `{"status": 413, "message": "...", "code": "PAYLOAD_TOO_LARGE"}` (unverified) |
  | 415 | `UNSUPPORTED_MEDIA_TYPE` | `{"status": 415, "message": "...", "code": "UNSUPPORTED_MEDIA_TYPE"}` (unverified) |
- **Notes:** `requires_prescription` is forced true for schedules H/H1/X/NARCOTIC. Duplicate barcode -> 409. Optional `image` file (multipart). 201 + `Location`. `Location` header example: `http://localhost/api/v1/products/PROD_c7a36281e0`.

### 32. GET /api/v1/products/by-barcode/{barcode}

- **Role/auth:** admin, user (Bearer access token)
- **Purpose:** Look up product by barcode
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `barcode` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "barcode": "8901234567890",
      "brand_name": "Calpol",
      "category": "Analgesic",
      "created_at": "2026-11-14T17:33:50Z",
      "dosage_form": "Tablet",
      "generic_name": "Paracetamol",
      "gst_percent": 12.0,
      "hsn_code": "3004",
      "image_url": null,
      "in_stock": false,
      "is_active": true,
      "manufacturer": "GSK",
      "mrp": 32.0,
      "name": "Paracetamol 500mg",
      "pack_size": "15 tablets",
      "price": 31.0,
      "product_id": "PROD_c7a36281e0",
      "purchase_price": null,
      "reorder_level": 12,
      "requires_prescription": false,
      "schedule_type": "OTC",
      "sellable_stock": 0,
      "stock": 0,
      "storage_conditions": "",
      "strength": "500mg",
      "unit": "strip",
      "updated_at": "2026-11-14T17:33:50Z"
    },
    "message": "Product fetched successfully",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "No product with this barcode", "status": 404}` |
- **Notes:** -

### 33. GET /api/v1/products/{product_id}

- **Role/auth:** admin, user (Bearer access token)
- **Purpose:** Get product (users: active only)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `product_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "barcode": "8901234567890",
      "brand_name": "Calpol",
      "category": "Analgesic",
      "created_at": "2026-11-14T17:33:50Z",
      "dosage_form": "Tablet",
      "generic_name": "Paracetamol",
      "gst_percent": 12.0,
      "hsn_code": "3004",
      "image_url": null,
      "in_stock": false,
      "is_active": true,
      "manufacturer": "GSK",
      "mrp": 32.0,
      "name": "Paracetamol 500mg",
      "pack_size": "15 tablets",
      "price": 30.0,
      "product_id": "PROD_c7a36281e0",
      "purchase_price": 22.0,
      "reorder_level": 10,
      "requires_prescription": false,
      "schedule_type": "OTC",
      "sellable_stock": 0,
      "stock": 0,
      "storage_conditions": "",
      "strength": "500mg",
      "unit": "strip",
      "updated_at": "2026-11-14T17:33:50Z"
    },
    "message": "Product fetched successfully",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "Product not found", "status": 404}` |
- **Notes:** -

### 34. PATCH /api/v1/products/{product_id}

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Partially update product
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path params:** `product_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `name` | string | required | max length 200 |
  | `generic_name` | string | optional | - |
  | `brand_name` | string | optional | - |
  | `manufacturer` | string | optional | - |
  | `category` | string | optional | - |
  | `dosage_form` | string | optional | - |
  | `strength` | string | optional | - |
  | `pack_size` | string | optional | - |
  | `unit` | string | optional | - |
  | `hsn_code` | string | optional | pattern `^[0-9]{4,8}$` |
  | `gst_percent` | number | optional | min 0; max 28 |
  | `price` | number | required | min 0 |
  | `mrp` | number | optional | min 0 |
  | `purchase_price` | number | optional | min 0 |
  | `schedule_type` | string | optional | - |
  | `requires_prescription` | boolean | optional | forced true for H/H1/X/NARCOTIC |
  | `storage_conditions` | string | optional | - |
  | `reorder_level` | integer | optional | min 0 |
  | `barcode` | string | optional | - |
  | `image` | string (binary) | optional | multipart only; jpeg/png/webp |
  Example:
  ```json
  {
    "price": 31,
    "reorder_level": 12
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "barcode": "8901234567890",
      "brand_name": "Calpol",
      "category": "Analgesic",
      "created_at": "2026-11-14T17:33:50Z",
      "dosage_form": "Tablet",
      "generic_name": "Paracetamol",
      "gst_percent": 12.0,
      "hsn_code": "3004",
      "image_url": null,
      "in_stock": false,
      "is_active": true,
      "manufacturer": "GSK",
      "mrp": 32.0,
      "name": "Paracetamol 500mg",
      "pack_size": "15 tablets",
      "price": 31.0,
      "product_id": "PROD_c7a36281e0",
      "purchase_price": 22.0,
      "reorder_level": 12,
      "requires_prescription": false,
      "schedule_type": "OTC",
      "sellable_stock": 0,
      "stock": 0,
      "storage_conditions": "",
      "strength": "500mg",
      "unit": "strip",
      "updated_at": "2026-11-14T17:33:50Z"
    },
    "message": "Product updated",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"code": "FORBIDDEN", "message": "Access Forbidden", "status": 403}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `CONFLICT` | `{"status": 409, "message": "...", "code": "CONFLICT"}` (unverified) |
  | 415 | `UNSUPPORTED_MEDIA_TYPE` | `{"status": 415, "message": "...", "code": "UNSUPPORTED_MEDIA_TYPE"}` (unverified) |
- **Notes:** -

### 35. POST /api/v1/products/{product_id}/deactivate

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Soft-deactivate product
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `product_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "barcode": "",
      "brand_name": "",
      "category": "General",
      "created_at": "2026-11-14T17:33:50Z",
      "dosage_form": "Tablet",
      "generic_name": "",
      "gst_percent": 12.0,
      "hsn_code": "",
      "image_url": null,
      "in_stock": true,
      "is_active": false,
      "manufacturer": "Unknown",
      "mrp": 125.0,
      "name": "Azithromycin 500mg",
      "pack_size": "",
      "price": 120.0,
      "product_id": "PROD_20f28a6512",
      "purchase_price": 0.0,
      "reorder_level": 10,
      "requires_prescription": true,
      "schedule_type": "H",
      "sellable_stock": 20,
      "stock": 20,
      "storage_conditions": "",
      "strength": "",
      "unit": "strip",
      "updated_at": "2026-11-14T17:33:51Z"
    },
    "message": "Product deactivated",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `CONFLICT` | `{"code": "CONFLICT", "message": "Product is already inactive", "status": 409}` |
- **Notes:** Soft delete (is_active=false); already inactive -> 409.

### 36. POST /api/v1/products/{product_id}/reactivate

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Reactivate product
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `product_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "barcode": "",
      "brand_name": "",
      "category": "General",
      "created_at": "2026-11-14T17:33:50Z",
      "dosage_form": "Tablet",
      "generic_name": "",
      "gst_percent": 12.0,
      "hsn_code": "",
      "image_url": null,
      "in_stock": true,
      "is_active": true,
      "manufacturer": "Unknown",
      "mrp": 125.0,
      "name": "Azithromycin 500mg",
      "pack_size": "",
      "price": 120.0,
      "product_id": "PROD_20f28a6512",
      "purchase_price": 0.0,
      "reorder_level": 10,
      "requires_prescription": true,
      "schedule_type": "H",
      "sellable_stock": 20,
      "stock": 20,
      "storage_conditions": "",
      "strength": "",
      "unit": "strip",
      "updated_at": "2026-11-14T17:33:51Z"
    },
    "message": "Product reactivated",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `CONFLICT` | `{"status": 409, "message": "...", "code": "CONFLICT"}` (unverified) |
- **Notes:** Already active -> 409.

#### Batches & stock

### 37. GET /api/v1/batches/{batch_id}

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Get batch
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `batch_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "batch_id": "BAT_2cceba2ef4f8",
      "batch_no": "B-2026-01",
      "created_at": "2026-11-14T17:33:50Z",
      "days_to_expiry": 594,
      "expiry_date": "2028-06-30",
      "is_expired": false,
      "is_legacy_placeholder": false,
      "mfg_date": "2026-01-10",
      "mrp": 32.0,
      "product_id": "PROD_c7a36281e0",
      "product_name": "Paracetamol 500mg",
      "purchase_price": 22.0,
      "quantity": 5,
      "received_date": "2026-11-14",
      "supplier_id": null,
      "supplier_name": "",
      "updated_at": "2026-11-14T17:33:50Z"
    },
    "message": "Batch fetched successfully",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "Batch not found", "status": 404}` |
- **Notes:** -

### 38. PATCH /api/v1/batches/{batch_id}

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Update batch metadata (not quantity); fixing a legacy expiry clears the placeholder flag
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path params:** `batch_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `batch_no` | string | required | - |
  | `expiry_date` | string (date) | required | - |
  | `mfg_date` | string (date) | optional | - |
  | `received_date` | string (date) | optional | - |
  | `quantity` | integer | optional | min 0 |
  | `purchase_price` | number | optional | - |
  | `mrp` | number | optional | - |
  | `supplier_id` | string | optional | - |
  | `supplier_name` | string | optional | - |
  Example:
  ```json
  {
    "mrp": 33
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "batch_id": "BAT_2cceba2ef4f8",
      "batch_no": "B-2026-01",
      "created_at": "2026-11-14T17:33:50Z",
      "days_to_expiry": 594,
      "expiry_date": "2028-06-30",
      "is_expired": false,
      "is_legacy_placeholder": false,
      "mfg_date": "2026-01-10",
      "mrp": 33.0,
      "product_id": "PROD_c7a36281e0",
      "product_name": "Paracetamol 500mg",
      "purchase_price": 22.0,
      "quantity": 5,
      "received_date": "2026-11-14",
      "supplier_id": null,
      "supplier_name": "",
      "updated_at": "2026-11-14T17:33:50Z"
    },
    "message": "Batch updated",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"expiry_date": "must be a date in YYYY-MM-DD format"}, "message": "Validation failed", "status": 400}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `CONFLICT` | `{"status": 409, "message": "...", "code": "CONFLICT"}` (unverified) |
- **Notes:** Correcting a `LEGACY-*` placeholder batch clears `is_legacy_placeholder`.

### 39. POST /api/v1/batches/{batch_id}/write-off

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Write off the whole batch quantity (EXPIRED_WRITEOFF)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path params:** `batch_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `note` | string | optional | - |
  Example:
  ```json
  {
    "note": "damaged in storage"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "batch": {
        "batch_id": "BAT_2cceba2ef4f8",
        "batch_no": "B-2026-01",
        "created_at": "2026-11-14T17:33:50Z",
        "days_to_expiry": 594,
        "expiry_date": "2028-06-30",
        "is_expired": false,
        "is_legacy_placeholder": false,
        "mfg_date": "2026-01-10",
        "mrp": 33.0,
        "product_id": "PROD_c7a36281e0",
        "product_name": "Paracetamol 500mg",
        "purchase_price": 22.0,
        "quantity": 0,
        "received_date": "2026-11-14",
        "supplier_id": null,
        "supplier_name": "",
        "updated_at": "2026-11-14T17:33:51Z"
      },
      "movement": {
        "batch_id": "BAT_2cceba2ef4f8",
        "change_qty": -5,
        "created_at": "2026-11-14T17:33:51Z",
        "movement_id": "MOV_fff22ab775294112",
        "performed_by": "AID_root",
        "product_id": "PROD_c7a36281e0",
        "product_stock": 100,
        "reason": "EXPIRED_WRITEOFF",
        "reference_id": "WOFF_89604c5ccb"
      }
    },
    "message": "Batch written off",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `CONFLICT` | `{"code": "CONFLICT", "message": "Batch has no stock to write off", "status": 409}` |
- **Notes:** Writes off the remaining quantity (reason EXPIRED_WRITEOFF); nothing left -> 409.

### 40. GET /api/v1/products/{product_id}/batches

- **Role/auth:** admin (Bearer access token)
- **Purpose:** List batches of a product
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `product_id` (string, required)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `include_expired` | boolean | default `true` | - |
  | `in_stock` | boolean | - | - |
  | `sort` | string | one of `expiry_date`, `batch_no`, `received_date`, `quantity`, `created_at`; default `"expiry_date"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [
      {
        "batch_id": "BAT_2cceba2ef4f8",
        "batch_no": "B-2026-01",
        "created_at": "2026-11-14T17:33:50Z",
        "days_to_expiry": 594,
        "expiry_date": "2028-06-30",
        "is_expired": false,
        "is_legacy_placeholder": false,
        "mfg_date": "2026-01-10",
        "mrp": 32.0,
        "product_id": "PROD_c7a36281e0",
        "product_name": "Paracetamol 500mg",
        "purchase_price": 22.0,
        "quantity": 5,
        "received_date": "2026-11-14",
        "supplier_id": null,
        "supplier_name": "",
        "updated_at": "2026-11-14T17:33:50Z"
      }
    ],
    "message": "Batches fetched successfully",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 2
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
- **Notes:** -

### 41. POST /api/v1/products/{product_id}/batches

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Create batch (optional opening quantity -> PURCHASE movement)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path params:** `product_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `batch_no` | string | required | - |
  | `expiry_date` | string (date) | required | - |
  | `mfg_date` | string (date) | optional | - |
  | `received_date` | string (date) | optional | - |
  | `quantity` | integer | optional | min 0 |
  | `purchase_price` | number | optional | - |
  | `mrp` | number | optional | - |
  | `supplier_id` | string | optional | - |
  | `supplier_name` | string | optional | - |
  Example:
  ```json
  {
    "batch_no": "B-2026-01",
    "expiry_date": "2028-06-30",
    "mfg_date": "2026-01-10",
    "purchase_price": 22,
    "mrp": 32
  }
  ```
- **Success:** HTTP 201
  ```json
  {
    "data": {
      "batch": {
        "batch_id": "BAT_2cceba2ef4f8",
        "batch_no": "B-2026-01",
        "created_at": "2026-11-14T17:33:50Z",
        "days_to_expiry": 594,
        "expiry_date": "2028-06-30",
        "is_expired": false,
        "is_legacy_placeholder": false,
        "mfg_date": "2026-01-10",
        "mrp": 32.0,
        "product_id": "PROD_c7a36281e0",
        "product_name": "Paracetamol 500mg",
        "purchase_price": 22.0,
        "quantity": 0,
        "received_date": "2026-11-14",
        "supplier_id": null,
        "supplier_name": "",
        "updated_at": "2026-11-14T17:33:50Z"
      },
      "movement": null
    },
    "message": "Batch created",
    "status": 201
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"batch_no": "is required", "expiry_date": "is required"}, "message": "Validation failed", "status": 400}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `BATCH_EXPIRED` | `{"status": 409, "message": "...", "code": "BATCH_EXPIRED"}` (unverified) |
  | 409 | `CONFLICT` | `{"code": "CONFLICT", "fields": {"batch_no": "already exists"}, "message": "Batch number already exists for this product", "status": 409}` |
- **Notes:** Creates an empty batch (quantity 0, unless `quantity` given). Duplicate batch_no for the product -> 409. 201 + `Location`. `Location` header example: `http://localhost/api/v1/batches/BAT_2cceba2ef4f8`.

### 42. POST /api/v1/products/{product_id}/stock/adjust

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Signed stock adjustment on one batch (never below zero)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path params:** `product_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `batch_id` | string | required | - |
  | `change_qty` | integer | required | non-zero, signed |
  | `reason` | string | required | min length 3 |
  Example:
  ```json
  {
    "batch_id": "BAT_2cceba2ef4f8",
    "change_qty": 5,
    "reason": "found in shelf count"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "batch": {
        "batch_id": "BAT_2cceba2ef4f8",
        "batch_no": "B-2026-01",
        "created_at": "2026-11-14T17:33:50Z",
        "days_to_expiry": 594,
        "expiry_date": "2028-06-30",
        "is_expired": false,
        "is_legacy_placeholder": false,
        "mfg_date": "2026-01-10",
        "mrp": 32.0,
        "product_id": "PROD_c7a36281e0",
        "product_name": "Paracetamol 500mg",
        "purchase_price": 22.0,
        "quantity": 5,
        "received_date": "2026-11-14",
        "supplier_id": null,
        "supplier_name": "",
        "updated_at": "2026-11-14T17:33:50Z"
      },
      "movement": {
        "batch_id": "BAT_2cceba2ef4f8",
        "change_qty": 5,
        "created_at": "2026-11-14T17:33:50Z",
        "movement_id": "MOV_cb1df2589fbb4aaa",
        "performed_by": "AID_root",
        "product_id": "PROD_c7a36281e0",
        "product_stock": 105,
        "reason": "ADJUSTMENT",
        "reference_id": "ADJ_4b74f0edd7"
      },
      "product_stock": 105
    },
    "message": "Stock adjusted",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `OUT_OF_STOCK` | `{"code": "OUT_OF_STOCK", "message": "Batch quantity cannot go below zero", "status": 409}` |
- **Notes:** Signed `change_qty`; a result below 0 -> 409 OUT_OF_STOCK.

### 43. POST /api/v1/products/{product_id}/stock/purchase

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Receive stock: create or top up a batch (PURCHASE)
- **Headers:** `Authorization: Bearer <access_token>` (required); `Idempotency-Key` (optional, max 255 chars; replays the first response); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: application/json` or `multipart/form-data`
- **Path params:** `product_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `batch_no` | string | required | - |
  | `expiry_date` | string (date) | required | - |
  | `mfg_date` | string (date) | optional | - |
  | `received_date` | string (date) | optional | - |
  | `quantity` | integer | required | min 1 |
  | `purchase_price` | number | optional | - |
  | `mrp` | number | optional | - |
  | `supplier_id` | string | optional | - |
  | `supplier_name` | string | optional | - |
  | `invoice_no` | string | optional | - |
  Example:
  ```json
  {
    "batch_no": "B-2026-02",
    "expiry_date": "2028-12-31",
    "quantity": 100,
    "purchase_price": 22,
    "mrp": 32,
    "supplier_id": "SUP_0debfd314e",
    "invoice_no": "INV-778"
  }
  ```
- **Success:** HTTP 201
  ```json
  {
    "data": {
      "batch": {
        "batch_id": "BAT_ba0ac6d4cb92",
        "batch_no": "B-2026-02",
        "created_at": "2026-11-14T17:33:50Z",
        "days_to_expiry": 778,
        "expiry_date": "2028-12-31",
        "is_expired": false,
        "is_legacy_placeholder": false,
        "mfg_date": null,
        "mrp": 32.0,
        "product_id": "PROD_c7a36281e0",
        "product_name": "Paracetamol 500mg",
        "purchase_price": 22.0,
        "quantity": 100,
        "received_date": "2026-11-14",
        "supplier_id": "SUP_0debfd314e",
        "supplier_name": "MedSupply Pvt Ltd",
        "updated_at": "2026-11-14T17:33:50Z"
      },
      "batch_created": true,
      "movement": {
        "batch_id": "BAT_ba0ac6d4cb92",
        "change_qty": 100,
        "created_at": "2026-11-14T17:33:50Z",
        "movement_id": "MOV_916c55c85fe34f5e",
        "performed_by": "AID_root",
        "product_id": "PROD_c7a36281e0",
        "product_stock": 100,
        "reason": "PURCHASE",
        "reference_id": "INV-778"
      },
      "product_stock": 100
    },
    "message": "Stock purchased",
    "status": 201
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"batch_no": "is required", "expiry_date": "is required", "quantity": "must be >= 1"}, "message": "Validation failed", "status": 400}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `BATCH_EXPIRED` | `{"status": 409, "message": "...", "code": "BATCH_EXPIRED"}` (unverified) |
  | 409 | `CONFLICT` | `{"status": 409, "message": "...", "code": "CONFLICT"}` (unverified) |
- **Notes:** Idempotent: retries with the same `Idempotency-Key` replay the first response with header `Idempotent-Replayed: true`. Creates the batch if `batch_no` is new (`batch_created`). 201 + `Location`. `Location` header example: `http://localhost/api/v1/batches/BAT_ba0ac6d4cb92`.

### 44. GET /api/v1/stock-movements

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Stock movement ledger
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `product_id` | string | - | - |
  | `batch_id` | string | - | - |
  | `reason` | string | - | - |
  | `performed_by` | string | - | - |
  | `from` | string | - | date or date-time (inclusive) |
  | `to` | string | - | date or date-time (inclusive) |
  | `sort` | string | one of `created_at`, `change_qty`; default `"created_at"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [
      {
        "batch_id": "BAT_2cceba2ef4f8",
        "batch_no": "B-2026-01",
        "change_qty": 5,
        "created_at": "2026-11-14T17:33:50Z",
        "movement_id": "MOV_cb1df2589fbb4aaa",
        "performed_by": "AID_root",
        "product_id": "PROD_c7a36281e0",
        "product_name": "Paracetamol 500mg",
        "reason": "ADJUSTMENT",
        "reference_id": "ADJ_4b74f0edd7"
      }
    ],
    "message": "Stock movements fetched successfully",
    "pagination": {
      "limit": 2,
      "offset": 0,
      "total": 3
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** -

#### Inventory alerts

### 45. GET /api/v1/inventory/expired

- **Role/auth:** admin (Bearer access token)
- **Purpose:** In-stock batches past expiry
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `sort` | string | one of `expiry_date`, `quantity`, `product_name`; default `"expiry_date"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [],
    "message": "Expired batches fetched successfully",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 0
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** -

### 46. GET /api/v1/inventory/low-stock

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Active products with stock <= reorder_level
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `sort` | string | one of `stock`, `name`, `reorder_level`; default `"stock"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [],
    "message": "Low-stock products fetched successfully",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 0
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** -

### 47. GET /api/v1/inventory/near-expiry

- **Role/auth:** admin (Bearer access token)
- **Purpose:** In-stock batches expiring within `days`
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `days` | integer | min 1; default `90` | - |
  | `sort` | string | one of `expiry_date`, `quantity`, `product_name`; default `"expiry_date"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [
      {
        "batch_id": "BAT_3fd84b4776f1",
        "batch_no": "AZ-1",
        "created_at": "2026-11-14T17:33:50Z",
        "days_to_expiry": 443,
        "expiry_date": "2028-01-31",
        "is_expired": false,
        "is_legacy_placeholder": false,
        "mfg_date": null,
        "mrp": 125.0,
        "product_id": "PROD_20f28a6512",
        "product_name": "Azithromycin 500mg",
        "purchase_price": 0.0,
        "quantity": 20,
        "received_date": "2026-11-14",
        "supplier_id": null,
        "supplier_name": "",
        "updated_at": "2026-11-14T17:33:50Z"
      }
    ],
    "message": "Near-expiry batches fetched successfully",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 3
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** -

### 48. GET /api/v1/inventory/out-of-stock

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Active products with stock <= 0
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `sort` | string | one of `stock`, `name`, `reorder_level`; default `"stock"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [],
    "message": "Out-of-stock products fetched successfully",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 0
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** -

#### Orders

### 49. GET /api/v1/orders

- **Role/auth:** admin, user (users only see their own resources; others return 404) (Bearer access token)
- **Purpose:** List orders (users: own only)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `status` | string | one of `pending`, `approved`, `sold`, `cancelled`, `returned` | - |
  | `product_id` | string | - | - |
  | `user_id` | string | - | admin only |
  | `from` | string (date) | - | - |
  | `to` | string (date) | - | - |
  | `updated_since` | string (date-time) | - | - |
  | `sort` | string | one of `created_at`, `updated_at`, `total_amount`, `status`; default `"created_at"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [
      {
        "cancel_reason": "",
        "category": "General",
        "created_at": "2026-11-14T17:33:50Z",
        "doctor_name": "Dr. Mehta",
        "image_url": null,
        "message": "",
        "order_id": "ORD_33ab8ec95c62",
        "patient_name": "Priya Sharma",
        "prescription_url": "https://res.cloudinary.com/demo/image/upload/MediAdminApp/Prescriptions/rx.png",
        "prescription_verified": false,
        "price": 120.0,
        "product_id": "PROD_20f28a6512",
        "product_name": "Azithromycin 500mg",
        "quantity": 1,
        "requires_prescription": true,
        "status": "pending",
        "total_amount": 120.0,
        "updated_at": "2026-11-14T17:33:50Z",
        "user_id": "UID_06ade2a9b763",
        "user_name": "Priya S"
      }
    ],
    "message": "Orders fetched successfully",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 2
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"status": "must be one of: pending, approved, sold, cancelled, returned"}, "message": "Invalid query parameters", "status": 400}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** Users see only their own orders. `updated_since` for incremental sync.

### 50. POST /api/v1/orders

- **Role/auth:** user (Bearer access token)
- **Purpose:** Place an order (stock is reserved only at sale)
- **Headers:** `Authorization: Bearer <access_token>` (required); `Idempotency-Key` (optional, max 255 chars; replays the first response); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: multipart/form-data` or `application/json`
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `product_id` | string | required | - |
  | `quantity` | integer | required | min 1 |
  | `message` | string | optional | - |
  | `doctor_name` | string | optional | - |
  | `patient_name` | string | optional | - |
  | `prescription_url` | string (uri) | optional | - |
  | `prescription` | string (binary) | optional | multipart only |
  Example:
  ```json
  {
    "product_id": "PROD_c7a36281e0",
    "quantity": 2,
    "message": "Need by evening"
  }
  ```
- **Success:** HTTP 201
  ```json
  {
    "data": {
      "cancel_reason": "",
      "category": "Analgesic",
      "created_at": "2026-11-14T17:33:50Z",
      "doctor_name": "",
      "image_url": null,
      "message": "Need by evening",
      "order_id": "ORD_f828d7b2e6d6",
      "patient_name": "",
      "prescription_url": null,
      "prescription_verified": false,
      "price": 31.0,
      "product_id": "PROD_c7a36281e0",
      "product_name": "Paracetamol 500mg",
      "quantity": 2,
      "requires_prescription": false,
      "status": "pending",
      "total_amount": 62.0,
      "updated_at": "2026-11-14T17:33:50Z",
      "user_id": "UID_06ade2a9b763",
      "user_name": "Priya S"
    },
    "message": "Order placed",
    "status": 201
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `PRESCRIPTION_REQUIRED` | `{"code": "PRESCRIPTION_REQUIRED", "fields": {"doctor_name": "required for this product", "prescription_url": "required for this product (or upload 'prescription')"}, "message": "This product requires a prescription", "status": 400}` |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"quantity": "must be >= 1"}, "message": "Validation failed", "status": 400}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `ACCOUNT_BLOCKED` | `{"status": 403, "message": "...", "code": "ACCOUNT_BLOCKED"}` (unverified) |
  | 403 | `ACCOUNT_NOT_APPROVED` | `{"status": 403, "message": "...", "code": "ACCOUNT_NOT_APPROVED"}` (unverified) |
  | 403 | `FORBIDDEN` | `{"code": "FORBIDDEN", "message": "Access Forbidden", "status": 403}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `CONFLICT` | `{"status": 409, "message": "...", "code": "CONFLICT"}` (unverified) |
  | 409 | `OUT_OF_STOCK` | `{"code": "OUT_OF_STOCK", "fields": {"quantity": "available: 105"}, "message": "Only 105 unit(s) available", "status": 409}` |
  | 413 | `PAYLOAD_TOO_LARGE` | `{"status": 413, "message": "...", "code": "PAYLOAD_TOO_LARGE"}` (unverified) |
  | 415 | `UNSUPPORTED_MEDIA_TYPE` | `{"status": 415, "message": "...", "code": "UNSUPPORTED_MEDIA_TYPE"}` (unverified) |
- **Notes:** Customer only (admin token -> 403). Idempotent via `Idempotency-Key`. Stock is checked here and deducted only at /sell. Prescription-schedule products need a prescription (file `prescription` or `prescription_url`) else 400 PRESCRIPTION_REQUIRED. Blocked/unapproved customers -> 403. 201 + `Location`. `Location` header example: `http://localhost/api/v1/orders/ORD_f828d7b2e6d6`.

### 51. GET /api/v1/orders/{order_id}

- **Role/auth:** admin, user (users only see their own resources; others return 404) (Bearer access token)
- **Purpose:** Get an order with its sales lines
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `order_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "cancel_reason": "",
      "category": "Analgesic",
      "created_at": "2026-11-14T17:33:50Z",
      "doctor_name": "",
      "image_url": null,
      "message": "Need by evening",
      "order_id": "ORD_f828d7b2e6d6",
      "patient_name": "",
      "prescription_url": null,
      "prescription_verified": false,
      "price": 31.0,
      "product_id": "PROD_c7a36281e0",
      "product_name": "Paracetamol 500mg",
      "quantity": 2,
      "requires_prescription": false,
      "sales": [],
      "status": "pending",
      "total_amount": 62.0,
      "updated_at": "2026-11-14T17:33:50Z",
      "user_id": "UID_06ade2a9b763",
      "user_name": "Priya S"
    },
    "message": "Order fetched successfully",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "Order not found", "status": 404}` |
- **Notes:** Other users' orders -> 404.

### 52. PATCH /api/v1/orders/{order_id}

- **Role/auth:** admin, user (users only see their own resources; others return 404) (Bearer access token)
- **Purpose:** Edit patient_name / doctor_name while pending
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: multipart/form-data` or `application/json`
- **Path params:** `order_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `patient_name` | string | optional | - |
  | `doctor_name` | string | optional | - |
  Example:
  ```json
  {
    "patient_name": "Priya Sharma"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "cancel_reason": "",
      "category": "Analgesic",
      "created_at": "2026-11-14T17:33:50Z",
      "doctor_name": "",
      "image_url": null,
      "message": "Need by evening",
      "order_id": "ORD_f828d7b2e6d6",
      "patient_name": "Priya Sharma",
      "prescription_url": null,
      "prescription_verified": false,
      "price": 31.0,
      "product_id": "PROD_c7a36281e0",
      "product_name": "Paracetamol 500mg",
      "quantity": 2,
      "requires_prescription": false,
      "status": "pending",
      "total_amount": 62.0,
      "updated_at": "2026-11-14T17:33:51Z",
      "user_id": "UID_06ade2a9b763",
      "user_name": "Priya S"
    },
    "message": "Order updated",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `INVALID_TRANSITION` | `{"status": 409, "message": "...", "code": "INVALID_TRANSITION"}` (unverified) |
- **Notes:** Users: own pending orders, `patient_name`/`doctor_name` only.

### 53. POST /api/v1/orders/{order_id}/approve

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Approve a pending order
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `order_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "cancel_reason": "",
      "category": "General",
      "created_at": "2026-11-14T17:33:50Z",
      "doctor_name": "Dr. Mehta",
      "image_url": null,
      "message": "",
      "order_id": "ORD_33ab8ec95c62",
      "patient_name": "Priya Sharma",
      "prescription_url": "https://res.cloudinary.com/demo/image/upload/MediAdminApp/Prescriptions/rx2.png",
      "prescription_verified": false,
      "price": 120.0,
      "product_id": "PROD_20f28a6512",
      "product_name": "Azithromycin 500mg",
      "quantity": 1,
      "requires_prescription": true,
      "status": "approved",
      "total_amount": 120.0,
      "updated_at": "2026-11-14T17:33:51Z",
      "user_id": "UID_06ade2a9b763",
      "user_name": "Priya S"
    },
    "message": "Order approved",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `INVALID_TRANSITION` | `{"code": "INVALID_TRANSITION", "message": "Cannot approve an order that is approved", "status": 409}` |
- **Notes:** pending -> approved; other states -> 409 INVALID_TRANSITION.

### 54. POST /api/v1/orders/{order_id}/cancel

- **Role/auth:** admin, user (users only see their own resources; others return 404) (Bearer access token)
- **Purpose:** Cancel (users: own pending orders only); restocks if deducted
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: multipart/form-data` or `application/json`
- **Path params:** `order_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `cancel_reason` | string | optional | - |
  Example:
  ```json
  {
    "cancel_reason": "ordered twice"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "cancel_reason": "ordered twice",
      "category": "Analgesic",
      "created_at": "2026-11-14T17:33:51Z",
      "doctor_name": "",
      "image_url": null,
      "message": "",
      "order_id": "ORD_5464cf806efd",
      "patient_name": "",
      "prescription_url": null,
      "prescription_verified": false,
      "price": 31.0,
      "product_id": "PROD_c7a36281e0",
      "product_name": "Paracetamol 500mg",
      "quantity": 1,
      "requires_prescription": false,
      "restocked": [],
      "status": "cancelled",
      "total_amount": 31.0,
      "updated_at": "2026-11-14T17:33:51Z",
      "user_id": "UID_06ade2a9b763",
      "user_name": "Priya S"
    },
    "message": "Order cancelled",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `INVALID_TRANSITION` | `{"code": "INVALID_TRANSITION", "message": "Only pending orders can be cancelled (order is sold)", "status": 409}` |
- **Notes:** User: own pending orders. Admin: pending/approved. Restocks any net SALE deduction (CANCEL_RESTOCK).

### 55. GET /api/v1/orders/{order_id}/invoice

- **Role/auth:** admin, user (users only see their own resources; others return 404) (Bearer access token)
- **Purpose:** Invoice (sold/returned orders)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `order_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "currency": "INR",
      "generated_at": "2026-11-14T17:33:51Z",
      "grand_total": 62.0,
      "gst_total": 6.64,
      "invoice_number": "INV-ORD_f828d7b2e6d6",
      "issued_at": "2026-11-14T17:33:51Z",
      "items": [
        {
          "batch_id": "BAT_2cceba2ef4f8",
          "batch_no": "B-2026-01",
          "expiry_date": "2028-06-30",
          "gst_amount": 6.64,
          "gst_percent": 12.0,
          "line_total": 62.0,
          "product_id": "PROD_c7a36281e0",
          "product_name": "Paracetamol 500mg",
          "quantity": 2,
          "taxable_amount": 55.36,
          "unit_price": 31.0
        }
      ],
      "order": {
        "cancel_reason": "",
        "category": "Analgesic",
        "created_at": "2026-11-14T17:33:50Z",
        "doctor_name": "",
        "image_url": null,
        "message": "Need by evening",
        "order_id": "ORD_f828d7b2e6d6",
        "patient_name": "Priya Sharma",
        "prescription_url": null,
        "prescription_verified": false,
        "price": 31.0,
        "product_id": "PROD_c7a36281e0",
        "product_name": "Paracetamol 500mg",
        "quantity": 2,
        "requires_prescription": false,
        "status": "sold",
        "total_amount": 62.0,
        "updated_at": "2026-11-14T17:33:51Z",
        "user_id": "UID_06ade2a9b763",
        "user_name": "Priya S"
      },
      "prices_include_gst": true,
      "subtotal": 55.36,
      "user": {
        "address": "14 MG Road, Pune",
        "email": "priya@example.com",
        "name": "Priya S",
        "phone_number": "+919811111111",
        "pin_code": "411002",
        "user_id": "UID_06ade2a9b763"
      }
    },
    "message": "Invoice generated",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `INVALID_TRANSITION` | `{"code": "INVALID_TRANSITION", "message": "Invoice is available only after the order is sold", "status": 409}` |
- **Notes:** Only for sold/returned orders (else 409 INVALID_TRANSITION). Prices are GST-inclusive.

### 56. POST /api/v1/orders/{order_id}/prescription

- **Role/auth:** admin, user (users only see their own resources; others return 404) (Bearer access token)
- **Purpose:** Upload prescription (jpeg/png/webp/pdf; size from MAX_UPLOAD_MB)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: multipart/form-data`
- **Path params:** `order_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `prescription` | string (binary) | required | - |
  | `doctor_name` | string | optional | - |
  | `patient_name` | string | optional | - |
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "cancel_reason": "",
      "category": "General",
      "created_at": "2026-11-14T17:33:50Z",
      "doctor_name": "Dr. Mehta",
      "image_url": null,
      "message": "",
      "order_id": "ORD_33ab8ec95c62",
      "patient_name": "Priya Sharma",
      "prescription_url": "https://res.cloudinary.com/demo/image/upload/MediAdminApp/Prescriptions/rx2.png",
      "prescription_verified": false,
      "price": 120.0,
      "product_id": "PROD_20f28a6512",
      "product_name": "Azithromycin 500mg",
      "quantity": 1,
      "requires_prescription": true,
      "status": "pending",
      "total_amount": 120.0,
      "updated_at": "2026-11-14T17:33:51Z",
      "user_id": "UID_06ade2a9b763",
      "user_name": "Priya S"
    },
    "message": "Prescription uploaded",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `INVALID_TRANSITION` | `{"status": 409, "message": "...", "code": "INVALID_TRANSITION"}` (unverified) |
  | 413 | `PAYLOAD_TOO_LARGE` | `{"status": 413, "message": "...", "code": "PAYLOAD_TOO_LARGE"}` (unverified) |
  | 415 | `UNSUPPORTED_MEDIA_TYPE` | `{"code": "UNSUPPORTED_MEDIA_TYPE", "fields": {"prescription": "allowed types: image/jpeg, image/png, image/webp, application/pdf"}, "message": "Unsupported file type", "status": 415}` |
- **Notes:** Multipart `prescription` (jpeg/png/webp/pdf).

### 57. POST /api/v1/orders/{order_id}/reject

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Reject (cancel) a pending/approved order
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: multipart/form-data` or `application/json`
- **Path params:** `order_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `reason` | string | optional | - |
  Example:
  ```json
  {
    "reason": "Not available for delivery"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "cancel_reason": "Rejected: Not available for delivery",
      "category": "Analgesic",
      "created_at": "2026-11-14T17:33:51Z",
      "doctor_name": "",
      "image_url": null,
      "message": "",
      "order_id": "ORD_09e2ae2b7a9a",
      "patient_name": "",
      "prescription_url": null,
      "prescription_verified": false,
      "price": 31.0,
      "product_id": "PROD_c7a36281e0",
      "product_name": "Paracetamol 500mg",
      "quantity": 1,
      "requires_prescription": false,
      "restocked": [],
      "status": "cancelled",
      "total_amount": 31.0,
      "updated_at": "2026-11-14T17:33:51Z",
      "user_id": "UID_06ade2a9b763",
      "user_name": "Priya S"
    },
    "message": "Order rejected",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `INVALID_TRANSITION` | `{"status": 409, "message": "...", "code": "INVALID_TRANSITION"}` (unverified) |
- **Notes:** pending -> cancelled with `reason`.

### 58. POST /api/v1/orders/{order_id}/return

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Return a sold order; restocks each batch (expired batches reported in not_restocked)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: multipart/form-data` or `application/json`
- **Path params:** `order_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `reason` | string | optional | - |
  Example:
  ```json
  {
    "reason": "wrong strength"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "cancel_reason": "wrong strength",
      "category": "Analgesic",
      "created_at": "2026-11-14T17:33:50Z",
      "doctor_name": "",
      "image_url": null,
      "message": "Need by evening",
      "not_restocked": [],
      "order_id": "ORD_f828d7b2e6d6",
      "patient_name": "Priya Sharma",
      "prescription_url": null,
      "prescription_verified": false,
      "price": 31.0,
      "product_id": "PROD_c7a36281e0",
      "product_name": "Paracetamol 500mg",
      "quantity": 2,
      "requires_prescription": false,
      "restocked": [
        {
          "batch_id": "BAT_2cceba2ef4f8",
          "batch_no": "B-2026-01",
          "qty": 2
        }
      ],
      "status": "returned",
      "total_amount": 62.0,
      "updated_at": "2026-11-14T17:33:51Z",
      "user_id": "UID_06ade2a9b763",
      "user_name": "Priya S"
    },
    "message": "Order returned",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `INVALID_TRANSITION` | `{"status": 409, "message": "...", "code": "INVALID_TRANSITION"}` (unverified) |
- **Notes:** sold -> returned. Restocks each batch (RETURN); expired/legacy batches are reported in `not_restocked`.

### 59. POST /api/v1/orders/{order_id}/sell

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Sell an approved order: FEFO deduction, one sale row per batch, single transaction
- **Headers:** `Authorization: Bearer <access_token>` (required); `Idempotency-Key` (optional, max 255 chars; replays the first response); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `order_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "cancel_reason": "",
      "category": "Analgesic",
      "created_at": "2026-11-14T17:33:50Z",
      "doctor_name": "",
      "image_url": null,
      "message": "Need by evening",
      "order_id": "ORD_f828d7b2e6d6",
      "patient_name": "Priya Sharma",
      "prescription_url": null,
      "prescription_verified": false,
      "price": 31.0,
      "product_id": "PROD_c7a36281e0",
      "product_name": "Paracetamol 500mg",
      "quantity": 2,
      "requires_prescription": false,
      "sales": [
        {
          "batch_id": "BAT_2cceba2ef4f8",
          "batch_no": "B-2026-01",
          "gst_percent": 12.0,
          "image_url": null,
          "order_id": "ORD_f828d7b2e6d6",
          "order_status": "sold",
          "price": 31.0,
          "product_id": "PROD_c7a36281e0",
          "product_name": "Paracetamol 500mg",
          "quantity": 2,
          "remaining_stock": 103,
          "sale_id": "SELL_dbd3c87884db",
          "sold_at": "2026-11-14T17:33:51Z",
          "sold_by": "AID_root",
          "total_amount": 62.0,
          "user_id": "UID_06ade2a9b763",
          "user_name": "Priya S"
        }
      ],
      "status": "sold",
      "total_amount": 62.0,
      "updated_at": "2026-11-14T17:33:51Z",
      "user_id": "UID_06ade2a9b763",
      "user_name": "Priya S"
    },
    "message": "Order sold",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `ALREADY_SOLD` | `{"code": "ALREADY_SOLD", "message": "Order has already been sold", "status": 409}` |
  | 409 | `INVALID_TRANSITION` | `{"status": 409, "message": "...", "code": "INVALID_TRANSITION"}` (unverified) |
  | 409 | `OUT_OF_STOCK` | `{"status": 409, "message": "...", "code": "OUT_OF_STOCK"}` (unverified) |
  | 409 | `PRESCRIPTION_NOT_VERIFIED` | `{"code": "PRESCRIPTION_NOT_VERIFIED", "message": "Prescription must be verified before sale", "status": 409}` |
- **Notes:** approved -> sold. Deducts stock FEFO from non-expired batches (OUT_OF_STOCK if insufficient; nothing changes). Rx orders need a verified prescription (409 PRESCRIPTION_NOT_VERIFIED). Repeat -> 409 ALREADY_SOLD. Idempotent via `Idempotency-Key`.

### 60. POST /api/v1/orders/{order_id}/verify-prescription

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Mark the prescription verified (or not)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: multipart/form-data` or `application/json`
- **Path params:** `order_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `verified` | boolean | optional | default `true` |
  Example:
  ```json
  {
    "verified": true
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "cancel_reason": "",
      "category": "General",
      "created_at": "2026-11-14T17:33:50Z",
      "doctor_name": "Dr. Mehta",
      "image_url": null,
      "message": "",
      "order_id": "ORD_33ab8ec95c62",
      "patient_name": "Priya Sharma",
      "prescription_url": "https://res.cloudinary.com/demo/image/upload/MediAdminApp/Prescriptions/rx2.png",
      "prescription_verified": true,
      "price": 120.0,
      "product_id": "PROD_20f28a6512",
      "product_name": "Azithromycin 500mg",
      "quantity": 1,
      "requires_prescription": true,
      "status": "approved",
      "total_amount": 120.0,
      "updated_at": "2026-11-14T17:33:51Z",
      "user_id": "UID_06ade2a9b763",
      "user_name": "Priya S"
    },
    "message": "Prescription verified",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `INVALID_TRANSITION` | `{"status": 409, "message": "...", "code": "INVALID_TRANSITION"}` (unverified) |
- **Notes:** Required before selling a prescription order.

### 61. GET /api/v1/users/{user_id}/orders

- **Role/auth:** admin, user (users only see their own resources; others return 404) (Bearer access token)
- **Purpose:** List a user's orders (users: own id only)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `user_id` (string, required)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `status` | string | one of `pending`, `approved`, `sold`, `cancelled`, `returned` | - |
  | `product_id` | string | - | - |
  | `from` | string (date) | - | - |
  | `to` | string (date) | - | - |
  | `updated_since` | string (date-time) | - | - |
  | `sort` | string | one of `created_at`, `updated_at`, `total_amount`, `status`; default `"created_at"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [
      {
        "cancel_reason": "",
        "category": "General",
        "created_at": "2026-11-14T17:33:50Z",
        "doctor_name": "Dr. Mehta",
        "image_url": null,
        "message": "",
        "order_id": "ORD_33ab8ec95c62",
        "patient_name": "Priya Sharma",
        "prescription_url": "https://res.cloudinary.com/demo/image/upload/MediAdminApp/Prescriptions/rx.png",
        "prescription_verified": false,
        "price": 120.0,
        "product_id": "PROD_20f28a6512",
        "product_name": "Azithromycin 500mg",
        "quantity": 1,
        "requires_prescription": true,
        "status": "pending",
        "total_amount": 120.0,
        "updated_at": "2026-11-14T17:33:50Z",
        "user_id": "UID_06ade2a9b763",
        "user_name": "Priya S"
      }
    ],
    "message": "Orders fetched successfully",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 2
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "User not found", "status": 404}` |
- **Notes:** Users: own id only, else 404.

#### Sales

### 62. GET /api/v1/sales

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Sales ledger (one row per order batch)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `from` | string (date) | - | - |
  | `to` | string (date) | - | - |
  | `product_id` | string | - | - |
  | `user_id` | string | - | - |
  | `order_id` | string | - | - |
  | `batch_id` | string | - | - |
  | `updated_since` | string (date-time) | - | - |
  | `sort` | string | one of `sold_at`, `total_amount`, `quantity`; default `"sold_at"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [
      {
        "batch_id": "BAT_2cceba2ef4f8",
        "batch_no": "B-2026-01",
        "gst_percent": 12.0,
        "image_url": null,
        "order_id": "ORD_f828d7b2e6d6",
        "order_status": "returned",
        "price": 31.0,
        "product_id": "PROD_c7a36281e0",
        "product_name": "Paracetamol 500mg",
        "quantity": 2,
        "remaining_stock": 103,
        "sale_id": "SELL_dbd3c87884db",
        "sold_at": "2026-11-14T17:33:51Z",
        "sold_by": "AID_root",
        "total_amount": 62.0,
        "user_id": "UID_06ade2a9b763",
        "user_name": "Priya S"
      }
    ],
    "message": "Sales fetched successfully",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 1
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** Sale ledger rows (one per batch deducted). Use `user_id`/`product_id` filters instead of the old per-user/per-product URLs.

#### Suppliers

### 63. GET /api/v1/suppliers

- **Role/auth:** admin (Bearer access token)
- **Purpose:** List suppliers
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `q` | string | - | - |
  | `is_active` | boolean | - | - |
  | `sort` | string | one of `name`, `created_at`, `updated_at`; default `"name"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [
      {
        "address": "Bhosari MIDC, Pune",
        "contact_phone": "+912012345678",
        "created_at": "2026-11-14T17:33:50Z",
        "email": "orders@medsupply.in",
        "gst_number": "27ABCDE1234F1Z5",
        "is_active": true,
        "name": "MedSupply Pvt Ltd",
        "supplier_id": "SUP_0debfd314e",
        "updated_at": "2026-11-14T17:33:50Z"
      }
    ],
    "message": "Suppliers fetched successfully",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 1
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** -

### 64. POST /api/v1/suppliers

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Create supplier
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: multipart/form-data` or `application/json`
- **Path/query params:** none
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `name` | string | required | max length 200 |
  | `contact_phone` | string | optional | - |
  | `email` | string (email) | optional | - |
  | `gst_number` | string | optional | 15-char GSTIN |
  | `address` | string | optional | - |
  Example:
  ```json
  {
    "name": "MedSupply Pvt Ltd",
    "contact_phone": "+912012345678",
    "email": "orders@medsupply.in",
    "gst_number": "27ABCDE1234F1Z5",
    "address": "Bhosari MIDC, Pune"
  }
  ```
- **Success:** HTTP 201
  ```json
  {
    "data": {
      "address": "Bhosari MIDC, Pune",
      "contact_phone": "+912012345678",
      "created_at": "2026-11-14T17:33:50Z",
      "email": "orders@medsupply.in",
      "gst_number": "27ABCDE1234F1Z5",
      "is_active": true,
      "name": "MedSupply Pvt Ltd",
      "supplier_id": "SUP_0debfd314e",
      "updated_at": "2026-11-14T17:33:50Z"
    },
    "message": "Supplier created",
    "status": 201
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"name": "is required"}, "message": "Validation failed", "status": 400}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 409 | `CONFLICT` | `{"status": 409, "message": "...", "code": "CONFLICT"}` (unverified) |
- **Notes:** `Location` header example: `http://localhost/api/v1/suppliers/SUP_0debfd314e`.

### 65. GET /api/v1/suppliers/{supplier_id}

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Get supplier
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `supplier_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "address": "Bhosari MIDC, Pune",
      "contact_phone": "+912012345678",
      "created_at": "2026-11-14T17:33:50Z",
      "email": "orders@medsupply.in",
      "gst_number": "27ABCDE1234F1Z5",
      "is_active": true,
      "name": "MedSupply Pvt Ltd",
      "supplier_id": "SUP_0debfd314e",
      "updated_at": "2026-11-14T17:33:50Z"
    },
    "message": "Supplier fetched successfully",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"code": "NOT_FOUND", "message": "Supplier not found", "status": 404}` |
- **Notes:** -

### 66. PATCH /api/v1/suppliers/{supplier_id}

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Partially update supplier
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426); `Content-Type: multipart/form-data` or `application/json`
- **Path params:** `supplier_id` (string, required)
- **Request body:**
  | Field | Type | Required | Validation / notes |
  | :--- | :--- | :--- | :--- |
  | `name` | string | required | max length 200 |
  | `contact_phone` | string | optional | - |
  | `email` | string (email) | optional | - |
  | `gst_number` | string | optional | 15-char GSTIN |
  | `address` | string | optional | - |
  Example:
  ```json
  {
    "contact_phone": "+912012345679"
  }
  ```
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "address": "Bhosari MIDC, Pune",
      "contact_phone": "+912012345679",
      "created_at": "2026-11-14T17:33:50Z",
      "email": "orders@medsupply.in",
      "gst_number": "27ABCDE1234F1Z5",
      "is_active": true,
      "name": "MedSupply Pvt Ltd",
      "supplier_id": "SUP_0debfd314e",
      "updated_at": "2026-11-14T17:33:50Z"
    },
    "message": "Supplier updated",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `CONFLICT` | `{"status": 409, "message": "...", "code": "CONFLICT"}` (unverified) |
- **Notes:** -

### 67. POST /api/v1/suppliers/{supplier_id}/deactivate

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Soft-deactivate supplier
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path params:** `supplier_id` (string, required)
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "address": "Bhosari MIDC, Pune",
      "contact_phone": "+912012345679",
      "created_at": "2026-11-14T17:33:50Z",
      "email": "orders@medsupply.in",
      "gst_number": "27ABCDE1234F1Z5",
      "is_active": false,
      "name": "MedSupply Pvt Ltd",
      "supplier_id": "SUP_0debfd314e",
      "updated_at": "2026-11-14T17:33:51Z"
    },
    "message": "Supplier deactivated",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
  | 404 | `NOT_FOUND` | `{"status": 404, "message": "...", "code": "NOT_FOUND"}` (unverified) |
  | 409 | `CONFLICT` | `{"code": "CONFLICT", "message": "Supplier is already inactive", "status": 409}` |
- **Notes:** -

#### Reports & dashboard

### 68. GET /api/v1/dashboard/summary

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Dashboard counters
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Path/query params:** none
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": {
      "approved_orders": 1,
      "date": "2026-11-14",
      "expired_batches": 0,
      "low_stock": 0,
      "near_expiry_batches": 0,
      "near_expiry_days": 90,
      "out_of_stock": 0,
      "pending_orders": 0,
      "products": 2,
      "today_sales_count": 0,
      "today_sales_total": 0.0
    },
    "message": "Dashboard summary",
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** Sales totals exclude returned orders.

### 69. GET /api/v1/reports/sales

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Sales grouped by day or product (net of returns)
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `from` | string (date) | - | default: today - 30 days |
  | `to` | string (date) | - | default: today |
  | `group_by` | string | one of `day`, `product`; default `"day"` | - |
  | `sort` | string | one of `key`, `quantity`, `revenue`; default `"key"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [],
    "message": "Sales report",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 0
    },
    "status": 200,
    "summary": {
      "from": "2026-10-15",
      "group_by": "day",
      "orders": 0,
      "quantity": 0,
      "revenue": 0.0,
      "to": "2026-11-14"
    }
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"code": "VALIDATION_ERROR", "fields": {"group_by": "must be one of: day, product"}, "message": "Invalid query parameters", "status": 400}` |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** Totals exclude returned orders.

### 70. GET /api/v1/reports/top-products

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Best-selling products
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `from` | string (date) | - | default: today - 30 days |
  | `to` | string (date) | - | default: today |
  | `sort` | string | one of `quantity`, `revenue`; default `"quantity"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [],
    "message": "Top products",
    "pagination": {
      "limit": 20,
      "offset": 0,
      "total": 0
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** -

#### Audit

### 71. GET /api/v1/audit-logs

- **Role/auth:** admin (Bearer access token)
- **Purpose:** Audit trail
- **Headers:** `Authorization: Bearer <access_token>` (required); `X-App-Version` (optional; below `MIN_APP_VERSION` -> 426)
- **Query params:**
  | Name | Type | Rules / default | Notes |
  | :--- | :--- | :--- | :--- |
  | `entity` | string | - | - |
  | `entity_id` | string | - | - |
  | `actor_id` | string | - | - |
  | `action` | string | - | - |
  | `from` | string | - | date or date-time |
  | `to` | string | - | date or date-time |
  | `sort` | string | one of `created_at`; default `"created_at"` | - |
  | `limit` | integer | max 100; default `20` | - |
  | `offset` | integer | default `0` | - |
  | `order` | string | one of `asc`, `desc` | - |
- **Request body:** none
- **Success:** HTTP 200
  ```json
  {
    "data": [
      {
        "action": "supplier.deactivate",
        "actor_id": "AID_root",
        "actor_role": "admin",
        "audit_id": "AUD_40d60e0ebf824d93",
        "created_at": "2026-11-14T17:33:51Z",
        "details": {
          "is_active": false
        },
        "entity": "supplier",
        "entity_id": "SUP_0debfd314e"
      }
    ],
    "message": "Audit logs fetched successfully",
    "pagination": {
      "limit": 2,
      "offset": 0,
      "total": 40
    },
    "status": 200
  }
  ```
- **Errors:**
  | HTTP | code | Example |
  | :--- | :--- | :--- |
  | 400 | `VALIDATION_ERROR` | `{"status": 400, "message": "...", "code": "VALIDATION_ERROR"}` (unverified) |
  | 401 | `TOKEN_EXPIRED` | `{"status": 401, "message": "Token has expired", "code": "TOKEN_EXPIRED"}` |
  | 401 | `TOKEN_INVALID` | `{"status": 401, "message": "Invalid token", "code": "TOKEN_INVALID"}` |
  | 401 | `UNAUTHORIZED` | `{"status": 401, "message": "Missing or malformed authorization token", "code": "UNAUTHORIZED"}` |
  | 403 | `FORBIDDEN` | `{"status": 403, "message": "Access Forbidden", "code": "FORBIDDEN"}` |
- **Notes:** Sensitive keys (password/otp/token/secret) are stripped from `details`.

---

## 5. Kotlin Integration Notes (v1)

- **One envelope everywhere:** parse `data` (object, list or null). Suggested DTOs:
  ```kotlin
  data class ApiResponse<T>(val status: Int, val message: String, val data: T?)
  data class Pagination(val limit: Int, val offset: Int, val total: Int)
  data class PagedResponse<T>(val status: Int, val message: String, val data: List<T>, val pagination: Pagination)
  data class ApiError(val status: Int, val message: String, val code: String, val fields: Map<String, String>? = null)
  ```
- **Branch on `code`, not on `message`.** Messages are for display/logging and may change.
- **IDs are strings** with prefixes (`UID_`, `AID_`, `PROD_`, `BAT_`, `ORD_`, `DEV_`, ...). All keys are snake_case (`product_id`, not `Product_id`).
- **Nullable fields** are always present (`null`), e.g. `image_url`, `phone_number`, `prescription_url`, `purchase_price` (null for customers), `supplier_id`. Declare them `String? = null` / `Double? = null`.
- **Booleans** are real JSON booleans (`is_approved`, `is_blocked`, `is_active`, `is_owner`, `requires_prescription`, ...). `AdminDto` gains `val is_approved: Boolean` and `val is_owner: Boolean`. The old `isApproved`/`block`/`sold` keys are gone.
- **Money** is a JSON number in rupees (e.g. `31.0`); use `BigDecimal` on the client for totals. (Integer paise is an open item.)
- **Timestamps** are UTC `...Z`; convert to local time only for display.
- **Retrofit:** use `@Multipart` with `@Part image: MultipartBody.Part?` for profile/product images and `@Part prescription` for orders; send other fields as `@Part` text parts or use JSON bodies when there is no file.
- **Interceptors:** add `Authorization` and `X-App-Version`; on 401 `TOKEN_EXPIRED` refresh once (single-flight) and retry; on 426 show the force-update screen.

---

## 6. Legacy vs Current Differences (historical, pre-v1)

_Kept for reference. Every endpoint named in this table was replaced by a `/api/v1` endpoint; see section 8 for the mapping._

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

- Error rows marked `(unverified)` in section 4 list codes the endpoint can return (from the OpenAPI fragments) whose exact `message` text was not reproduced in the capture run; the `status` and `code` values are reliable.
- `GET /health/ready` 503 bodies (requires a failing database/Redis).
- 413 `PAYLOAD_TOO_LARGE` bodies (requires a >5 MB upload).
- `POST /admins/register` 413/415 rows (image upload path, same code as `POST /admins`; not exercised in the capture run).
- Everything else in section 4 (success bodies and the remaining error rows) was captured from the code on 2026-11-14 (admin signup entries on 2026-11-15).

---

## 8. Changelog

### Old URL -> new URL (all parts)

| Old (removed) | New (`/api/v1`) | Notes |
| :--- | :--- | :--- |
| `GET /` | `GET /api/v1` | "Hello World" removed; index lists public links |
| `GET /dox` | `GET /api/docs` | `/dox` now 301-redirects |
| `POST /admin/login`, `POST /user/login` | `POST /auth/login` | `account_type` = `admin`/`user` |
| `POST /admin/verifyOtp`, `POST /user/verifyUserOtp` | `POST /auth/verify-otp` | `account_id` replaces `admin_id`/`user_id` |
| `POST /admin/refreshToken` | `POST /auth/refresh` | users too; tokens rotate |
| (none) | `POST /auth/logout` | new |
| `POST /admin/requestAdminPasswordReset`, `POST /user/requestUserPasswordReset` | `POST /auth/password-reset/request` | generic response |
| `POST /admin/resetAdminPasswordWithOtp`, `POST /user/resetUserPasswordWithOtp` | `POST /auth/password-reset/confirm` | field `new_password` |
| `POST /user/create` | `POST /users` | `phone_number`/`pin_code` (not `phoneNumber`/`pincode`); role always user |
| `GET /admin/getAllUsers` | `GET /users` | paginated |
| `POST /admin/user/getSpecificUser` | `GET /users/{user_id}` | |
| `PATCH /admin/updateUser` | `PATCH /users/me` (self) / `PATCH /users/{user_id}` (admin) | |
| `PATCH /admin/approveUser` | `POST /users/{user_id}/approve`, `/block`, `/unblock` | |
| `POST /admin/deleteUser` | `DELETE /users/{user_id}` | soft delete |
| `POST /admin/create` | `POST /admins` | |
| `GET /admin/getAllAdmins` | `GET /admins` | paginated |
| `PATCH /admin/update` | `PATCH /admins/{admin_id}` | |
| `POST /admin/delete` | `DELETE /admins/{admin_id}` | soft delete; last admin protected |
| `POST /admin/addProduct` | `POST /products` | |
| `GET /admin/user/getAllProducts` | `GET /products` | paginated, filters |
| `POST /admin/user/getSpecificProduct` | `GET /products/{product_id}` | |
| `PATCH /admin/updateProduct` | `PATCH /products/{product_id}` | |
| `POST /admin/deleteProduct` | `POST /products/{product_id}/deactivate` | soft delete |
| `POST /user/createOrder` | `POST /orders` | idempotent |
| `GET /admin/getAllOrders` | `GET /orders` | |
| `POST /admin/user/getOrdersByUserId` | `GET /users/{user_id}/orders` | |
| `POST /admin/user/orderById` | `GET /orders/{order_id}` | |
| `PATCH /admin/updateOrder` | `PATCH /orders/{order_id}` | limited fields |
| `PATCH /admin/approveOrder` | `POST /orders/{order_id}/approve` / `/reject` | |
| `POST /admin/deleteOrder` | `POST /orders/{order_id}/cancel` | no hard delete |
| `POST /admin/recordSell` | `POST /orders/{order_id}/sell` | FEFO batches |
| `GET /admin/getSellHistory` | `GET /sales` | |
| `POST /admin/user/getSellHistoryByUserId` | `GET /sales?user_id=` (admin) / `GET /orders?status=sold` (user) | |
| `POST /admin/getproductsellhistory` | `GET /sales?product_id=` | |
| `POST /admin/deleteSellHistory` | `POST /orders/{order_id}/return` | sales are never deleted |

### Changed / added / removed in this run (Part 3, 2026-11-14)
- **Removed** entries (endpoints no longer exist): all 38 legacy entries `GET /`, `GET /dox` (now a redirect, re-documented as H4), `/admin/*`, `/user/*` listed in the table above.
- **Changed:** `GET /health` entry re-checked (unchanged body); sections 1, 2, 3, 5, 7 rewritten for v1 (envelope with `data`, `code` in every error, auth flow, headers, pagination, uploads, enums); section 6 kept as history.
- **Added (Part 1):** products, product-categories, batches, stock purchase/adjust, stock-movements, inventory alerts (20 operations).
- **Added (Part 2):** orders lifecycle, invoices, prescriptions, sales, suppliers, dashboard, reports, audit-logs (23 operations).
- **Added (Part 3):** auth (6), users (10), admins (5), devices (2), `GET /api/v1`, `GET /app-config`, `GET /openapi.json`, `GET /health/ready`, `GET /api/docs`.
- **Response contract changes:** success payload always under `data`; lists add `pagination`; errors add `code` (+ `fields`); ids/keys snake_case; booleans real; timestamps UTC `Z`; passwords and OTPs never returned; 201 + `Location` on create.

### Changed / added in this run (admin signup, 2026-11-15)
- **Added:** `POST /api/v1/admins/register` (public admin signup, #25) and `POST /api/v1/admins/{admin_id}/approve` (#26). Entries #25-#69 were renumbered to #27-#71.
- **Added:** `is_approved` filter on `GET /api/v1/admins`; `admin_signup {enabled, code_required}` in `GET /api/v1/app-config`; `is_approved` and `is_owner` in every admin object.
- **Changed:** admin login, verify-otp and refresh return 403 `ACCOUNT_NOT_APPROVED` for unapproved admins. The owner cannot be deleted or disabled (403 "Owner account is protected"). The last-admin rule now counts approved, active admins. Its message is now "At least one approved admin is required" (was "Cannot remove or demote the last active admin"); the status is still 409 `CONFLICT`. `PATCH /admins/{admin_id}` and `POST /admins` reject `is_approved`/`is_owner` (400).
- **Database (additive only, nothing deleted):** `Admin.is_approved INTEGER DEFAULT 1` (existing admins stay approved), `Admin.is_owner INTEGER DEFAULT 0`, unique partial index `ux_admin_owner`. The usual `<db>.bak-<timestamp>` backup is taken before the migration.
- **Server:** env `ADMIN_SIGNUP_CODE` (recommended in production), `ADMIN_SIGNUP_RATE_LIMIT`, `ADMIN_SIGNUP_RATE_WINDOW_SECONDS`; CLI `flask --app wsgi approve-admin --email <email> [--owner]`.
