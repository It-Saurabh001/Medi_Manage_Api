# Medi Manage API

REST API for a medical shop (pharmacy). It powers two Android apps: **MediUserApp** for customers and **MediAdminApp** for the shop owner. It covers accounts, products, batch-wise inventory, orders with prescriptions, sales, invoices and reports.

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white">
  <img alt="Flask" src="https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white">
  <img alt="JWT" src="https://img.shields.io/badge/Auth-JWT-000000?logo=jsonwebtokens&logoColor=white">
  <img alt="SQLite" src="https://img.shields.io/badge/SQLite-local-003B57?logo=sqlite&logoColor=white">
  <img alt="Turso" src="https://img.shields.io/badge/Turso-hosted%20SQLite-4FF8D2?logo=turso&logoColor=black">
  <img alt="Redis" src="https://img.shields.io/badge/Redis-OTP%20%26%20limits-DC382D?logo=redis&logoColor=white">
  <img alt="Cloudinary" src="https://img.shields.io/badge/Cloudinary-uploads-3448C5?logo=cloudinary&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white">
  <img alt="OpenAPI" src="https://img.shields.io/badge/OpenAPI-3.0-6BA539?logo=openapiinitiative&logoColor=white">
  <img alt="pytest" src="https://img.shields.io/badge/tests-170%20passing-0A9EDC?logo=pytest&logoColor=white">
</p>

---

## Contents

