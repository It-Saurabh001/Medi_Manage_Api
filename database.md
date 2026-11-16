# Complete SQLite Database Logic & Code Specification

> **Purpose:** This document is an exhaustive, line-by-line, statement-by-statement technical specification of every SQLite table, schema definition, migration step, PRAGMA command, transaction boundary, and SQL query in the repository. It contains all 239 individual SQLite operations across both application and test files. Every query is written verbatim with parameter bindings and operational context to allow complete conversion to another database engine (PostgreSQL, MySQL, SQLAlchemy, Prisma).

---

## 1. Database Connection, PRAGMAs & Transaction Architecture

### 1.1 Connection Factory & PRAGMAs
- **File:** `app/db.py:18-26`
- **Method:** `get_db(db_name=None)`
- **Database Resolution (`get_database_name()`):**
  - App Context: `current_app.config.get("DATABASE_NAME") or "My_Medical_Shope.db"`
  - Non-App Context: `os.getenv("DATABASE_NAME", "My_Medical_Shope.db")`
- **Exact Code & PRAGMA Executions:**
```python
conn = sqlite3.connect(db_name or get_database_name(), timeout=5)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
conn.execute("PRAGMA foreign_keys=ON")
```
- **Engine Rules:**
  - `PRAGMA journal_mode=WAL`: Enables Write-Ahead Logging to prevent concurrent read locks from blocking writes and vice versa.
  - `PRAGMA busy_timeout=5000`: Directs SQLite to wait up to 5,000 milliseconds when encountering a locked database before raising `sqlite3.OperationalError: database is locked`.
  - `PRAGMA foreign_keys=ON`: Enforces foreign key referential integrity at the database engine level on each new connection.

### 1.2 Transaction Scoping Context Manager
- **File:** `app/db.py:29-45`
- **Method:** `db_connection(immediate=False, db_name=None)`
- **Exact Implementation:**
```python
@contextmanager
def db_connection(immediate=False, db_name=None):
    conn = get_db(db_name)
    try:
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
```
- **`BEGIN IMMEDIATE`**: Acquires a reserved lock on the SQLite database immediately at transaction start, ensuring that no other write transaction can begin concurrently. Used across all inventory, order, user, and admin mutations to prevent deadlocks and race conditions.

### 1.3 Savepoint Scoping in Stock Operations
- **File:** `app/services/stock_service.py:26-38`
- **Method:** `_savepoint(conn)`
- **Exact Implementation:**
```python
@contextmanager
def _savepoint(conn):
    name = "sp_" + uuid.uuid4().hex[:8]
    conn.execute(f"SAVEPOINT {name}")
    try:
        yield
    except BaseException:
        conn.execute(f"ROLLBACK TO SAVEPOINT {name}")
        conn.execute(f"RELEASE SAVEPOINT {name}")
        raise
    else:
        conn.execute(f"RELEASE SAVEPOINT {name}")
```

### 1.4 Online Backup Mechanism
- **File:** `app/services/db_init.py:254-266`
- **Method:** `_backup_if_needed(db_path, backup=None)`
- **Exact Implementation:**
```python
def _backup_if_needed(db_path, backup=None):
    target_path = f"{db_path}.bak-{timestamp}"
    source = get_db(db_path)
    try:
        target = sqlite3.connect(target_path)
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()
```

---

## 2. Complete Schema DDL (Exact Statements)

All DDL statements are defined in `app/services/db_init.py`.

### 2.1 Core & Legacy Tables

#### Table: `Admin`
```sql
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
);
```

#### Table: `Users`
```sql
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
);
```

#### Table: `Products`
```sql
CREATE TABLE IF NOT EXISTS Products(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    Product_id VARCHAR(255) UNIQUE,
    name VARCHAR(255),
    price FLOAT,
    category VARCHAR(255),
    stock INTEGER,
    image_url VARCHAR(1000) DEFAULT NULL
);
```

#### Table: `Order_Details`
```sql
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
);
```

#### Table: `Sell_History`
```sql
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
);
```

---

### 2.2 New Domain Tables (Parts 1, 2 & 3)

#### Table: `Suppliers`
```sql
CREATE TABLE IF NOT EXISTS Suppliers(
    Supplier_id TEXT PRIMARY KEY,
    name TEXT NOT NULL DEFAULT '' CHECK(length(name) > 0),
    contact_phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    gst_number TEXT DEFAULT '',
    address TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);
```

#### Table: `Product_Batches`
```sql
CREATE TABLE IF NOT EXISTS Product_Batches(
    Batch_id TEXT PRIMARY KEY,
    Product_id TEXT NOT NULL DEFAULT '' REFERENCES Products(Product_id),
    batch_no TEXT NOT NULL DEFAULT '' CHECK(length(batch_no) > 0),
    mfg_date TEXT,
    expiry_date TEXT NOT NULL DEFAULT '' CHECK(length(expiry_date) = 10),
    quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
    purchase_price REAL DEFAULT 0,
    mrp REAL DEFAULT 0,
    supplier_id TEXT REFERENCES Suppliers(Supplier_id),
    supplier_name TEXT DEFAULT '',
    received_date TEXT,
    is_legacy_placeholder INTEGER NOT NULL DEFAULT 0,
    created_at TEXT,
    updated_at TEXT,
    UNIQUE(Product_id, batch_no)
);
```

#### Table: `Stock_Movements`
```sql
CREATE TABLE IF NOT EXISTS Stock_Movements(
    Movement_id TEXT PRIMARY KEY,
    Product_id TEXT NOT NULL DEFAULT '' REFERENCES Products(Product_id),
    Batch_id TEXT REFERENCES Product_Batches(Batch_id),
    change_qty INTEGER NOT NULL DEFAULT 0 CHECK(change_qty <> 0),
    reason TEXT NOT NULL DEFAULT '' CHECK(reason IN
        ('PURCHASE','SALE','ADJUSTMENT','EXPIRED_WRITEOFF','RETURN','CANCEL_RESTOCK')),
    reference_id TEXT DEFAULT '',
    performed_by TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT ''
);
```

#### Table: `Audit_Log`
```sql
CREATE TABLE IF NOT EXISTS Audit_Log(
    Audit_id TEXT PRIMARY KEY,
    actor_id TEXT,
    actor_role TEXT,
    action TEXT NOT NULL DEFAULT '',
    entity TEXT NOT NULL DEFAULT '',
    entity_id TEXT,
    details TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT ''
);
```

#### Table: `Device_Tokens`
```sql
CREATE TABLE IF NOT EXISTS Device_Tokens(
    Device_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT '',
    token TEXT NOT NULL DEFAULT '' UNIQUE,
    platform TEXT NOT NULL DEFAULT 'android' CHECK(platform IN ('android','ios')),
    app_version TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);
```

#### Table: `Idempotency_Keys`
```sql
CREATE TABLE IF NOT EXISTS Idempotency_Keys(
    key TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '',
    endpoint TEXT NOT NULL DEFAULT '',
    response_json TEXT,
    status_code INTEGER NOT NULL DEFAULT 0,
    location TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(key, user_id, endpoint)
);
```

---

### 2.3 Additive Column Migrations (`ADD_COLUMNS`)
Defined in `app/services/db_init.py:166-224` and applied via `ALTER TABLE {table} ADD COLUMN {col} {decl}`:

#### On `Admin`:
```sql
ALTER TABLE Admin ADD COLUMN role VARCHAR(20) DEFAULT 'admin';
ALTER TABLE Admin ADD COLUMN image_url VARCHAR(1000) DEFAULT NULL;
ALTER TABLE Admin ADD COLUMN is_approved INTEGER DEFAULT 1;
ALTER TABLE Admin ADD COLUMN is_owner INTEGER DEFAULT 0;
ALTER TABLE Admin ADD COLUMN is_email_verified INTEGER DEFAULT 1;
```

#### On `Users`:
```sql
ALTER TABLE Users ADD COLUMN image_url VARCHAR(1000) DEFAULT NULL;
ALTER TABLE Users ADD COLUMN is_email_verified INTEGER DEFAULT 1;
```

#### On `Products`:
```sql
ALTER TABLE Products ADD COLUMN image_url VARCHAR(1000) DEFAULT NULL;
ALTER TABLE Products ADD COLUMN generic_name TEXT DEFAULT '';
ALTER TABLE Products ADD COLUMN brand_name TEXT DEFAULT '';
ALTER TABLE Products ADD COLUMN manufacturer TEXT DEFAULT 'Unknown';
ALTER TABLE Products ADD COLUMN category TEXT DEFAULT 'General';
ALTER TABLE Products ADD COLUMN dosage_form TEXT DEFAULT 'Tablet';
ALTER TABLE Products ADD COLUMN strength TEXT DEFAULT '';
ALTER TABLE Products ADD COLUMN pack_size TEXT DEFAULT '';
ALTER TABLE Products ADD COLUMN unit TEXT DEFAULT 'strip';
ALTER TABLE Products ADD COLUMN hsn_code TEXT DEFAULT '';
ALTER TABLE Products ADD COLUMN gst_percent REAL DEFAULT 12;
ALTER TABLE Products ADD COLUMN mrp REAL DEFAULT 0;
ALTER TABLE Products ADD COLUMN purchase_price REAL DEFAULT 0;
ALTER TABLE Products ADD COLUMN schedule_type TEXT DEFAULT 'OTC';
ALTER TABLE Products ADD COLUMN requires_prescription INTEGER DEFAULT 0;
ALTER TABLE Products ADD COLUMN storage_conditions TEXT DEFAULT '';
ALTER TABLE Products ADD COLUMN reorder_level INTEGER DEFAULT 10;
ALTER TABLE Products ADD COLUMN barcode TEXT DEFAULT '';
ALTER TABLE Products ADD COLUMN is_active INTEGER DEFAULT 1;
ALTER TABLE Products ADD COLUMN created_at TEXT DEFAULT NULL;
ALTER TABLE Products ADD COLUMN updated_at TEXT DEFAULT NULL;
```

#### On `Order_Details`:
```sql
ALTER TABLE Order_Details ADD COLUMN image_url VARCHAR(1000) DEFAULT NULL;
ALTER TABLE Order_Details ADD COLUMN prescription_url TEXT DEFAULT '';
ALTER TABLE Order_Details ADD COLUMN doctor_name TEXT DEFAULT '';
ALTER TABLE Order_Details ADD COLUMN patient_name TEXT DEFAULT '';
ALTER TABLE Order_Details ADD COLUMN prescription_verified INTEGER DEFAULT 0;
ALTER TABLE Order_Details ADD COLUMN status TEXT DEFAULT 'pending';
ALTER TABLE Order_Details ADD COLUMN cancel_reason TEXT DEFAULT '';
ALTER TABLE Order_Details ADD COLUMN updated_at TEXT DEFAULT NULL;
```

