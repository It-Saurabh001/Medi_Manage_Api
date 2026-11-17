"""Idempotent, additive-only schema migration (R1).

Only `CREATE TABLE/INDEX IF NOT EXISTS` and `ALTER TABLE ADD COLUMN` are used. Nothing is
ever dropped, rebuilt or deleted. An existing DB file is copied to `<db>.bak-<timestamp>`
(SQLite online-backup API) before the first change in this process.
"""
import logging
import os
import sqlite3

from flask import current_app, has_app_context
from werkzeug.security import generate_password_hash

from app.db import get_database_name, get_db, is_remote, turso_url
from app.utils.timeutil import utc_now, utc_now_iso

log = logging.getLogger(__name__)

# ---------------------------------------------------------------- legacy tables (unchanged)
LEGACY_TABLES = {
    "Admin": """
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
)""",
    "Users": """
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
)""",
    "Products": """
CREATE TABLE IF NOT EXISTS Products(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    Product_id VARCHAR(255) UNIQUE,
    name VARCHAR(255),
    price FLOAT,
    category VARCHAR(255),
    stock INTEGER,
    image_url VARCHAR(1000) DEFAULT NULL
)""",
    "Order_Details": """
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
)""",
    "Sell_History": """
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
)""",
}

# ---------------------------------------------------------------- new tables (Parts 1-3)
NEW_TABLES = {
    "Suppliers": """
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
)""",
    "Product_Batches": """
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
)""",
    "Stock_Movements": """
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
)""",
    "Audit_Log": """
CREATE TABLE IF NOT EXISTS Audit_Log(
    Audit_id TEXT PRIMARY KEY,
    actor_id TEXT,
    actor_role TEXT,
    action TEXT NOT NULL DEFAULT '',
    entity TEXT NOT NULL DEFAULT '',
    entity_id TEXT,
    details TEXT DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT ''
)""",
    "Device_Tokens": """
CREATE TABLE IF NOT EXISTS Device_Tokens(
    Device_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT '',
    token TEXT NOT NULL DEFAULT '' UNIQUE,
    platform TEXT NOT NULL DEFAULT 'android' CHECK(platform IN ('android','ios')),
    app_version TEXT DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
)""",
    "Idempotency_Keys": """
CREATE TABLE IF NOT EXISTS Idempotency_Keys(
    key TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '',
    endpoint TEXT NOT NULL DEFAULT '',
    response_json TEXT,
    status_code INTEGER NOT NULL DEFAULT 0,
    location TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(key, user_id, endpoint)
)""",
}

# ---------------------------------------------------------------- additive columns
ADD_COLUMNS = {
    "Admin": [
        ("role", "VARCHAR(20) DEFAULT 'admin'"),
        ("image_url", "VARCHAR(1000) DEFAULT NULL"),
        # Admin signup: existing admins keep access (DEFAULT 1 fills existing rows); new signups start at 0.
        ("is_approved", "INTEGER DEFAULT 1"),
        ("is_owner", "INTEGER DEFAULT 0"),
        ("is_email_verified", "INTEGER DEFAULT 1"),
    ],
    "Users": [
        ("image_url", "VARCHAR(1000) DEFAULT NULL"),
        ("is_email_verified", "INTEGER DEFAULT 1"),
    ],
    "Products": [
        ("image_url", "VARCHAR(1000) DEFAULT NULL"),
        ("generic_name", "TEXT DEFAULT ''"),
        ("brand_name", "TEXT DEFAULT ''"),
        ("manufacturer", "TEXT DEFAULT 'Unknown'"),
        ("category", "TEXT DEFAULT 'General'"),
        ("dosage_form", "TEXT DEFAULT 'Tablet'"),
        ("strength", "TEXT DEFAULT ''"),
        ("pack_size", "TEXT DEFAULT ''"),
        ("unit", "TEXT DEFAULT 'strip'"),
        ("hsn_code", "TEXT DEFAULT ''"),
        ("gst_percent", "REAL DEFAULT 12"),
        ("mrp", "REAL DEFAULT 0"),
        ("purchase_price", "REAL DEFAULT 0"),
        ("schedule_type", "TEXT DEFAULT 'OTC'"),
        ("requires_prescription", "INTEGER DEFAULT 0"),
        ("storage_conditions", "TEXT DEFAULT ''"),
        ("reorder_level", "INTEGER DEFAULT 10"),
        ("barcode", "TEXT DEFAULT ''"),
        ("is_active", "INTEGER DEFAULT 1"),
        ("created_at", "TEXT DEFAULT NULL"),
        ("updated_at", "TEXT DEFAULT NULL"),
    ],
    "Order_Details": [
        ("image_url", "VARCHAR(1000) DEFAULT NULL"),
        ("prescription_url", "TEXT DEFAULT ''"),
        ("doctor_name", "TEXT DEFAULT ''"),
        ("patient_name", "TEXT DEFAULT ''"),
        ("prescription_verified", "INTEGER DEFAULT 0"),
        ("status", "TEXT DEFAULT 'pending'"),
        ("cancel_reason", "TEXT DEFAULT ''"),
        ("updated_at", "TEXT DEFAULT NULL"),
        ("checkout_id", "VARCHAR(64) DEFAULT NULL"),
    ],
    "Sell_History": [
        ("image_url", "VARCHAR(1000) DEFAULT NULL"),
        ("batch_id", "TEXT DEFAULT ''"),
        ("batch_no", "TEXT DEFAULT ''"),
        ("gst_percent", "REAL DEFAULT 0"),
        ("sold_by", "TEXT DEFAULT ''"),
    ],
}

INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_products_barcode ON Products(barcode)",
    "CREATE INDEX IF NOT EXISTS ix_products_name ON Products(name)",
    "CREATE INDEX IF NOT EXISTS ix_batches_product ON Product_Batches(Product_id)",
    "CREATE INDEX IF NOT EXISTS ix_batches_expiry ON Product_Batches(expiry_date)",
    "CREATE INDEX IF NOT EXISTS ix_orders_user ON Order_Details(user_id)",
    "CREATE INDEX IF NOT EXISTS ix_orders_status ON Order_Details(status)",
    "CREATE INDEX IF NOT EXISTS ix_orders_checkout ON Order_Details(checkout_id)",
    "CREATE INDEX IF NOT EXISTS ix_sell_order ON Sell_History(Order_id)",
    "CREATE INDEX IF NOT EXISTS ix_sell_user ON Sell_History(user_id)",
    "CREATE INDEX IF NOT EXISTS ix_sell_product ON Sell_History(product_id)",
    "CREATE INDEX IF NOT EXISTS ix_movements_product ON Stock_Movements(Product_id, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_movements_created ON Stock_Movements(created_at)",
    "CREATE INDEX IF NOT EXISTS ix_audit_entity ON Audit_Log(entity, entity_id)",
    "CREATE INDEX IF NOT EXISTS ix_audit_created ON Audit_Log(created_at)",
    "CREATE INDEX IF NOT EXISTS ix_device_user ON Device_Tokens(user_id)",
    "CREATE INDEX IF NOT EXISTS ix_idempotency_created ON Idempotency_Keys(created_at)",
    # At most one owner admin (backs up the locked first-signup check).
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_admin_owner ON Admin(is_owner) WHERE is_owner = 1",
]

LEGACY_BATCH_EXPIRY = "9999-12-31"
_BACKED_UP = set()


# ---------------------------------------------------------------- helpers
def _db_path(db_name):
    return db_name or get_database_name()


def _table_exists(conn, table):
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _columns(conn, table):
    # PRAGMA cannot take bound parameters; `table` only ever comes from the constants above.
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def _backup_enabled(backup):
    if backup is not None:
        return bool(backup)
    if has_app_context():
        return bool(current_app.config.get("DB_BACKUP_ON_MIGRATE", True))
    return True


def migration_pending(conn):
    """True if any table or column from this migration is missing."""
    for table in list(LEGACY_TABLES) + list(NEW_TABLES):
        if not _table_exists(conn, table):
            return True
    for table, cols in ADD_COLUMNS.items():
        existing = _columns(conn, table)
        if any(name not in existing for name, _ in cols):
            return True
    return False


def backup_database(db_path):
    """Copy the DB to `<db>.bak-<UTC timestamp>` with the SQLite backup API. Returns the path."""
    target = f"{db_path}.bak-{utc_now().strftime('%Y%m%dT%H%M%S%fZ')}"
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    log.warning("Database backed up to %s before migration", target)
    return target


def _backup_if_needed(db_path, backup):
    """Back up once per process per DB path, only if the file exists and changes are pending."""
    if is_remote(db_path):
        return None  # Turso keeps its own point-in-time backups; there is no local file to copy
    key = os.path.abspath(db_path)
    if key in _BACKED_UP or not _backup_enabled(backup):
        return None
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        return None
    conn = get_db(db_path)
    try:
        pending = migration_pending(conn)
    finally:
        conn.close()
    if not pending:
        return None
    _BACKED_UP.add(key)
    return backup_database(db_path)