- [Features](#features)
- [Tech stack](#tech-stack)
- [How it works](#how-it-works)
- [Project structure](#project-structure)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Database](#database)
- [Deployment](#deployment)
- [Testing](#testing)
- [Error format](#error-format)
- [Related projects](#related-projects)

---

## Features

**Accounts and authentication**
- Separate `user` (customer) and `admin` (shop) accounts with role-based access.
- Sign in with email and password, then a 6-digit email OTP. JWT access and refresh tokens, logout revokes the token.
- Email verification on sign up, password reset by OTP, resend with cooldown.
- New accounts need approval. Admins can approve, block, unblock and remove accounts.

**Products and inventory**
- Product catalogue with categories, barcode lookup, search, filters, sorting and pagination.
- Batch-wise stock (batch number, MFG and expiry date, MRP, purchase price, supplier).
- Stock is sold **First-Expiry-First-Out (FEFO)**. Every change is recorded in a stock movement ledger.
- Stock purchase, adjustment and expired write-off. Low-stock, out-of-stock, near-expiry and expired lists.
- Supplier management.

**Orders and sales**
- Single orders and multi-product checkouts (one checkout, one invoice).
- Prescription upload for Rx and scheduled medicines, verified by the admin before the sale.
- Order lifecycle: `pending` → `approved` → `sold`, plus `cancelled` and `returned`.
- Invoices for orders and checkouts, sales history.

**Reports and admin tools**
- Dashboard summary, sales report, top products and audit log of admin actions.

**Platform**
- Versioned REST API with a single JSON response and error format.
- Retry-safe `POST` requests with the `Idempotency-Key` header.
- Minimum app version check with the `X-App-Version` header.
- Device registration for push notifications.
- OpenAPI 3.0 spec and Swagger UI (can be turned off in production).
- Health and readiness endpoints.

---

## Tech stack

| | Tool | Used for |
|---|---|---|
| <img src="https://cdn.simpleicons.org/python/3776AB" width="20"> | **Python 3.12** | Language |
| <img src="https://cdn.simpleicons.org/flask/000000" width="20"> | **Flask 3.1** | Web framework, blueprints, application factory |
| <img src="https://cdn.simpleicons.org/jsonwebtokens/000000" width="20"> | **Flask-JWT-Extended** | Access and refresh tokens, token revocation |
| <img src="https://cdn.simpleicons.org/sqlite/003B57" width="20"> | **SQLite** | Local database (development and tests) |
| <img src="https://cdn.simpleicons.org/turso/4FF8D2" width="20"> | **Turso (libSQL)** | Hosted SQLite in production, through a built-in HTTP client |
| <img src="https://cdn.simpleicons.org/redis/DC382D" width="20"> | **Redis** | OTP store, rate limiting, token blocklist |
| <img src="https://cdn.simpleicons.org/cloudinary/3448C5" width="20"> | **Cloudinary** | Product images, profile photos and prescriptions |
| <img src="https://cdn.simpleicons.org/brevo/0B996E" width="20"> | **Brevo / Resend** | Transactional email over HTTPS API (SMTP also supported) |
| <img src="https://cdn.simpleicons.org/gunicorn/499848" width="20"> | **Gunicorn** | Production WSGI server |
| <img src="https://cdn.simpleicons.org/docker/2496ED" width="20"> | **Docker** | Container image and local compose setup |
| <img src="https://cdn.simpleicons.org/render/000000" width="20"> | **Render** | Hosting |
| <img src="https://cdn.simpleicons.org/swagger/85EA2D" width="20"> | **OpenAPI / Swagger UI** | API documentation |
| <img src="https://cdn.simpleicons.org/pytest/0A9EDC" width="20"> | **pytest** | Automated tests |

Other libraries: Flask-CORS, Werkzeug (password hashing), python-dotenv, aiosmtpd (local email debugging).

---

## How it works

```
MediUserApp (customer)          Medi Manage API                    MediAdminApp (shop)
──────────────────────          ───────────────                    ───────────────────
Place order / checkout   ─►     Order = pending             ─►     Sees new order
Upload prescription      ─►     Prescription stored         ─►     Verifies prescription
                                Order = approved            ◄─     Approves
                                Stock deducted (FEFO)       ◄─     Marks as sold
View invoice             ◄─     Order = sold, invoice ready
```

**Request flow inside the API**

```
Routes (blueprints)  →  Services (business rules)  →  Database layer  →  SQLite file / Turso
        │                       │
   validation, auth       stock, orders, accounts,
   and roles              email, OTP, uploads
```

- **Routes** validate input, check the JWT and role, and return the standard response.
- **Services** hold the business rules. Stock and order changes run in one database transaction, so partial updates never happen.
- **Integrations** (email, OTP store) are chosen by configuration, with separate development and production providers.

---

## Project structure

```
├── app/
│   ├── routes/          # Blueprints: auth, users, admins, products, inventory, orders, reports, ...
│   ├── services/        # Business logic: accounts, stock (FEFO), orders, reports, audit, DB setup
│   ├── integrations/    # Email (dev SMTP / production SMTP or API) and OTP store (memory / Redis)
│   ├── openapi/         # OpenAPI 3.0 spec
│   ├── utils/           # Validation, responses, idempotency, rate limit, time helpers
│   ├── db.py            # Database connections (SQLite or Turso)
│   └── turso_http.py    # Turso HTTP client with a sqlite3-style interface
├── config/              # Development, testing and production settings
├── scripts/
│   ├── dev/             # Local run helpers and a Turso connection check
│   └── prod/            # Container start: database migration, then Gunicorn
├── tests/               # pytest suite
├── requirements/        # base, dev and prod dependencies
├── Dockerfile
├── docker-compose.yml
└── wsgi.py              # WSGI entry point
```

---

## Getting started

**Requirements:** Python 3.12 or newer and Git. Redis is only needed for the production setup.

1. Clone and enter the project:
   ```bash
   git clone https://github.com/It-Saurabh001/Medi_Manage_Api.git
   cd Medi_Manage_Api
   ```

2. Create a virtual environment and install the development dependencies:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   # source .venv/bin/activate     # macOS / Linux
   pip install -r requirements/dev.txt
   ```

3. Create a `.env` file in the project root with your local settings (see [Configuration](#configuration)).

4. Start the local email debug server in a separate terminal. OTP emails are printed there instead of being sent:
   ```bash
   start_mail.bat
   ```

5. Start the API. This creates or upgrades the tables, then runs the development server on port 5000:
   ```bash
   devstart.bat
   ```
   On macOS or Linux run `flask --app wsgi init-db` and then `flask --app wsgi run --debug`.

---

## Configuration

All settings come from environment variables: a local `.env` file in development, and the host's environment settings in production. They cover the app and JWT secrets, the database, Redis, Cloudinary, the email provider, OTP timing and client rules. Never commit real values.

Production refuses to start when a required setting is missing or a development provider is configured.

---

## Database

| Environment | Database |
|---|---|
| Development and tests | Local SQLite file |
| Production | **Turso** (hosted SQLite), when configured |

- The same SQL runs on both. Turso is reached through a small built-in HTTP client, so no native driver is needed.
- Schema changes are additive and idempotent: tables, columns and indexes are created when missing, and existing data is never dropped.
- Without Turso, production falls back to a local SQLite file. On hosts with temporary disks that data is lost on restart, so use Turso or a persistent disk.

To check a Turso database before deploying (read-only):
```bash
python scripts/dev/check_turso.py
```
It reads the Turso settings from the environment.

---

## Deployment

The `Dockerfile` builds a production image (Python 3.12, non-root user, health check). On start, `scripts/prod/start.sh`:

1. runs the database migration once, in its own process;
2. starts Gunicorn (`WORKERS` and `BIND` can be set by environment).

Set the production settings in your host's environment (for example Render). For a full local stack with Redis:

```bash
docker compose up --build
```

---

## Testing

```bash
pytest
```

The suite uses a temporary SQLite database and a fake email sender, so it never sends real email or touches a real database.

To run the same suite through the Turso HTTP client against an in-process fake Turso server:

```bash
# Windows PowerShell
$env:TEST_DB_BACKEND="turso-fake"; pytest
```

---

## Error format

Errors share one shape:

```json
{
  "code": "VALIDATION_ERROR",
  "message": "Validation failed",
  "status": 400,
  "fields": { "email": "required" }
}
```

`fields` appears only for validation errors. Common codes: `VALIDATION_ERROR`, `UNAUTHORIZED`, `TOKEN_EXPIRED`, `FORBIDDEN`, `ACCOUNT_BLOCKED`, `ACCOUNT_NOT_APPROVED`, `EMAIL_NOT_VERIFIED`, `NOT_FOUND`, `CONFLICT`, `OUT_OF_STOCK`, `PRESCRIPTION_REQUIRED`, `RATE_LIMITED`, `UPGRADE_REQUIRED`.

---

## Related projects

- **MediUserApp**: Android app for customers (Kotlin, Jetpack Compose).
- **MediAdminApp**: Android app for the shop owner.

---

## Contributing

Issues and pull requests are welcome. Please run `pytest` before opening a pull request.

For questions, open an [issue](https://github.com/It-Saurabh001/Medi_Manage_Api/issues).