#### On `Sell_History`:
```sql
ALTER TABLE Sell_History ADD COLUMN image_url VARCHAR(1000) DEFAULT NULL;
ALTER TABLE Sell_History ADD COLUMN batch_id TEXT DEFAULT '';
ALTER TABLE Sell_History ADD COLUMN batch_no TEXT DEFAULT '';
ALTER TABLE Sell_History ADD COLUMN gst_percent REAL DEFAULT 0;
ALTER TABLE Sell_History ADD COLUMN sold_by TEXT DEFAULT '';
```

---

### 2.4 Complete Index Definitions
Defined in `app/services/db_init.py:226-244`:
```sql
CREATE INDEX IF NOT EXISTS ix_products_barcode ON Products(barcode);
CREATE INDEX IF NOT EXISTS ix_products_name ON Products(name);
CREATE INDEX IF NOT EXISTS ix_batches_product ON Product_Batches(Product_id);
CREATE INDEX IF NOT EXISTS ix_batches_expiry ON Product_Batches(expiry_date);
CREATE INDEX IF NOT EXISTS ix_orders_user ON Order_Details(user_id);
CREATE INDEX IF NOT EXISTS ix_orders_status ON Order_Details(status);
CREATE INDEX IF NOT EXISTS ix_sell_order ON Sell_History(Order_id);
CREATE INDEX IF NOT EXISTS ix_sell_user ON Sell_History(user_id);
CREATE INDEX IF NOT EXISTS ix_sell_product ON Sell_History(product_id);
CREATE INDEX IF NOT EXISTS ix_movements_product ON Stock_Movements(Product_id, created_at);
CREATE INDEX IF NOT EXISTS ix_movements_created ON Stock_Movements(created_at);
CREATE INDEX IF NOT EXISTS ix_audit_entity ON Audit_Log(entity, entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_created ON Audit_Log(created_at);
CREATE INDEX IF NOT EXISTS ix_device_user ON Device_Tokens(user_id);
CREATE INDEX IF NOT EXISTS ix_idempotency_created ON Idempotency_Keys(created_at);
CREATE UNIQUE INDEX IF NOT EXISTS ux_admin_owner ON Admin(is_owner) WHERE is_owner = 1;
```

---

## 3. Data Migrations & Backfill Queries (Verbatim)

Defined in `app/services/db_init.py:307-360`:

### 3.1 Legacy Image Backfills
```sql
UPDATE Order_Details SET image_url = (
    SELECT Products.image_url FROM Products WHERE Products.Product_id = Order_Details.product_id
) WHERE image_url IS NULL;

UPDATE Sell_History SET image_url = (
    SELECT Products.image_url FROM Products WHERE Products.Product_id = Sell_History.product_id
) WHERE image_url IS NULL;
```

### 3.2 Product Timestamps Backfill
```sql
UPDATE Products SET created_at = ? WHERE created_at IS NULL;
-- Params: [utc_now_iso()]

UPDATE Products SET updated_at = COALESCE(created_at, ?) WHERE updated_at IS NULL;
-- Params: [utc_now_iso()]
```

### 3.3 Order Status Flag Derivation Backfill
```sql
UPDATE Order_Details SET status = CASE
    WHEN sold IN (1, '1', 'true', 'True')
      OR EXISTS (SELECT 1 FROM Sell_History s WHERE s.Order_id = Order_Details.Order_id)
        THEN 'sold'
    WHEN isApproved IN (1, '1', 'true', 'True') THEN 'approved'
    ELSE 'pending' END;
```

### 3.4 Legacy Batch Backfill Query
```sql
SELECT Product_id, CAST(COALESCE(stock, 0) AS INTEGER) AS qty, COALESCE(purchase_price, 0) AS pp,
       COALESCE(mrp, 0) AS mrp
FROM Products p
WHERE p.Product_id IS NOT NULL
  AND CAST(COALESCE(p.stock, 0) AS INTEGER) > 0
  AND NOT EXISTS (SELECT 1 FROM Product_Batches b WHERE b.Product_id = p.Product_id);

INSERT OR IGNORE INTO Product_Batches(
    Batch_id, Product_id, batch_no, mfg_date, expiry_date, quantity,
    purchase_price, mrp, supplier_id, supplier_name, received_date, is_legacy_placeholder,
    created_at, updated_at
) VALUES (?, ?, ?, NULL, ?, ?, ?, ?, NULL, '', NULL, 1, ?, ?);
-- Params: [f"BAT_LEGACY_{product_id}", product_id, f"LEGACY-{product_id}", "9999-12-31", qty, pp, mrp, now, now]

INSERT OR IGNORE INTO Stock_Movements(
    Movement_id, Product_id, Batch_id, change_qty, reason,
    reference_id, performed_by, created_at
) VALUES (?, ?, ?, ?, 'ADJUSTMENT', 'LEGACY-OPENING-BALANCE', 'system:migration', ?);
-- Params: [f"MOV_LEGACY_{product_id}", product_id, f"BAT_LEGACY_{product_id}", qty, now]
```

### 3.5 Plaintext Password Hashing Migration
```sql
SELECT id, password FROM Users;

UPDATE Users SET password = ? WHERE id = ?;
-- Params: [generate_password_hash(pwd), row_id]
```

---

## 4. Complete Application SQLite Operations Inventory (Logics #1 to #181)

This section documents every operational SQLite call executed in the application runtime.

### Operation #1: `app/cli.py:33` in `approve_admin_command()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute("SELECT admin_id, role FROM Admin WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
```
- **Query / SQL Expression:**
```sql
'SELECT admin_id, role FROM Admin WHERE LOWER(email) = LOWER(?)'
```
- **Bound Parameters:** `(email,)`

### Operation #2: `app/cli.py:38` in `approve_admin_command()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("UPDATE Admin SET is_owner = 0 WHERE is_owner IN (1, '1') AND admin_id <> ?", (admin_id,))
```
- **Query / SQL Expression:**
```sql
"UPDATE Admin SET is_owner = 0 WHERE is_owner IN (1, '1') AND admin_id <> ?"
```
- **Bound Parameters:** `(admin_id,)`

### Operation #3: `app/cli.py:39` in `approve_admin_command()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
"UPDATE Admin SET is_approved = 1, role = 'admin'" + (', is_owner = 1' if owner else '') + ' WHERE admin_id = ?'
```
- **Bound Parameters:** `(admin_id,)`

### Operation #4: `app/db.py:23` in `get_db()`
- **Method Type:** `connect`
- **Code Statement:**
```python
conn = sqlite3.connect(db_name or get_database_name(), timeout=5)
```
- **Query / SQL Expression:**
```sql
db_name or get_database_name()
```

### Operation #5: `app/db.py:25` in `get_db()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("PRAGMA journal_mode=WAL")
```
- **Query / SQL Expression:**
```sql
'PRAGMA journal_mode=WAL'
```

### Operation #6: `app/db.py:26` in `get_db()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("PRAGMA busy_timeout=5000")
```
- **Query / SQL Expression:**
```sql
'PRAGMA busy_timeout=5000'
```

### Operation #7: `app/db.py:27` in `get_db()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("PRAGMA foreign_keys=ON")
```
- **Query / SQL Expression:**
```sql
'PRAGMA foreign_keys=ON'
```

### Operation #8: `app/db.py:41` in `db_connection()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("BEGIN IMMEDIATE")
```
- **Query / SQL Expression:**
```sql
'BEGIN IMMEDIATE'
```

### Operation #9: `app/db.py:43` in `db_connection()`
- **Method Type:** `commit`
- **Code Statement:**
```python
conn.commit()
```

### Operation #10: `app/db.py:45` in `db_connection()`
- **Method Type:** `rollback`
- **Code Statement:**
```python
conn.rollback()
```

### Operation #11: `app/db.py:48` in `db_connection()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #12: `app/routes/admin.py:49` in `list_admins()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #13: `app/routes/admin.py:126` in `register_admin()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("DELETE FROM Admin WHERE admin_id = ? AND COALESCE(is_email_verified, 0) = 0", (admin_id,))
```
- **Query / SQL Expression:**
```sql
'DELETE FROM Admin WHERE admin_id = ? AND COALESCE(is_email_verified, 0) = 0'
```
- **Bound Parameters:** `(admin_id,)`

### Operation #14: `app/routes/admin.py:154` in `get_admin()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #15: `app/routes/admin.py:178` in `update_admin()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #16: `app/routes/auth.py:42` in `login()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #17: `app/routes/auth.py:131` in `refresh()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #18: `app/routes/auth.py:170` in `password_reset_request()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #19: `app/routes/auth.py:196` in `password_reset_confirm()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #20: `app/routes/health.py:25` in `ready()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("SELECT 1").fetchone()
```
- **Query / SQL Expression:**
```sql
'SELECT 1'
```

### Operation #21: `app/routes/health.py:27` in `ready()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #22: `app/routes/inventory.py:87` in `list_product_batches()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #23: `app/routes/inventory.py:125` in `get_batch()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #24: `app/routes/inventory.py:276` in `list_stock_movements()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #25: `app/routes/inventory.py:288` in `_batch_alert_response()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #26: `app/routes/inventory.py:298` in `_product_alert_response()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #27: `app/routes/meta.py:108` in `register_device()`
- **Method Type:** `execute`
- **Code Statement:**
```python
existing = conn.execute("SELECT * FROM Device_Tokens WHERE token = ?", (cleaned["token"],)).fetchone()
```
- **Query / SQL Expression:**
```sql
'SELECT * FROM Device_Tokens WHERE token = ?'
```
- **Bound Parameters:** `(cleaned['token'],)`