# ---------------------------------------------------------------- public API
def createTable(db_name=None, backup=None):
    """Create every table (legacy + new) if missing. Never alters existing data."""
    db_path = _db_path(db_name)
    _backup_if_needed(db_path, backup)
    conn = get_db(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        for ddl in LEGACY_TABLES.values():
            conn.execute(ddl)
        # FK parent key for Product_Batches/Stock_Movements. Legacy DBs created Products
        # without UNIQUE(Product_id); a unique index satisfies SQLite's FK requirement.
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_products_product_id ON Products(Product_id)"
            )
        except sqlite3.IntegrityError:
            raise RuntimeError(
                "Products contains duplicate Product_id values; resolve them manually "
                "before migrating (no rows are changed automatically)."
            )
        for ddl in NEW_TABLES.values():
            conn.execute(ddl)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def updateTable(db_name=None, backup=None):
    """Add missing columns, run backfills and create indexes. Safe to run repeatedly."""
    db_path = _db_path(db_name)
    _backup_if_needed(db_path, backup)
    conn = get_db(db_path)
    now = utc_now_iso()
    try:
        conn.execute("BEGIN IMMEDIATE")
        added = {}
        for table, cols in ADD_COLUMNS.items():
            existing = _columns(conn, table)
            for name, decl in cols:
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
                    added.setdefault(table, set()).add(name)

        # Legacy image backfills (kept from the previous migration; only fill NULLs)
        conn.execute("""
            UPDATE Order_Details SET image_url = (
                SELECT Products.image_url FROM Products WHERE Products.Product_id = Order_Details.product_id)
            WHERE image_url IS NULL""")
        conn.execute("""
            UPDATE Sell_History SET image_url = (
                SELECT Products.image_url FROM Products WHERE Products.Product_id = Sell_History.product_id)
            WHERE image_url IS NULL""")

        # Products timestamps (only fill NULLs)
        conn.execute("UPDATE Products SET created_at = ? WHERE created_at IS NULL", (now,))
        conn.execute("UPDATE Products SET updated_at = COALESCE(created_at, ?) WHERE updated_at IS NULL", (now,))

        # Order status derived from legacy flags, only when the column is first added
        if "status" in added.get("Order_Details", set()):
            conn.execute("""
                UPDATE Order_Details SET status = CASE
                    WHEN sold IN (1, '1', 'true', 'True')
                      OR EXISTS (SELECT 1 FROM Sell_History s WHERE s.Order_id = Order_Details.Order_id)
                        THEN 'sold'
                    WHEN isApproved IN (1, '1', 'true', 'True') THEN 'approved'
                    ELSE 'pending' END""")

        _backfill_legacy_batches(conn, now)

        for ddl in INDEXES:
            conn.execute(ddl)
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def _backfill_legacy_batches(conn, now):
    """One placeholder batch per product that has stock but no batch (expiry 9999-12-31).

    Also writes an opening-balance ADJUSTMENT movement so the ledger matches batch totals.
    Products with stock <= 0 get no placeholder (nothing to trace).
    """
    rows = conn.execute("""
        SELECT Product_id, CAST(COALESCE(stock, 0) AS INTEGER) AS qty, COALESCE(purchase_price, 0) AS pp,
               COALESCE(mrp, 0) AS mrp
        FROM Products p
        WHERE p.Product_id IS NOT NULL
          AND CAST(COALESCE(p.stock, 0) AS INTEGER) > 0
          AND NOT EXISTS (SELECT 1 FROM Product_Batches b WHERE b.Product_id = p.Product_id)
    """).fetchall()
    for row in rows:
        product_id, qty = row["Product_id"], row["qty"]
        batch_id = f"BAT_LEGACY_{product_id}"
        conn.execute("""
            INSERT OR IGNORE INTO Product_Batches(Batch_id, Product_id, batch_no, mfg_date, expiry_date, quantity,
                purchase_price, mrp, supplier_id, supplier_name, received_date, is_legacy_placeholder,
                created_at, updated_at)
            VALUES (?, ?, ?, NULL, ?, ?, ?, ?, NULL, '', NULL, 1, ?, ?)""",
            (batch_id, product_id, f"LEGACY-{product_id}", LEGACY_BATCH_EXPIRY, qty,
             row["pp"], row["mrp"], now, now))
        conn.execute("""
            INSERT OR IGNORE INTO Stock_Movements(Movement_id, Product_id, Batch_id, change_qty, reason,
                reference_id, performed_by, created_at)
            VALUES (?, ?, ?, ?, 'ADJUSTMENT', 'LEGACY-OPENING-BALANCE', 'system:migration', ?)""",
            (f"MOV_LEGACY_{product_id}", product_id, batch_id, qty, now))


def init_db(db_name=None, backup=None):
    """Full idempotent migration: backup (if needed) -> create tables -> add columns/backfill/indexes."""
    db_path = _db_path(db_name)
    backup_path = _backup_if_needed(db_path, backup)
    createTable(db_path, backup=False)
    updateTable(db_path, backup=False)
    return {"database": turso_url() if is_remote(db_path) else db_path, "backup": backup_path}


def migrate_passwords(db_name=None):
    """Legacy one-off: hash any plaintext Users.password values."""
    conn = get_db(_db_path(db_name))
    try:
        with conn:
            rows = conn.execute("SELECT id, password FROM Users").fetchall()
            for row_id, pwd in rows:
                if pwd and not (pwd.startswith("pbkdf2:") or pwd.startswith("scrypt:")):
                    conn.execute("UPDATE Users SET password = ? WHERE id = ?", (generate_password_hash(pwd), row_id))
    finally:
        conn.close()
