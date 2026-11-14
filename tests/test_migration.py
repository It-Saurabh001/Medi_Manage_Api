import glob
import os
import sqlite3

from app.services.db_init import init_db

LEGACY_SCHEMA = [
    """CREATE TABLE Users(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id VARCHAR(255), password VARCHAR(255),
       date_of_account_creation DATE, isApproved BOOLEAN, block BOOLEAN, name VARCHAR(255), address VARCHAR(255),
       email VARCHAR(255), phone_number VARCHAR(255), pin_code VARCHAR(255), role VARCHAR(20) DEFAULT 'user')""",
    """CREATE TABLE Admin(id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id TEXT UNIQUE, password TEXT, name TEXT,
       email TEXT UNIQUE, phone_number TEXT UNIQUE, date_of_account_creation DATE)""",
    # Real legacy DB: Product_id has no UNIQUE constraint, stock declared INTEGER(255)
    """CREATE TABLE Products(id INTEGER PRIMARY KEY AUTOINCREMENT, Product_id VARCHAR(255), name VARCHAR(255),
       price FLOAT, category VARCHAR(255), stock INTEGER(255))""",
    """CREATE TABLE Order_Details(id INTEGER PRIMARY KEY AUTOINCREMENT, Order_id VARCHAR(255), user_id VARCHAR(255),
       product_id VARCHAR(255), isApproved BOOLEAN, quantity INTEGER(255), date_of_order_creation DATE, price FLOAT,
       total_amount FLOAT, product_name VARCHAR(255), user_name VARCHAR(255), message VARCHAR(1000),
       category VARCHAR(255), sold BOOLEAN)""",
    """CREATE TABLE Sell_History(id INTEGER PRIMARY KEY AUTOINCREMENT, Sell_id VARCHAR(255), product_id VARCHAR(255),
       Order_id VARCHAR(255), isApproved BOOLEAN, quantity INTEGER(255), Remaining_stock INTEGER(255),
       date_of_sell DATE, total_amount FLOAT, price FLOAT, product_name VARCHAR(255), user_id VARCHAR(255),
       user_name VARCHAR(255))""",
]


def _legacy_db(path):
    conn = sqlite3.connect(path)
    for ddl in LEGACY_SCHEMA:
        conn.execute(ddl)
    conn.executemany(
        "INSERT INTO Products(Product_id, name, price, category, stock) VALUES (?,?,?,?,?)",
        [("PROD_A", "Aspirin", 10.0, "Pain", 25), ("PROD_B", "Bandage", 5.0, "Care", 0)],
    )
    conn.executemany(
        """INSERT INTO Order_Details(Order_id, user_id, product_id, isApproved, quantity, price, total_amount, sold)
           VALUES (?,?,?,?,?,?,?,?)""",
        [("ORD1", "U1", "PROD_A", 0, 1, 10, 10, 0),
         ("ORD2", "U1", "PROD_A", 1, 2, 10, 20, 0),
         ("ORD3", "U1", "PROD_A", 1, 3, 10, 30, 0)],
    )
    conn.execute("INSERT INTO Sell_History(Sell_id, product_id, Order_id, quantity) VALUES ('S1','PROD_A','ORD3',3)")
    conn.execute("INSERT INTO Users(user_id, name, password) VALUES ('U1', 'Old User', 'scrypt:x')")
    conn.commit()
    conn.close()


def _counts(conn):
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in ("Users", "Products", "Order_Details", "Sell_History", "Product_Batches", "Stock_Movements")}


def test_migration_preserves_rows_backfills_and_is_idempotent(tmp_path):
    db = str(tmp_path / "legacy.db")
    _legacy_db(db)

    result = init_db(db, backup=True)
    assert result["backup"] and os.path.exists(result["backup"])
    assert result["backup"].startswith(db + ".bak-")

    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    first = _counts(conn)
    assert first["Users"] == 1 and first["Products"] == 2 and first["Order_Details"] == 3 and first["Sell_History"] == 1

    # New columns with defaults; legacy values untouched
    a = conn.execute("SELECT * FROM Products WHERE Product_id='PROD_A'").fetchone()
    assert a["name"] == "Aspirin" and a["stock"] == 25 and a["price"] == 10.0
    assert a["schedule_type"] == "OTC" and a["is_active"] == 1 and a["gst_percent"] == 12
    assert a["created_at"].endswith("Z") and a["updated_at"].endswith("Z")

    # Legacy placeholder batch only for stocked products, with opening-balance movement
    batches = conn.execute("SELECT * FROM Product_Batches").fetchall()
    assert len(batches) == 1
    b = batches[0]
    assert (b["Product_id"], b["batch_no"], b["expiry_date"], b["quantity"], b["is_legacy_placeholder"]) == \
        ("PROD_A", "LEGACY-PROD_A", "9999-12-31", 25, 1)
    mv = conn.execute("SELECT * FROM Stock_Movements").fetchall()
    assert len(mv) == 1 and mv[0]["change_qty"] == 25 and mv[0]["reason"] == "ADJUSTMENT"

    # Order status derived from legacy flags
    status = dict(conn.execute("SELECT Order_id, status FROM Order_Details").fetchall())
    assert status == {"ORD1": "pending", "ORD2": "approved", "ORD3": "sold"}

    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"Suppliers", "Audit_Log", "Device_Tokens", "Idempotency_Keys", "Product_Batches", "Stock_Movements"} <= tables
    conn.close()

    # Second run: nothing pending -> no new backup, no duplicate rows
    backups_before = set(glob.glob(db + ".bak-*"))
    second = init_db(db, backup=True)
    assert second["backup"] is None
    assert set(glob.glob(db + ".bak-*")) == backups_before
    conn = sqlite3.connect(db)
    assert _counts(conn) == first
    conn.close()

    # Backup is a faithful copy of the pre-migration DB
    bconn = sqlite3.connect(result["backup"])
    cols = [r[1] for r in bconn.execute("PRAGMA table_info(Products)")]
    assert "schedule_type" not in cols
    assert bconn.execute("SELECT COUNT(*) FROM Products").fetchone()[0] == 2
    bconn.close()


def test_migration_on_fresh_db(tmp_path):
    db = str(tmp_path / "fresh.db")
    result = init_db(db, backup=True)
    assert result["backup"] is None  # nothing to back up
    conn = sqlite3.connect(db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(Order_Details)")}
    assert {"status", "prescription_url", "cancel_reason", "updated_at"} <= cols
    conn.close()