### Operation #28: `app/routes/meta.py:111` in `register_device()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
'UPDATE Device_Tokens SET user_id = ?, platform = ?, app_version = ?, is_active = 1, updated_at = ?\n                   WHERE Device_id = ?'
```
- **Bound Parameters:** `(identity, cleaned['platform'], cleaned['app_version'], now, device_id)`

### Operation #29: `app/routes/meta.py:117` in `register_device()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
'INSERT INTO Device_Tokens(Device_id, user_id, token, platform, app_version, is_active, created_at,\n                       updated_at) VALUES (?, ?, ?, ?, ?, 1, ?, ?)'
```
- **Bound Parameters:** `(device_id, identity, cleaned['token'], cleaned['platform'], cleaned['app_version'], now, now)`

### Operation #30: `app/routes/meta.py:123` in `register_device()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute("SELECT * FROM Device_Tokens WHERE Device_id = ?", (device_id,)).fetchone()
```
- **Query / SQL Expression:**
```sql
'SELECT * FROM Device_Tokens WHERE Device_id = ?'
```
- **Bound Parameters:** `(device_id,)`

### Operation #31: `app/routes/meta.py:134` in `delete_device()`
- **Method Type:** `execute`
- **Code Statement:**
```python
cur = conn.execute(
```
- **Query / SQL Expression:**
```sql
'UPDATE Device_Tokens SET is_active = 0, updated_at = ? WHERE Device_id = ? AND user_id = ? AND is_active = 1'
```
- **Bound Parameters:** `(utc_now_iso(), device_id, identity)`

### Operation #32: `app/routes/meta.py:140` in `delete_device()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute("SELECT * FROM Device_Tokens WHERE Device_id = ?", (device_id,)).fetchone()
```
- **Query / SQL Expression:**
```sql
'SELECT * FROM Device_Tokens WHERE Device_id = ?'
```
- **Bound Parameters:** `(device_id,)`

### Operation #33: `app/routes/order.py:63` in `_orders_page()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #34: `app/routes/order.py:112` in `get_order()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #35: `app/routes/order.py:124` in `get_invoice()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #36: `app/routes/order.py:152` in `create_order()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #37: `app/routes/order.py:222` in `upload_prescription()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #38: `app/routes/order.py:362` in `list_sales()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #39: `app/routes/product.py:65` in `list_products()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #40: `app/routes/product.py:103` in `get_product()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #41: `app/routes/product.py:116` in `update_product()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #42: `app/routes/product.py:148` in `get_product_by_barcode()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #43: `app/routes/product.py:186` in `list_product_categories()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #44: `app/routes/report.py:35` in `dashboard_summary()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #45: `app/routes/report.py:52` in `sales_report()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #46: `app/routes/report.py:67` in `top_products()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #47: `app/routes/report.py:95` in `list_audit_logs()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #48: `app/routes/supplier.py:30` in `list_suppliers()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #49: `app/routes/supplier.py:56` in `get_supplier()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #50: `app/routes/user.py:83` in `list_users()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #51: `app/routes/user.py:104` in `get_me()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #52: `app/routes/user.py:120` in `update_me()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #53: `app/routes/user.py:149` in `get_user()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #54: `app/services/account_service.py:104` in `fetch_user()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,)).fetchone()
```
- **Query / SQL Expression:**
```sql
'SELECT * FROM Users WHERE user_id = ?'
```
- **Bound Parameters:** `(user_id,)`

### Operation #55: `app/services/account_service.py:112` in `ensure_user_unique()`
- **Method Type:** `execute`
- **Code Statement:**
```python
if conn.execute("SELECT 1 FROM Users WHERE LOWER(email) = LOWER(?) AND user_id IS NOT ?",
```
- **Query / SQL Expression:**
```sql
'SELECT 1 FROM Users WHERE LOWER(email) = LOWER(?) AND user_id IS NOT ?'
```
- **Bound Parameters:** `(email, exclude_id)`

### Operation #56: `app/services/account_service.py:116` in `ensure_user_unique()`
- **Method Type:** `execute`
- **Code Statement:**
```python
if conn.execute("SELECT 1 FROM Users WHERE phone_number = ? AND user_id IS NOT ?",
```
- **Query / SQL Expression:**
```sql
'SELECT 1 FROM Users WHERE phone_number = ? AND user_id IS NOT ?'
```
- **Bound Parameters:** `(phone, exclude_id)`

### Operation #57: `app/services/account_service.py:124` in `insert_user()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
"INSERT INTO Users(user_id, password, date_of_account_creation, isApproved, block, name, address,\n                   email, phone_number, pin_code, role, image_url)\n               VALUES (?, ?, ?, 0, 0, ?, ?, ?, ?, ?, 'user', ?)"
```
- **Bound Parameters:** `(user_id, hash_password(cleaned['password']), utc_now_iso(), cleaned['name'], cleaned.get('address'), cleaned.get('email'), cleaned.get('phone_number'), cleaned.get('pin_code'), cleaned.get('image_url'))`

### Operation #58: `app/services/account_service.py:152` in `update_user()`
- **Method Type:** `execute`
- **Code Statement:**
```python
cur = conn.execute(
```
- **Query / SQL Expression:**
```sql
f"UPDATE Users SET {', '.join(sets)} WHERE user_id = ? AND COALESCE(role, 'user') <> 'deleted'"
```
- **Bound Parameters:** `params + [user_id]`

### Operation #59: `app/services/account_service.py:170` in `set_user_flags()`
- **Method Type:** `execute`
- **Code Statement:**
```python
cur = conn.execute(
```
- **Query / SQL Expression:**
```sql
f"UPDATE Users SET {', '.join(sets)} WHERE user_id = ? AND COALESCE(role, 'user') <> 'deleted'"
```
- **Bound Parameters:** `params + [user_id]`

### Operation #60: `app/services/account_service.py:195` in `list_users()`
- **Method Type:** `execute`
- **Code Statement:**
```python
total = conn.execute(f"SELECT COUNT(*) FROM Users{where_sql}", params).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(*) FROM Users{where_sql}'
```
- **Bound Parameters:** `params`

### Operation #61: `app/services/account_service.py:197` in `list_users()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'SELECT * FROM Users{where_sql} ORDER BY {USER_SORT[sort]} {direction}, id {direction} LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `params + [limit, offset]`

### Operation #62: `app/services/account_service.py:238` in `fetch_admin()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute("SELECT * FROM Admin WHERE admin_id = ?", (admin_id,)).fetchone()
```
- **Query / SQL Expression:**
```sql
'SELECT * FROM Admin WHERE admin_id = ?'
```
- **Bound Parameters:** `(admin_id,)`

### Operation #63: `app/services/account_service.py:250` in `approved_admin_count()`
- **Method Type:** `execute`
- **Code Statement:**
```python
return conn.execute(f"SELECT COUNT(*) FROM Admin WHERE {APPROVED_ACTIVE_SQL}").fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(*) FROM Admin WHERE {APPROVED_ACTIVE_SQL}'
```

### Operation #64: `app/services/account_service.py:273` in `has_live_admin()`
- **Method Type:** `execute`
- **Code Statement:**
```python
return conn.execute(
```
- **Query / SQL Expression:**
```sql
"SELECT 1 FROM Admin WHERE COALESCE(role, 'admin') <> 'deleted' OR is_owner IN (1, '1') LIMIT 1"
```

### Operation #65: `app/services/account_service.py:279` in `ensure_admin_unique()`
- **Method Type:** `execute`
- **Code Statement:**
```python
if email and conn.execute("SELECT 1 FROM Admin WHERE LOWER(email) = LOWER(?) AND admin_id IS NOT ?",
```
- **Query / SQL Expression:**
```sql
'SELECT 1 FROM Admin WHERE LOWER(email) = LOWER(?) AND admin_id IS NOT ?'
```
- **Bound Parameters:** `(email, exclude_id)`

### Operation #66: `app/services/account_service.py:282` in `ensure_admin_unique()`
- **Method Type:** `execute`
- **Code Statement:**
```python
if phone and conn.execute("SELECT 1 FROM Admin WHERE phone_number = ? AND admin_id IS NOT ?",
```
- **Query / SQL Expression:**
```sql
'SELECT 1 FROM Admin WHERE phone_number = ? AND admin_id IS NOT ?'
```
- **Bound Parameters:** `(phone, exclude_id)`

### Operation #67: `app/services/account_service.py:291` in `insert_admin()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
"INSERT INTO Admin(admin_id, password, name, email, phone_number, date_of_account_creation, role,\n                   image_url, is_approved, is_owner, is_email_verified) VALUES (?, ?, ?, ?, ?, ?, 'admin', ?, ?, ?, ?)"
```
- **Bound Parameters:** `(admin_id, password_hash or hash_password(cleaned['password']), cleaned['name'], cleaned['email'], cleaned.get('phone_number') or None, utc_now_iso(), cleaned.get('image_url'), 1 if is_approved else 0, 1 if is_owner else 0, 1 if email_verified else 0)`

### Operation #68: `app/services/account_service.py:306` in `approve_admin()`
- **Method Type:** `execute`
- **Code Statement:**
```python
cur = conn.execute(
```
- **Query / SQL Expression:**
```sql
"UPDATE Admin SET is_approved = 1 WHERE admin_id = ? AND COALESCE(role, 'admin') <> 'deleted'"
```
- **Bound Parameters:** `(admin_id,)`

### Operation #69: `app/services/account_service.py:327` in `update_admin()`
- **Method Type:** `execute`
- **Code Statement:**
```python
cur = conn.execute(
```
- **Query / SQL Expression:**
```sql
f"UPDATE Admin SET {', '.join(sets)} WHERE admin_id = ? AND COALESCE(role, 'admin') <> 'deleted'"
```
- **Bound Parameters:** `params + [admin_id]`

### Operation #70: `app/services/account_service.py:348` in `list_admins()`
- **Method Type:** `execute`
- **Code Statement:**
```python
total = conn.execute(f"SELECT COUNT(*) FROM Admin{where_sql}", params).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(*) FROM Admin{where_sql}'
```
- **Bound Parameters:** `params`

### Operation #71: `app/services/account_service.py:350` in `list_admins()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'SELECT * FROM Admin{where_sql} ORDER BY {ADMIN_SORT[sort]} {direction}, id {direction} LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `params + [limit, offset]`

### Operation #72: `app/services/audit_service.py:25` in `write_audit()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
'INSERT INTO Audit_Log(Audit_id, actor_id, actor_role, action, entity, entity_id, details, created_at)\n           VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
```
- **Bound Parameters:** `(audit_id, None if actor_id is None else str(actor_id), actor_role, action, entity, None if entity_id is None else str(entity_id), json.dumps(_scrub(details or {}), default=str, sort_keys=True), utc_now_iso())`

### Operation #73: `app/services/auth_service.py:40` in `find_account_by_email()`
- **Method Type:** `execute`
- **Code Statement:**
```python
return conn.execute(f"SELECT * FROM {table} WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
```
- **Query / SQL Expression:**
```sql
f'SELECT * FROM {table} WHERE LOWER(email) = LOWER(?)'
```
- **Bound Parameters:** `(email,)`

### Operation #74: `app/services/auth_service.py:45` in `fetch_account()`
- **Method Type:** `execute`
- **Code Statement:**
```python
return conn.execute(f"SELECT * FROM {table} WHERE {id_col} = ?", (account_id,)).fetchone()
```
- **Query / SQL Expression:**
```sql
f'SELECT * FROM {table} WHERE {id_col} = ?'
```
- **Bound Parameters:** `(account_id,)`

### Operation #75: `app/services/auth_service.py:180` in `mark_email_verified()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(f"UPDATE {table} SET is_email_verified = 1 WHERE {id_col} = ?", (account_id,))
```
- **Query / SQL Expression:**
```sql
f'UPDATE {table} SET is_email_verified = 1 WHERE {id_col} = ?'
```
- **Bound Parameters:** `(account_id,)`

### Operation #76: `app/services/bootstrap.py:21` in `bootstrap_admin()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute("SELECT admin_id FROM Admin WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
```
- **Query / SQL Expression:**
```sql
'SELECT admin_id FROM Admin WHERE LOWER(email) = LOWER(?)'
```
- **Bound Parameters:** `(email,)`

### Operation #77: `app/services/bootstrap.py:30` in `bootstrap_admin()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("UPDATE Admin SET is_owner = 0 WHERE is_owner IN (1, '1') AND admin_id <> ?", (admin_id,))
```
- **Query / SQL Expression:**
```sql
"UPDATE Admin SET is_owner = 0 WHERE is_owner IN (1, '1') AND admin_id <> ?"
```
- **Bound Parameters:** `(admin_id,)`

### Operation #78: `app/services/bootstrap.py:31` in `bootstrap_admin()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("UPDATE Admin SET is_approved = 1, is_owner = 1, is_email_verified = 1, role = 'admin' "
```
- **Query / SQL Expression:**
```sql
"UPDATE Admin SET is_approved = 1, is_owner = 1, is_email_verified = 1, role = 'admin' WHERE admin_id = ?"
```
- **Bound Parameters:** `(admin_id,)`

### Operation #79: `app/services/db_init.py:261` in `_table_exists()`
- **Method Type:** `execute`
- **Code Statement:**
```python
return conn.execute(
```
- **Query / SQL Expression:**
```sql
"SELECT 1 FROM sqlite_master WHERE type='table' AND name=?"
```
- **Bound Parameters:** `(table,)`

### Operation #80: `app/services/db_init.py:268` in `_columns()`
- **Method Type:** `execute`
- **Code Statement:**
```python
return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
```
- **Query / SQL Expression:**
```sql
f'PRAGMA table_info({table})'
```

### Operation #81: `app/services/db_init.py:294` in `backup_database()`
- **Method Type:** `connect`
- **Code Statement:**
```python
src = sqlite3.connect(db_path)
```
- **Query / SQL Expression:**
```sql
db_path
```

### Operation #82: `app/services/db_init.py:295` in `backup_database()`
- **Method Type:** `connect`
- **Code Statement:**
```python
dst = sqlite3.connect(target)
```
- **Query / SQL Expression:**
```sql
target
```

### Operation #83: `app/services/db_init.py:297` in `backup_database()`
- **Method Type:** `backup`
- **Code Statement:**
```python
src.backup(dst)
```
- **Query / SQL Expression:**
```sql
dst
```

### Operation #84: `app/services/db_init.py:299` in `backup_database()`
- **Method Type:** `close`
- **Code Statement:**
```python
dst.close()
```

### Operation #85: `app/services/db_init.py:300` in `backup_database()`
- **Method Type:** `close`
- **Code Statement:**
```python
src.close()
```

### Operation #86: `app/services/db_init.py:316` in `_backup_if_needed()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #87: `app/services/db_init.py:330` in `createTable()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("BEGIN IMMEDIATE")
```
- **Query / SQL Expression:**
```sql
'BEGIN IMMEDIATE'
```

### Operation #88: `app/services/db_init.py:332` in `createTable()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(ddl)
```
- **Query / SQL Expression:**
```sql
ddl
```

### Operation #89: `app/services/db_init.py:336` in `createTable()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
'CREATE UNIQUE INDEX IF NOT EXISTS ux_products_product_id ON Products(Product_id)'
```

### Operation #90: `app/services/db_init.py:345` in `createTable()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(ddl)
```
- **Query / SQL Expression:**
```sql
ddl
```

### Operation #91: `app/services/db_init.py:346` in `createTable()`
- **Method Type:** `commit`
- **Code Statement:**
```python
conn.commit()
```

### Operation #92: `app/services/db_init.py:348` in `createTable()`
- **Method Type:** `rollback`
- **Code Statement:**
```python
conn.rollback()
```

### Operation #93: `app/services/db_init.py:351` in `createTable()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #94: `app/services/db_init.py:361` in `updateTable()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("BEGIN IMMEDIATE")
```
- **Query / SQL Expression:**
```sql
'BEGIN IMMEDIATE'
```

### Operation #95: `app/services/db_init.py:367` in `updateTable()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
```
- **Query / SQL Expression:**
```sql
f'ALTER TABLE {table} ADD COLUMN {name} {decl}'
```

### Operation #96: `app/services/db_init.py:371` in `updateTable()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("""
```
- **Query / SQL Expression:**
```sql
'\n            UPDATE Order_Details SET image_url = (\n                SELECT Products.image_url FROM Products WHERE Products.Product_id = Order_Details.product_id)\n            WHERE image_url IS NULL'
```

### Operation #97: `app/services/db_init.py:375` in `updateTable()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("""
```
- **Query / SQL Expression:**
```sql
'\n            UPDATE Sell_History SET image_url = (\n                SELECT Products.image_url FROM Products WHERE Products.Product_id = Sell_History.product_id)\n            WHERE image_url IS NULL'
```

### Operation #98: `app/services/db_init.py:381` in `updateTable()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("UPDATE Products SET created_at = ? WHERE created_at IS NULL", (now,))
```
- **Query / SQL Expression:**
```sql
'UPDATE Products SET created_at = ? WHERE created_at IS NULL'
```
- **Bound Parameters:** `(now,)`

### Operation #99: `app/services/db_init.py:382` in `updateTable()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("UPDATE Products SET updated_at = COALESCE(created_at, ?) WHERE updated_at IS NULL", (now,))
```
- **Query / SQL Expression:**
```sql
'UPDATE Products SET updated_at = COALESCE(created_at, ?) WHERE updated_at IS NULL'
```
- **Bound Parameters:** `(now,)`

### Operation #100: `app/services/db_init.py:386` in `updateTable()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("""
```
- **Query / SQL Expression:**
```sql
"\n                UPDATE Order_Details SET status = CASE\n                    WHEN sold IN (1, '1', 'true', 'True')\n                      OR EXISTS (SELECT 1 FROM Sell_History s WHERE s.Order_id = Order_Details.Order_id)\n                        THEN 'sold'\n                    WHEN isApproved IN (1, '1', 'true', 'True') THEN 'approved'\n                    ELSE 'pending' END"
```

### Operation #101: `app/services/db_init.py:397` in `updateTable()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(ddl)
```
- **Query / SQL Expression:**
```sql
ddl
```

### Operation #102: `app/services/db_init.py:398` in `updateTable()`
- **Method Type:** `commit`
- **Code Statement:**
```python
conn.commit()
```

### Operation #103: `app/services/db_init.py:400` in `updateTable()`
- **Method Type:** `rollback`
- **Code Statement:**
```python
conn.rollback()
```

### Operation #104: `app/services/db_init.py:403` in `updateTable()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #105: `app/services/db_init.py:412` in `_backfill_legacy_batches()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute("""
```
- **Query / SQL Expression:**
```sql
'\n        SELECT Product_id, CAST(COALESCE(stock, 0) AS INTEGER) AS qty, COALESCE(purchase_price, 0) AS pp,\n               COALESCE(mrp, 0) AS mrp\n        FROM Products p\n        WHERE p.Product_id IS NOT NULL\n          AND CAST(COALESCE(p.stock, 0) AS INTEGER) > 0\n          AND NOT EXISTS (SELECT 1 FROM Product_Batches b WHERE b.Product_id = p.Product_id)\n    '
```

### Operation #106: `app/services/db_init.py:423` in `_backfill_legacy_batches()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("""
```
- **Query / SQL Expression:**
```sql
"\n            INSERT OR IGNORE INTO Product_Batches(Batch_id, Product_id, batch_no, mfg_date, expiry_date, quantity,\n                purchase_price, mrp, supplier_id, supplier_name, received_date, is_legacy_placeholder,\n                created_at, updated_at)\n            VALUES (?, ?, ?, NULL, ?, ?, ?, ?, NULL, '', NULL, 1, ?, ?)"
```
- **Bound Parameters:** `(batch_id, product_id, f'LEGACY-{product_id}', LEGACY_BATCH_EXPIRY, qty, row['pp'], row['mrp'], now, now)`

### Operation #107: `app/services/db_init.py:430` in `_backfill_legacy_batches()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("""
```
- **Query / SQL Expression:**
```sql
"\n            INSERT OR IGNORE INTO Stock_Movements(Movement_id, Product_id, Batch_id, change_qty, reason,\n                reference_id, performed_by, created_at)\n            VALUES (?, ?, ?, ?, 'ADJUSTMENT', 'LEGACY-OPENING-BALANCE', 'system:migration', ?)"
```
- **Bound Parameters:** `(f'MOV_LEGACY_{product_id}', product_id, batch_id, qty, now)`

### Operation #108: `app/services/db_init.py:451` in `migrate_passwords()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute("SELECT id, password FROM Users").fetchall()
```
- **Query / SQL Expression:**
```sql
'SELECT id, password FROM Users'
```

### Operation #109: `app/services/db_init.py:454` in `migrate_passwords()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("UPDATE Users SET password = ? WHERE id = ?", (generate_password_hash(pwd), row_id))
```
- **Query / SQL Expression:**
```sql
'UPDATE Users SET password = ? WHERE id = ?'
```
- **Bound Parameters:** `(generate_password_hash(pwd), row_id)`

### Operation #110: `app/services/db_init.py:456` in `migrate_passwords()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #111: `app/services/inventory_service.py:79` in `fetch_batch()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute(f"{_BATCH_SELECT} WHERE b.Batch_id = ?", (batch_id,)).fetchone()
```
- **Query / SQL Expression:**
```sql
f'{_BATCH_SELECT} WHERE b.Batch_id = ?'
```
- **Bound Parameters:** `(batch_id,)`

### Operation #112: `app/services/inventory_service.py:86` in `fetch_batch_by_no()`
- **Method Type:** `execute`
- **Code Statement:**
```python
return conn.execute(
```
- **Query / SQL Expression:**
```sql
f'{_BATCH_SELECT} WHERE b.Product_id = ? AND b.batch_no = ?'
```
- **Bound Parameters:** `(product_id, batch_no)`

### Operation #113: `app/services/inventory_service.py:93` in `fetch_supplier()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute(
```
- **Query / SQL Expression:**
```sql
'SELECT * FROM Suppliers WHERE Supplier_id = ? AND COALESCE(is_active, 1) = 1'
```
- **Bound Parameters:** `(supplier_id,)`

### Operation #114: `app/services/inventory_service.py:107` in `insert_batch()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
'INSERT INTO Product_Batches(Batch_id, Product_id, batch_no, mfg_date, expiry_date, quantity,\n               purchase_price, mrp, supplier_id, supplier_name, received_date, is_legacy_placeholder,\n               created_at, updated_at)\n           VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 0, ?, ?)'
```
- **Bound Parameters:** `(batch_id, product_id, data['batch_no'], data.get('mfg_date'), data['expiry_date'], data.get('purchase_price', 0.0), data.get('mrp', 0.0), data.get('supplier_id'), data.get('supplier_name', ''), data.get('received_date') or utc_today(), now, now)`

### Operation #115: `app/services/inventory_service.py:133` in `update_batch_fields()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(f"UPDATE Product_Batches SET {', '.join(sets)} WHERE Batch_id = ?", params + [batch_id])
```
- **Query / SQL Expression:**
```sql
f"UPDATE Product_Batches SET {', '.join(sets)} WHERE Batch_id = ?"
```
- **Bound Parameters:** `params + [batch_id]`

### Operation #116: `app/services/inventory_service.py:144` in `list_batches()`
- **Method Type:** `execute`
- **Code Statement:**
```python
total = conn.execute(f"SELECT COUNT(*) FROM Product_Batches b{where_sql}", params).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(*) FROM Product_Batches b{where_sql}'
```
- **Bound Parameters:** `params`

### Operation #117: `app/services/inventory_service.py:145` in `list_batches()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'{_BATCH_SELECT}{where_sql} ORDER BY {BATCH_SORT[sort]} {_dir(order)}, b.Batch_id ASC LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `params + [limit, offset]`

### Operation #118: `app/services/inventory_service.py:166` in `list_movements()`
- **Method Type:** `execute`
- **Code Statement:**
```python
total = conn.execute(f"SELECT COUNT(*) FROM Stock_Movements m{where_sql}", params).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(*) FROM Stock_Movements m{where_sql}'
```
- **Bound Parameters:** `params`

### Operation #119: `app/services/inventory_service.py:167` in `list_movements()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'SELECT m.*, p.name AS product_name, b.batch_no AS batch_no FROM Stock_Movements m LEFT JOIN Products p ON p.Product_id = m.Product_id LEFT JOIN Product_Batches b ON b.Batch_id = m.Batch_id{where_sql} ORDER BY {MOVEMENT_SORT[sort]} {_dir(order)}, m.rowid {_dir(order)} LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `params + [limit, offset]`

### Operation #120: `app/services/inventory_service.py:179` in `_batch_alert()`
- **Method Type:** `execute`
- **Code Statement:**
```python
total = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(*) FROM Product_Batches b LEFT JOIN Products p ON p.Product_id = b.Product_id{where_sql}'
```
- **Bound Parameters:** `params`

### Operation #121: `app/services/inventory_service.py:183` in `_batch_alert()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'{_BATCH_SELECT}{where_sql} ORDER BY {ALERT_BATCH_SORT[sort]} {_dir(order)}, b.Batch_id ASC LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `list(params) + [limit, offset]`

### Operation #122: `app/services/inventory_service.py:203` in `_product_alert()`
- **Method Type:** `execute`
- **Code Statement:**
```python
total = conn.execute(f"SELECT COUNT(*) FROM Products p{where_sql}").fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(*) FROM Products p{where_sql}'
```

### Operation #123: `app/services/inventory_service.py:204` in `_product_alert()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'SELECT p.* FROM Products p{where_sql} ORDER BY {ALERT_PRODUCT_SORT[sort]} {_dir(order)}, p.id ASC LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `(limit, offset)`

### Operation #124: `app/services/order_service.py:179` in `fetch_customer()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute(
```
- **Query / SQL Expression:**
```sql
'SELECT user_id, name, email, phone_number, address, pin_code, isApproved, block FROM Users WHERE user_id = ?'
```
- **Bound Parameters:** `(user_id,)`

### Operation #125: `app/services/order_service.py:215` in `fetch_order()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute(sql, params).fetchone()
```
- **Query / SQL Expression:**
```sql
sql
```
- **Bound Parameters:** `params`

### Operation #126: `app/services/order_service.py:225` in `insert_order()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
"INSERT INTO Order_Details(Order_id, user_id, product_id, isApproved, quantity, date_of_order_creation,\n               price, total_amount, product_name, user_name, message, category, sold, image_url,\n               prescription_url, doctor_name, patient_name, prescription_verified, status, cancel_reason, updated_at)\n           VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 0, 'pending', '', ?)"
```
- **Bound Parameters:** `(order_id, user_row['user_id'], product_row['Product_id'], quantity, now, price, money(price * quantity), product_row['name'], user_row['name'], data.get('message', ''), product_row['category'], product_row['image_url'], data.get('prescription_url', ''), data.get('doctor_name', ''), data.get('patient_name', ''), now)`

### Operation #127: `app/services/order_service.py:250` in `set_order_fields()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(f"UPDATE Order_Details SET {', '.join(sets)} WHERE Order_id = ?", params + [order_id])
```
- **Query / SQL Expression:**
```sql
f"UPDATE Order_Details SET {', '.join(sets)} WHERE Order_id = ?"
```
- **Bound Parameters:** `params + [order_id]`

### Operation #128: `app/services/order_service.py:269` in `list_orders()`
- **Method Type:** `execute`
- **Code Statement:**
```python
total = conn.execute(f"SELECT COUNT(*) FROM Order_Details o{where_sql}", params).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(*) FROM Order_Details o{where_sql}'
```
- **Bound Parameters:** `params`

### Operation #129: `app/services/order_service.py:271` in `list_orders()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'{_ORDER_SELECT}{where_sql} ORDER BY {ORDER_SORT[sort]} {direction}, o.id {direction} LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `params + [limit, offset]`

### Operation #130: `app/services/order_service.py:280` in `sales_for_order()`
- **Method Type:** `execute`
- **Code Statement:**
```python
return conn.execute(f"{_SALE_SELECT} WHERE s.Order_id = ? ORDER BY s.id ASC", (order_id,)).fetchall()
```
- **Query / SQL Expression:**
```sql
f'{_SALE_SELECT} WHERE s.Order_id = ? ORDER BY s.id ASC'
```
- **Bound Parameters:** `(order_id,)`

### Operation #131: `app/services/order_service.py:300` in `list_sales()`
- **Method Type:** `execute`
- **Code Statement:**
```python
total = conn.execute(f"SELECT COUNT(*) FROM Sell_History s{where_sql}", params).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(*) FROM Sell_History s{where_sql}'
```
- **Bound Parameters:** `params`

### Operation #132: `app/services/order_service.py:302` in `list_sales()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'{_SALE_SELECT}{where_sql} ORDER BY {SALE_SORT[sort]} {direction}, s.id {direction} LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `params + [limit, offset]`

### Operation #133: `app/services/order_service.py:316` in `sell_order()`
- **Method Type:** `execute`
- **Code Statement:**
```python
if order_status(order_row) == "sold" or conn.execute(
```
- **Query / SQL Expression:**
```sql
'SELECT 1 FROM Sell_History WHERE Order_id = ? LIMIT 1'
```
- **Bound Parameters:** `(order_id,)`

### Operation #134: `app/services/order_service.py:325` in `sell_order()`
- **Method Type:** `execute`
- **Code Statement:**
```python
remaining = conn.execute("SELECT stock FROM Products WHERE Product_id = ?",
```
- **Query / SQL Expression:**
```sql
'SELECT stock FROM Products WHERE Product_id = ?'
```
- **Bound Parameters:** `(order_row['product_id'],)`

### Operation #135: `app/services/order_service.py:331` in `sell_order()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
'INSERT INTO Sell_History(Sell_id, product_id, Order_id, isApproved, quantity, Remaining_stock,\n                   date_of_sell, total_amount, price, product_name, user_id, user_name, image_url,\n                   batch_id, batch_no, gst_percent, sold_by)\n               VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
```
- **Bound Parameters:** `('SELL_' + uuid.uuid4().hex[:12], order_row['product_id'], order_id, alloc['qty'], remaining, now, money(price * alloc['qty']), price, order_row['product_name'], order_row['user_id'], order_row['user_name'], order_row['image_url'] or order_row['p_image_url'], alloc['batch_id'], alloc['batch_no'], gst, sold_by)`

### Operation #136: `app/services/order_service.py:347` in `restock_deducted()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
"SELECT Batch_id, SUM(change_qty) AS net FROM Stock_Movements\n           WHERE reference_id = ? AND reason IN ('SALE', 'RETURN', 'CANCEL_RESTOCK') AND Batch_id IS NOT NULL\n           GROUP BY Batch_id HAVING SUM(change_qty) < 0"
```
- **Bound Parameters:** `(order_id,)`

### Operation #137: `app/services/order_service.py:388` in `build_invoice()`
- **Method Type:** `execute`
- **Code Statement:**
```python
sales = conn.execute(
```
- **Query / SQL Expression:**
```sql
'SELECT s.*, b.expiry_date AS expiry_date FROM Sell_History s\n           LEFT JOIN Product_Batches b ON b.Batch_id = s.batch_id\n           WHERE s.Order_id = ? ORDER BY s.id ASC'
```
- **Bound Parameters:** `(order_row['Order_id'],)`

### Operation #138: `app/services/order_service.py:420` in `build_invoice()`
- **Method Type:** `execute`
- **Code Statement:**
```python
user = conn.execute(
```
- **Query / SQL Expression:**
```sql
'SELECT user_id, name, email, phone_number, address, pin_code FROM Users WHERE user_id = ?'
```
- **Bound Parameters:** `(order_row['user_id'],)`

### Operation #139: `app/services/product_service.py:161` in `ensure_barcode_unique()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute(
```
- **Query / SQL Expression:**
```sql
'SELECT Product_id FROM Products WHERE barcode = ? AND Product_id IS NOT ?'
```
- **Bound Parameters:** `(barcode, exclude_product_id)`

### Operation #140: `app/services/product_service.py:175` in `fetch_product()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute(sql, params).fetchone()
```
- **Query / SQL Expression:**
```sql
sql
```
- **Bound Parameters:** `params`

### Operation #141: `app/services/product_service.py:187` in `fetch_product_by_barcode()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute(sql, (utc_today(), barcode)).fetchone()
```
- **Query / SQL Expression:**
```sql
sql
```
- **Bound Parameters:** `(utc_today(), barcode)`

### Operation #142: `app/services/product_service.py:225` in `list_products()`
- **Method Type:** `execute`
- **Code Statement:**
```python
total = conn.execute(f"SELECT COUNT(*) FROM Products p{where_sql}", params).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(*) FROM Products p{where_sql}'
```
- **Bound Parameters:** `params`

### Operation #143: `app/services/product_service.py:227` in `list_products()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'SELECT p.*, {SELLABLE_SQL} AS sellable_stock FROM Products p{where_sql} ORDER BY {order_sql} LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `[today] + params + [limit, offset]`

### Operation #144: `app/services/product_service.py:243` in `insert_product()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
f"INSERT INTO Products({', '.join(columns)}) VALUES ({', '.join(('?' for _ in columns))})"
```
- **Bound Parameters:** `[values[c] for c in columns]`

### Operation #145: `app/services/product_service.py:262` in `update_product_fields()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(f"UPDATE Products SET {', '.join(sets)} WHERE Product_id = ?", params + [product_id])
```
- **Query / SQL Expression:**
```sql
f"UPDATE Products SET {', '.join(sets)} WHERE Product_id = ?"
```
- **Bound Parameters:** `params + [product_id]`

### Operation #146: `app/services/product_service.py:266` in `set_product_active()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
'UPDATE Products SET is_active = ?, updated_at = ? WHERE Product_id = ?'
```
- **Bound Parameters:** `(1 if active else 0, utc_now_iso(), product_id)`

### Operation #147: `app/services/product_service.py:275` in `list_categories()`
- **Method Type:** `execute`
- **Code Statement:**
```python
total = conn.execute(f"SELECT COUNT(DISTINCT {name_sql}) FROM Products{where}").fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(DISTINCT {name_sql}) FROM Products{where}'
```

### Operation #148: `app/services/product_service.py:277` in `list_categories()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f"SELECT {name_sql} AS name, COUNT(*) AS product_count FROM Products{where} GROUP BY {name_sql} ORDER BY {sort_sql} {('DESC' if order == 'desc' else 'ASC')}, name ASC LIMIT ? OFFSET ?"
```
- **Bound Parameters:** `(limit, offset)`

### Operation #149: `app/services/report_service.py:18` in `_scalar()`
- **Method Type:** `execute`
- **Code Statement:**
```python
value = conn.execute(sql, params).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
sql
```
- **Bound Parameters:** `params`

### Operation #150: `app/services/report_service.py:55` in `sales_report()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'SELECT {select}, SUM(s.quantity) AS quantity, ROUND(SUM(s.total_amount), 2) AS revenue, COUNT(DISTINCT s.Order_id) AS orders {where} GROUP BY {key} ORDER BY {GROUP_SORT[group_by][sort]} {direction} LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `params + [limit, offset]`

### Operation #151: `app/services/report_service.py:61` in `sales_report()`
- **Method Type:** `execute`
- **Code Statement:**
```python
summary_row = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'SELECT COALESCE(SUM(s.quantity), 0), COALESCE(ROUND(SUM(s.total_amount), 2), 0), COUNT(DISTINCT s.Order_id) {where}'
```
- **Bound Parameters:** `params`

### Operation #152: `app/services/report_service.py:81` in `top_products()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'SELECT s.product_id AS product_id, MAX(s.product_name) AS product_name, SUM(s.quantity) AS quantity, ROUND(SUM(s.total_amount), 2) AS revenue {where} GROUP BY s.product_id ORDER BY {TOP_SORT[sort]} {direction}, product_id ASC LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `params + [limit, offset]`

### Operation #153: `app/services/report_service.py:124` in `list_audit_logs()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'SELECT * FROM Audit_Log{where_sql} ORDER BY {AUDIT_SORT[sort]} {direction}, rowid {direction} LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `params + [limit, offset]`

### Operation #154: `app/services/stock_service.py:34` in `_savepoint()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(f"SAVEPOINT {name}")
```
- **Query / SQL Expression:**
```sql
f'SAVEPOINT {name}'
```

### Operation #155: `app/services/stock_service.py:38` in `_savepoint()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(f"ROLLBACK TO SAVEPOINT {name}")
```
- **Query / SQL Expression:**
```sql
f'ROLLBACK TO SAVEPOINT {name}'
```

### Operation #156: `app/services/stock_service.py:39` in `_savepoint()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(f"RELEASE SAVEPOINT {name}")
```
- **Query / SQL Expression:**
```sql
f'RELEASE SAVEPOINT {name}'
```

### Operation #157: `app/services/stock_service.py:42` in `_savepoint()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(f"RELEASE SAVEPOINT {name}")
```
- **Query / SQL Expression:**
```sql
f'RELEASE SAVEPOINT {name}'
```

### Operation #158: `app/services/stock_service.py:55` in `_insert_movement()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
'INSERT INTO Stock_Movements(Movement_id, Product_id, Batch_id, change_qty, reason,\n               reference_id, performed_by, created_at)\n           VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
```
- **Bound Parameters:** `(movement_id, product_id, batch_id, change_qty, reason, reference_id or '', performed_by or '', created_at)`

### Operation #159: `app/services/stock_service.py:78` in `_change_batch()`
- **Method Type:** `execute`
- **Code Statement:**
```python
cur = conn.execute(
```
- **Query / SQL Expression:**
```sql
'UPDATE Product_Batches SET quantity = quantity - ?, updated_at = ?\n               WHERE Batch_id = ? AND Product_id = ? AND quantity >= ?'
```
- **Bound Parameters:** `(-change_qty, now, batch_id, product_id, -change_qty)`

### Operation #160: `app/services/stock_service.py:84` in `_change_batch()`
- **Method Type:** `execute`
- **Code Statement:**
```python
cur = conn.execute(
```
- **Query / SQL Expression:**
```sql
'UPDATE Product_Batches SET quantity = quantity + ?, updated_at = ?\n               WHERE Batch_id = ? AND Product_id = ?'
```
- **Bound Parameters:** `(change_qty, now, batch_id, product_id)`

### Operation #161: `app/services/stock_service.py:91` in `_change_batch()`
- **Method Type:** `execute`
- **Code Statement:**
```python
exists = conn.execute(
```
- **Query / SQL Expression:**
```sql
'SELECT 1 FROM Product_Batches WHERE Batch_id = ? AND Product_id = ?'
```
- **Bound Parameters:** `(batch_id, product_id)`

### Operation #162: `app/services/stock_service.py:101` in `recompute_stock()`
- **Method Type:** `execute`
- **Code Statement:**
```python
total = conn.execute(
```
- **Query / SQL Expression:**
```sql
'SELECT COALESCE(SUM(quantity), 0) FROM Product_Batches WHERE Product_id = ?'
```
- **Bound Parameters:** `(product_id,)`

### Operation #163: `app/services/stock_service.py:104` in `recompute_stock()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
'UPDATE Products SET stock = ?, updated_at = ? WHERE Product_id = ?'
```
- **Bound Parameters:** `(int(total), utc_now_iso(), product_id)`

### Operation #164: `app/services/stock_service.py:131` in `deduct_fefo()`
- **Method Type:** `execute`
- **Code Statement:**
```python
batches = conn.execute(
```
- **Query / SQL Expression:**
```sql
"SELECT Batch_id, batch_no, quantity FROM Product_Batches\n           WHERE Product_id = ? AND quantity > 0 AND expiry_date >= ?\n           ORDER BY expiry_date ASC, COALESCE(received_date, '') ASC, Batch_id ASC"
```
- **Bound Parameters:** `(product_id, today)`

### Operation #165: `app/services/stock_service.py:148` in `deduct_fefo()`
- **Method Type:** `execute`
- **Code Statement:**
```python
cur = conn.execute(
```
- **Query / SQL Expression:**
```sql
'UPDATE Product_Batches SET quantity = quantity - ?, updated_at = ?\n                   WHERE Batch_id = ? AND quantity >= ?'
```
- **Bound Parameters:** `(take, utc_now_iso(), batch['Batch_id'], take)`

### Operation #166: `app/services/stock_service.py:168` in `restock_to_batch()`
- **Method Type:** `execute`
- **Code Statement:**
```python
batch = conn.execute(
```
- **Query / SQL Expression:**
```sql
'SELECT Product_id, expiry_date FROM Product_Batches WHERE Batch_id = ?'
```
- **Bound Parameters:** `(batch_id,)`

### Operation #167: `app/services/supplier_service.py:52` in `fetch()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute("SELECT * FROM Suppliers WHERE Supplier_id = ?", (supplier_id,)).fetchone()
```
- **Query / SQL Expression:**
```sql
'SELECT * FROM Suppliers WHERE Supplier_id = ?'
```
- **Bound Parameters:** `(supplier_id,)`

### Operation #168: `app/services/supplier_service.py:61` in `ensure_gst_unique()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute("SELECT 1 FROM Suppliers WHERE gst_number = ? AND Supplier_id IS NOT ?",
```
- **Query / SQL Expression:**
```sql
'SELECT 1 FROM Suppliers WHERE gst_number = ? AND Supplier_id IS NOT ?'
```
- **Bound Parameters:** `(gst_number, exclude_id)`

### Operation #169: `app/services/supplier_service.py:70` in `insert()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
'INSERT INTO Suppliers(Supplier_id, name, contact_phone, email, gst_number, address, is_active,\n               created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)'
```
- **Bound Parameters:** `(supplier_id, cleaned['name'], cleaned.get('contact_phone', ''), cleaned.get('email', ''), cleaned.get('gst_number', ''), cleaned.get('address', ''), now, now)`

### Operation #170: `app/services/supplier_service.py:87` in `update()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(f"UPDATE Suppliers SET {', '.join(sets)} WHERE Supplier_id = ?", params + [supplier_id])
```
- **Query / SQL Expression:**
```sql
f"UPDATE Suppliers SET {', '.join(sets)} WHERE Supplier_id = ?"
```
- **Bound Parameters:** `params + [supplier_id]`

### Operation #171: `app/services/supplier_service.py:91` in `set_active()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("UPDATE Suppliers SET is_active = ?, updated_at = ? WHERE Supplier_id = ?",
```
- **Query / SQL Expression:**
```sql
'UPDATE Suppliers SET is_active = ?, updated_at = ? WHERE Supplier_id = ?'
```
- **Bound Parameters:** `(1 if active else 0, utc_now_iso(), supplier_id)`

### Operation #172: `app/services/supplier_service.py:106` in `list_suppliers()`
- **Method Type:** `execute`
- **Code Statement:**
```python
total = conn.execute(f"SELECT COUNT(*) FROM Suppliers{where_sql}", params).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(*) FROM Suppliers{where_sql}'
```
- **Bound Parameters:** `params`

### Operation #173: `app/services/supplier_service.py:108` in `list_suppliers()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute(
```
- **Query / SQL Expression:**
```sql
f'SELECT * FROM Suppliers{where_sql} ORDER BY {SORT_COLUMNS[sort]} {direction}, rowid {direction} LIMIT ? OFFSET ?'
```
- **Bound Parameters:** `params + [limit, offset]`

### Operation #174: `app/utils/idempotency.py:38` in `_reserve()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("BEGIN IMMEDIATE")
```
- **Query / SQL Expression:**
```sql
'BEGIN IMMEDIATE'
```

### Operation #175: `app/utils/idempotency.py:39` in `_reserve()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("DELETE FROM Idempotency_Keys WHERE created_at < ?", (utc_iso_before(ttl_hours),))
```
- **Query / SQL Expression:**
```sql
'DELETE FROM Idempotency_Keys WHERE created_at < ?'
```
- **Bound Parameters:** `(utc_iso_before(ttl_hours),)`

### Operation #176: `app/utils/idempotency.py:40` in `_reserve()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute(
```
- **Query / SQL Expression:**
```sql
'SELECT response_json, status_code, location FROM Idempotency_Keys\n               WHERE key = ? AND user_id = ? AND endpoint = ?'
```
- **Bound Parameters:** `(key, user_id, endpoint)`

### Operation #177: `app/utils/idempotency.py:46` in `_reserve()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
"INSERT INTO Idempotency_Keys(key, user_id, endpoint, response_json, status_code, location, created_at)\n                   VALUES (?, ?, ?, NULL, 0, '', ?)"
```
- **Bound Parameters:** `(key, user_id, endpoint, utc_now_iso())`

### Operation #178: `app/utils/idempotency.py:51` in `_reserve()`
- **Method Type:** `commit`
- **Code Statement:**
```python
conn.commit()
```

### Operation #179: `app/utils/idempotency.py:54` in `_reserve()`
- **Method Type:** `rollback`
- **Code Statement:**
```python
conn.rollback()
```

### Operation #180: `app/utils/idempotency.py:57` in `_reserve()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #181: `app/utils/idempotency.py:64` in `_store()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
'UPDATE Idempotency_Keys SET response_json = ?, status_code = ?, location = ?\n                   WHERE key = ? AND user_id = ? AND endpoint = ?'
```
- **Bound Parameters:** `(response.get_data(as_text=True), response.status_code, response.headers.get('Location', ''), key, user_id, endpoint)`

### Operation #182: `app/utils/idempotency.py:71` in `_store()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Operation #183: `app/utils/idempotency.py:78` in `_release()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
'DELETE FROM Idempotency_Keys WHERE key = ? AND user_id = ? AND endpoint = ? AND status_code = 0'
```
- **Bound Parameters:** `(key, user_id, endpoint)`

### Operation #184: `app/utils/idempotency.py:83` in `_release()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

---

## 5. Complete Test Suite SQLite Operations Inventory (Logics #182 to #239)

This section documents every SQLite call executed in test suites (`tests/`), fixtures, seeders, and migration verification.

### Test Operation #185: `tests/test_admin_signup.py:32` in `_audit_actions()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = conn.execute("SELECT action, details FROM Audit_Log WHERE entity_id = ?", (admin_id,)).fetchall()
```
- **Query / SQL Expression:**
```sql
'SELECT action, details FROM Audit_Log WHERE entity_id = ?'
```
- **Bound Parameters:** `(admin_id,)`

### Test Operation #186: `tests/test_admin_signup.py:159` in `test_concurrent_first_signups_exactly_one_owner()`
- **Method Type:** `connect`
- **Code Statement:**
```python
conn = sqlite3.connect(app.config["DATABASE_NAME"])
```
- **Query / SQL Expression:**
```sql
app.config['DATABASE_NAME']
```

### Test Operation #187: `tests/test_admin_signup.py:161` in `test_concurrent_first_signups_exactly_one_owner()`
- **Method Type:** `execute`
- **Code Statement:**
```python
assert conn.execute("SELECT COUNT(*) FROM Admin WHERE is_owner = 1").fetchone()[0] == 1
```
- **Query / SQL Expression:**
```sql
'SELECT COUNT(*) FROM Admin WHERE is_owner = 1'
```

### Test Operation #188: `tests/test_admin_signup.py:162` in `test_concurrent_first_signups_exactly_one_owner()`
- **Method Type:** `execute`
- **Code Statement:**
```python
assert conn.execute("SELECT COUNT(*) FROM Admin WHERE is_approved = 1").fetchone()[0] == 1
```
- **Query / SQL Expression:**
```sql
'SELECT COUNT(*) FROM Admin WHERE is_approved = 1'
```

### Test Operation #189: `tests/test_admin_signup.py:164` in `test_concurrent_first_signups_exactly_one_owner()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Test Operation #190: `tests/test_admin_signup.py:203` in `test_migration_keeps_existing_admins_approved()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("INSERT INTO Admin(admin_id, password, name, email, role) VALUES "
```
- **Query / SQL Expression:**
```sql
"INSERT INTO Admin(admin_id, password, name, email, role) VALUES ('AID_legacy', 'x', 'Legacy', 'legacy@example.com', 'admin')"
```

### Test Operation #191: `tests/test_admin_signup.py:207` in `test_migration_keeps_existing_admins_approved()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute("SELECT is_approved, is_owner FROM Admin WHERE admin_id = 'AID_legacy'").fetchone()
```
- **Query / SQL Expression:**
```sql
"SELECT is_approved, is_owner FROM Admin WHERE admin_id = 'AID_legacy'"
```

### Test Operation #192: `tests/test_admin_signup.py:220` in `test_cli_approve_admin()`
- **Method Type:** `execute`
- **Code Statement:**
```python
for r in conn.execute("SELECT email, is_approved, is_owner FROM Admin")}
```
- **Query / SQL Expression:**
```sql
'SELECT email, is_approved, is_owner FROM Admin'
```

### Test Operation #193: `tests/test_helpers.py:59` in `test_write_audit_strips_secrets()`
- **Method Type:** `execute`
- **Code Statement:**
```python
row = conn.execute("SELECT * FROM Audit_Log WHERE Audit_id = ?", (audit_id,)).fetchone()
```
- **Query / SQL Expression:**
```sql
'SELECT * FROM Audit_Log WHERE Audit_id = ?'
```
- **Bound Parameters:** `(audit_id,)`

### Test Operation #194: `tests/test_inventory_api.py:29` in `_audit_actions()`
- **Method Type:** `execute`
- **Code Statement:**
```python
rows = [r["action"] for r in conn.execute("SELECT action FROM Audit_Log WHERE entity_id = ?", (entity_id,))]
```
- **Query / SQL Expression:**
```sql
'SELECT action FROM Audit_Log WHERE entity_id = ?'
```
- **Bound Parameters:** `(entity_id,)`

### Test Operation #195: `tests/test_inventory_api.py:30` in `_audit_actions()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Test Operation #196: `tests/test_migration.py:28` in `_legacy_db()`
- **Method Type:** `connect`
- **Code Statement:**
```python
conn = sqlite3.connect(path)
```
- **Query / SQL Expression:**
```sql
path
```

### Test Operation #197: `tests/test_migration.py:30` in `_legacy_db()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(ddl)
```
- **Query / SQL Expression:**
```sql
ddl
```

### Test Operation #198: `tests/test_migration.py:31` in `_legacy_db()`
- **Method Type:** `executemany`
- **Code Statement:**
```python
conn.executemany(
```
- **Query / SQL Expression:**
```sql
'INSERT INTO Products(Product_id, name, price, category, stock) VALUES (?,?,?,?,?)'
```
- **Bound Parameters:** `[('PROD_A', 'Aspirin', 10.0, 'Pain', 25), ('PROD_B', 'Bandage', 5.0, 'Care', 0)]`

### Test Operation #199: `tests/test_migration.py:35` in `_legacy_db()`
- **Method Type:** `executemany`
- **Code Statement:**
```python
conn.executemany(
```
- **Query / SQL Expression:**
```sql
'INSERT INTO Order_Details(Order_id, user_id, product_id, isApproved, quantity, price, total_amount, sold)\n           VALUES (?,?,?,?,?,?,?,?)'
```
- **Bound Parameters:** `[('ORD1', 'U1', 'PROD_A', 0, 1, 10, 10, 0), ('ORD2', 'U1', 'PROD_A', 1, 2, 10, 20, 0), ('ORD3', 'U1', 'PROD_A', 1, 3, 10, 30, 0)]`

### Test Operation #200: `tests/test_migration.py:42` in `_legacy_db()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("INSERT INTO Sell_History(Sell_id, product_id, Order_id, quantity) VALUES ('S1','PROD_A','ORD3',3)")
```
- **Query / SQL Expression:**
```sql
"INSERT INTO Sell_History(Sell_id, product_id, Order_id, quantity) VALUES ('S1','PROD_A','ORD3',3)"
```

### Test Operation #201: `tests/test_migration.py:43` in `_legacy_db()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("INSERT INTO Users(user_id, name, password) VALUES ('U1', 'Old User', 'scrypt:x')")
```
- **Query / SQL Expression:**
```sql
"INSERT INTO Users(user_id, name, password) VALUES ('U1', 'Old User', 'scrypt:x')"
```

### Test Operation #202: `tests/test_migration.py:44` in `_legacy_db()`
- **Method Type:** `commit`
- **Code Statement:**
```python
conn.commit()
```

### Test Operation #203: `tests/test_migration.py:45` in `_legacy_db()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Test Operation #204: `tests/test_migration.py:49` in `_counts()`
- **Method Type:** `execute`
- **Code Statement:**
```python
return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT COUNT(*) FROM {t}'
```

### Test Operation #205: `tests/test_migration.py:61` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `connect`
- **Code Statement:**
```python
conn = sqlite3.connect(db)
```
- **Query / SQL Expression:**
```sql
db
```

### Test Operation #206: `tests/test_migration.py:67` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `execute`
- **Code Statement:**
```python
a = conn.execute("SELECT * FROM Products WHERE Product_id='PROD_A'").fetchone()
```
- **Query / SQL Expression:**
```sql
"SELECT * FROM Products WHERE Product_id='PROD_A'"
```

### Test Operation #207: `tests/test_migration.py:73` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `execute`
- **Code Statement:**
```python
batches = conn.execute("SELECT * FROM Product_Batches").fetchall()
```
- **Query / SQL Expression:**
```sql
'SELECT * FROM Product_Batches'
```

### Test Operation #208: `tests/test_migration.py:78` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `execute`
- **Code Statement:**
```python
mv = conn.execute("SELECT * FROM Stock_Movements").fetchall()
```
- **Query / SQL Expression:**
```sql
'SELECT * FROM Stock_Movements'
```

### Test Operation #209: `tests/test_migration.py:82` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `execute`
- **Code Statement:**
```python
status = dict(conn.execute("SELECT Order_id, status FROM Order_Details").fetchall())
```
- **Query / SQL Expression:**
```sql
'SELECT Order_id, status FROM Order_Details'
```

### Test Operation #210: `tests/test_migration.py:85` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `execute`
- **Code Statement:**
```python
tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
```
- **Query / SQL Expression:**
```sql
"SELECT name FROM sqlite_master WHERE type='table'"
```

### Test Operation #211: `tests/test_migration.py:87` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Test Operation #212: `tests/test_migration.py:94` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `connect`
- **Code Statement:**
```python
conn = sqlite3.connect(db)
```
- **Query / SQL Expression:**
```sql
db
```

### Test Operation #213: `tests/test_migration.py:96` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Test Operation #214: `tests/test_migration.py:99` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `connect`
- **Code Statement:**
```python
bconn = sqlite3.connect(result["backup"])
```
- **Query / SQL Expression:**
```sql
result['backup']
```

### Test Operation #215: `tests/test_migration.py:100` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `execute`
- **Code Statement:**
```python
cols = [r[1] for r in bconn.execute("PRAGMA table_info(Products)")]
```
- **Query / SQL Expression:**
```sql
'PRAGMA table_info(Products)'
```

### Test Operation #216: `tests/test_migration.py:102` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `execute`
- **Code Statement:**
```python
assert bconn.execute("SELECT COUNT(*) FROM Products").fetchone()[0] == 2
```
- **Query / SQL Expression:**
```sql
'SELECT COUNT(*) FROM Products'
```

### Test Operation #217: `tests/test_migration.py:103` in `test_migration_preserves_rows_backfills_and_is_idempotent()`
- **Method Type:** `close`
- **Code Statement:**
```python
bconn.close()
```

### Test Operation #218: `tests/test_migration.py:110` in `test_migration_on_fresh_db()`
- **Method Type:** `connect`
- **Code Statement:**
```python
conn = sqlite3.connect(db)
```
- **Query / SQL Expression:**
```sql
db
```

### Test Operation #219: `tests/test_migration.py:111` in `test_migration_on_fresh_db()`
- **Method Type:** `execute`
- **Code Statement:**
```python
cols = {r[1] for r in conn.execute("PRAGMA table_info(Order_Details)")}
```
- **Query / SQL Expression:**
```sql
'PRAGMA table_info(Order_Details)'
```

### Test Operation #220: `tests/test_migration.py:113` in `test_migration_on_fresh_db()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Test Operation #221: `tests/test_order_image_url.py:10` in `test_order_and_sale_image_url()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("INSERT INTO Users (user_id, name, email, role, isApproved, block) "
```
- **Query / SQL Expression:**
```sql
"INSERT INTO Users (user_id, name, email, role, isApproved, block) VALUES ('U1', 'Test User', 'u1@test.com', 'user', 1, 0)"
```

### Test Operation #222: `tests/test_order_image_url.py:23` in `test_order_and_sale_image_url()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute("UPDATE Products SET image_url = ? WHERE Product_id = ?", (image, pids[0]))
```
- **Query / SQL Expression:**
```sql
'UPDATE Products SET image_url = ? WHERE Product_id = ?'
```
- **Bound Parameters:** `(image, pids[0])`

### Test Operation #223: `tests/test_orders_api.py:17` in `_insert_user()`
- **Method Type:** `execute`
- **Code Statement:**
```python
conn.execute(
```
- **Query / SQL Expression:**
```sql
"INSERT INTO Users(user_id, password, isApproved, block, name, email, phone_number, address, pin_code, role)\n                   VALUES (?, 'x', ?, ?, ?, ?, '9999999999', 'Street 1', '400001', 'user')"
```
- **Bound Parameters:** `(user_id, approved, block, name or f'User {user_id}', f'{user_id.lower()}@example.com')`

### Test Operation #224: `tests/test_orders_api.py:77` in `_sales_rows()`
- **Method Type:** `execute`
- **Code Statement:**
```python
n = conn.execute("SELECT COUNT(*) FROM Sell_History WHERE Order_id = ?", (order_id,)).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
'SELECT COUNT(*) FROM Sell_History WHERE Order_id = ?'
```
- **Bound Parameters:** `(order_id,)`

### Test Operation #225: `tests/test_orders_api.py:78` in `_sales_rows()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Test Operation #226: `tests/test_orders_api.py:216` in `test_full_lifecycle_fefo_invoice_and_return()`
- **Method Type:** `execute`
- **Code Statement:**
```python
reasons = [r[0] for r in conn.execute(
```
- **Query / SQL Expression:**
```sql
'SELECT reason FROM Stock_Movements WHERE reference_id = ? ORDER BY rowid'
```
- **Bound Parameters:** `(oid,)`

### Test Operation #227: `tests/test_orders_api.py:218` in `test_full_lifecycle_fefo_invoice_and_return()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Test Operation #228: `tests/test_part3_api.py:51` in `_db_role()`
- **Method Type:** `connect`
- **Code Statement:**
```python
conn = sqlite3.connect(os.getenv("DATABASE_NAME", "test_medical_shop.db"))
```
- **Query / SQL Expression:**
```sql
os.getenv('DATABASE_NAME', 'test_medical_shop.db')
```

### Test Operation #229: `tests/test_part3_api.py:53` in `_db_role()`
- **Method Type:** `execute`
- **Code Statement:**
```python
return conn.execute(f"SELECT role FROM {table} WHERE {id_col} = ?", (value,)).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
f'SELECT role FROM {table} WHERE {id_col} = ?'
```
- **Bound Parameters:** `(value,)`

### Test Operation #230: `tests/test_part3_api.py:55` in `_db_role()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Test Operation #231: `tests/test_security_passwords.py:7` in `_stored_password()`
- **Method Type:** `connect`
- **Code Statement:**
```python
conn = sqlite3.connect(os.getenv("DATABASE_NAME", "test_medical_shop.db"))
```
- **Query / SQL Expression:**
```sql
os.getenv('DATABASE_NAME', 'test_medical_shop.db')
```

### Test Operation #232: `tests/test_security_passwords.py:9` in `_stored_password()`
- **Method Type:** `execute`
- **Code Statement:**
```python
return conn.execute("SELECT password FROM Users WHERE user_id = ?", (user_id,)).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
'SELECT password FROM Users WHERE user_id = ?'
```
- **Bound Parameters:** `(user_id,)`

### Test Operation #233: `tests/test_security_passwords.py:11` in `_stored_password()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Test Operation #234: `tests/test_stock_service.py:27` in `_state()`
- **Method Type:** `execute`
- **Code Statement:**
```python
batches = {r["batch_no"]: r["quantity"] for r in conn.execute(
```
- **Query / SQL Expression:**
```sql
'SELECT batch_no, quantity FROM Product_Batches WHERE Product_id = ?'
```
- **Bound Parameters:** `(pid,)`

### Test Operation #235: `tests/test_stock_service.py:29` in `_state()`
- **Method Type:** `execute`
- **Code Statement:**
```python
stock = conn.execute("SELECT stock FROM Products WHERE Product_id = ?", (pid,)).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
'SELECT stock FROM Products WHERE Product_id = ?'
```
- **Bound Parameters:** `(pid,)`

### Test Operation #236: `tests/test_stock_service.py:30` in `_state()`
- **Method Type:** `execute`
- **Code Statement:**
```python
moves = conn.execute("SELECT COUNT(*) FROM Stock_Movements WHERE Product_id = ?", (pid,)).fetchone()[0]
```
- **Query / SQL Expression:**
```sql
'SELECT COUNT(*) FROM Stock_Movements WHERE Product_id = ?'
```
- **Bound Parameters:** `(pid,)`

### Test Operation #237: `tests/test_stock_service.py:32` in `_state()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

### Test Operation #238: `tests/test_stock_service.py:57` in `test_fefo_splits_across_batches_and_skips_expired()`
- **Method Type:** `execute`
- **Code Statement:**
```python
sale = conn.execute("SELECT SUM(change_qty) FROM Stock_Movements WHERE reason='SALE' AND reference_id='ORD_X'").fetchone()[0]
```
- **Query / SQL Expression:**
```sql
"SELECT SUM(change_qty) FROM Stock_Movements WHERE reason='SALE' AND reference_id='ORD_X'"
```

### Test Operation #239: `tests/test_stock_service.py:58` in `test_fefo_splits_across_batches_and_skips_expired()`
- **Method Type:** `close`
- **Code Statement:**
```python
conn.close()
```

---

## 6. PostgreSQL & MySQL Migration Translation Matrix

Use this matrix when converting the SQLite schema to PostgreSQL or MySQL.

| SQLite Pattern in Repo | PostgreSQL Target | MySQL 8+ Target | Notes / Gotchas |
| :--- | :--- | :--- | :--- |
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `BIGSERIAL PRIMARY KEY` or `BIGINT GENERATED ALWAYS AS IDENTITY` | `BIGINT AUTO_INCREMENT PRIMARY KEY` | Standard primary key mapping. |
| `name COLLATE NOCASE` | `name CITEXT` or `COLLATE "und-x-icu"` | `name VARCHAR(255) COLLATE utf8mb4_unicode_ci` | SQLite relies heavily on `COLLATE NOCASE` for case-insensitive sorting and unique checks. |
| `CREATE UNIQUE INDEX ... WHERE is_owner = 1` | `CREATE UNIQUE INDEX ... WHERE is_owner = 1` | Not natively supported without functional index or triggers (e.g. `CREATE UNIQUE INDEX ... ON ((CASE WHEN is_owner = 1 THEN 1 ELSE NULL END))`) | Partial index guarantees exactly one owner admin across the entire system. |
| `substr(s.date_of_sell, 1, 10)` | `s.date_of_sell::DATE` or `SUBSTRING(s.date_of_sell FROM 1 FOR 10)` | `DATE(s.date_of_sell)` or `SUBSTRING(s.date_of_sell, 1, 10)` | Used throughout `report_service.py` to group sales and filter date intervals. |
| `COALESCE(col, 'default')` | `COALESCE(col, 'default')` | `COALESCE(col, 'default')` | Fully compatible. |
| `PRAGMA foreign_keys = ON` | Native by default | Native in InnoDB | Must ensure foreign keys are defined with matching column data types. |
| `BEGIN IMMEDIATE` | `BEGIN;` followed by `SELECT ... FOR UPDATE` | `BEGIN;` followed by `SELECT ... FOR UPDATE` | PostgreSQL and MySQL achieve write-intent serialisation via row-level locks rather than database-level reserved locks. |
| `CHECK(reason IN (...))` | `VARCHAR(30) CHECK (reason IN (...))` or `CREATE TYPE stock_movement_reason AS ENUM (...)` | `ENUM('PURCHASE', 'SALE', ...)` | Enforces strict inventory audit categories. |
| `details TEXT DEFAULT '{}'` | `JSONB DEFAULT '{}'::jsonb` | `JSON` | Stores audit details and idempotency response payloads. |
