"""Batch, movement and inventory-alert queries (read side + batch rows). Stock changes go
through app.services.stock_service only."""
import uuid
from datetime import date

from app.errors import ConflictError, NotFoundError
from app.services.product_service import _int, _num
from app.utils.timeutil import to_iso_z, utc_date_after, utc_now_iso, utc_today

LEGACY_EXPIRY = "9999-12-31"

BATCH_SORT = {
    "expiry_date": "b.expiry_date",
    "batch_no": "b.batch_no COLLATE NOCASE",
    "received_date": "b.received_date",
    "quantity": "b.quantity",
    "created_at": "b.created_at",
}
MOVEMENT_SORT = {"created_at": "m.created_at", "change_qty": "m.change_qty"}
ALERT_BATCH_SORT = {"expiry_date": "b.expiry_date", "quantity": "b.quantity", "product_name": "p.name COLLATE NOCASE"}
ALERT_PRODUCT_SORT = {"stock": "p.stock", "name": "p.name COLLATE NOCASE", "reorder_level": "p.reorder_level"}

_BATCH_SELECT = "SELECT b.*, p.name AS product_name FROM Product_Batches b LEFT JOIN Products p ON p.Product_id = b.Product_id"


def _dir(order):
    return "DESC" if order == "desc" else "ASC"


def serialize_batch(row):
    keys = row.keys()
    expiry = row["expiry_date"]
    today = utc_today()
    legacy = bool(row["is_legacy_placeholder"])
    days = None
    if expiry and expiry != LEGACY_EXPIRY:
        try:
            days = (date.fromisoformat(expiry) - date.fromisoformat(today)).days
        except ValueError:
            days = None
    return {
        "batch_id": row["Batch_id"],
        "product_id": row["Product_id"],
        "product_name": row["product_name"] if "product_name" in keys else None,
        "batch_no": row["batch_no"],
        "mfg_date": row["mfg_date"],
        "expiry_date": expiry,
        "quantity": _int(row["quantity"], 0),
        "purchase_price": _num(row["purchase_price"]),
        "mrp": _num(row["mrp"]),
        "supplier_id": row["supplier_id"],
        "supplier_name": row["supplier_name"] or "",
        "received_date": row["received_date"],
        "is_legacy_placeholder": legacy,
        "is_expired": bool(expiry) and expiry < today,
        "days_to_expiry": days,
        "created_at": to_iso_z(row["created_at"]),
        "updated_at": to_iso_z(row["updated_at"]),
    }


def serialize_movement(row):
    keys = row.keys()
    return {
        "movement_id": row["Movement_id"],
        "product_id": row["Product_id"],
        "product_name": row["product_name"] if "product_name" in keys else None,
        "batch_id": row["Batch_id"],
        "batch_no": row["batch_no"] if "batch_no" in keys else None,
        "change_qty": _int(row["change_qty"], 0),
        "reason": row["reason"],
        "reference_id": row["reference_id"] or "",
        "performed_by": row["performed_by"] or "",
        "created_at": to_iso_z(row["created_at"]),
    }


def fetch_batch(conn, batch_id):
    row = conn.execute(f"{_BATCH_SELECT} WHERE b.Batch_id = ?", (batch_id,)).fetchone()
    if row is None:
        raise NotFoundError("Batch not found")
    return row


def fetch_batch_by_no(conn, product_id, batch_no):
    return conn.execute(
        f"{_BATCH_SELECT} WHERE b.Product_id = ? AND b.batch_no = ?", (product_id, batch_no)
    ).fetchone()


def fetch_supplier(conn, supplier_id):
    """Active supplier row or 404 (with `fields`)."""
    row = conn.execute(
        "SELECT * FROM Suppliers WHERE Supplier_id = ? AND COALESCE(is_active, 1) = 1", (supplier_id,)
    ).fetchone()
    if row is None:
        raise NotFoundError("Supplier not found", fields={"supplier_id": "unknown or inactive supplier"})
    return row


def insert_batch(conn, product_id, data):
    """Insert an empty (quantity 0) batch; stock is then added via stock_service. Returns Batch_id."""
    if fetch_batch_by_no(conn, product_id, data["batch_no"]) is not None:
        raise ConflictError("Batch number already exists for this product", fields={"batch_no": "already exists"})
    batch_id = "BAT_" + uuid.uuid4().hex[:12]
    now = utc_now_iso()
    conn.execute(
        """INSERT INTO Product_Batches(Batch_id, Product_id, batch_no, mfg_date, expiry_date, quantity,
               purchase_price, mrp, supplier_id, supplier_name, received_date, is_legacy_placeholder,
               created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, 0, ?, ?)""",
        (batch_id, product_id, data["batch_no"], data.get("mfg_date"), data["expiry_date"],
         data.get("purchase_price", 0.0), data.get("mrp", 0.0), data.get("supplier_id"),
         data.get("supplier_name", ""), data.get("received_date") or utc_today(), now, now),
    )
    return batch_id


BATCH_WRITABLE = ("batch_no", "mfg_date", "expiry_date", "purchase_price", "mrp",
                  "supplier_id", "supplier_name", "received_date")


def update_batch_fields(conn, batch_id, cleaned, clear_legacy_flag=False):
    sets, params = [], []
    for col in BATCH_WRITABLE:
        if col in cleaned:
            sets.append(f"{col} = ?")
            params.append(cleaned[col])
    if clear_legacy_flag:
        sets.append("is_legacy_placeholder = 0")
    sets.append("updated_at = ?")
    params.append(utc_now_iso())
    conn.execute(f"UPDATE Product_Batches SET {', '.join(sets)} WHERE Batch_id = ?", params + [batch_id])


def list_batches(conn, product_id, filters, limit, offset, sort, order):
    where, params = ["b.Product_id = ?"], [product_id]
    if filters.get("include_expired") is False:
        where.append("b.expiry_date >= ?")
        params.append(utc_today())
    if "in_stock" in filters:
        where.append("b.quantity > 0" if filters["in_stock"] else "b.quantity = 0")
    where_sql = " WHERE " + " AND ".join(where)
    total = conn.execute(f"SELECT COUNT(*) FROM Product_Batches b{where_sql}", params).fetchone()[0]
    rows = conn.execute(
        f"{_BATCH_SELECT}{where_sql} ORDER BY {BATCH_SORT[sort]} {_dir(order)}, b.Batch_id ASC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return rows, total


def list_movements(conn, filters, limit, offset, sort, order):
    where, params = [], []
    for key, col in (("product_id", "m.Product_id"), ("batch_id", "m.Batch_id"),
                     ("reason", "m.reason"), ("performed_by", "m.performed_by")):
        if filters.get(key):
            where.append(f"{col} = ?")
            params.append(filters[key])
    if filters.get("from"):
        where.append("m.created_at >= ?")
        params.append(filters["from"])
    if filters.get("to"):
        where.append("m.created_at <= ?")
        params.append(filters["to"])
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM Stock_Movements m{where_sql}", params).fetchone()[0]
    rows = conn.execute(
        "SELECT m.*, p.name AS product_name, b.batch_no AS batch_no FROM Stock_Movements m "
        "LEFT JOIN Products p ON p.Product_id = m.Product_id "
        f"LEFT JOIN Product_Batches b ON b.Batch_id = m.Batch_id{where_sql} "
        f"ORDER BY {MOVEMENT_SORT[sort]} {_dir(order)}, m.rowid {_dir(order)} LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return rows, total


def _batch_alert(conn, condition, params, limit, offset, sort, order):
    where_sql = f" WHERE b.quantity > 0 AND {condition}"
    total = conn.execute(
        f"SELECT COUNT(*) FROM Product_Batches b LEFT JOIN Products p ON p.Product_id = b.Product_id{where_sql}",
        params,
    ).fetchone()[0]
    rows = conn.execute(
        f"{_BATCH_SELECT}{where_sql} ORDER BY {ALERT_BATCH_SORT[sort]} {_dir(order)}, b.Batch_id ASC LIMIT ? OFFSET ?",
        list(params) + [limit, offset],
    ).fetchall()
    return rows, total


def near_expiry_batches(conn, days, limit, offset, sort, order):
    """In-stock batches expiring between today and today+days (inclusive)."""
    return _batch_alert(conn, "b.expiry_date >= ? AND b.expiry_date <= ?",
                        [utc_today(), utc_date_after(days)], limit, offset, sort, order)


def expired_batches(conn, limit, offset, sort, order):
    """In-stock batches already past expiry (candidates for write-off)."""
    return _batch_alert(conn, "b.expiry_date < ?", [utc_today()], limit, offset, sort, order)


def _product_alert(conn, condition, limit, offset, sort, order):
    where_sql = f" WHERE COALESCE(p.is_active, 1) = 1 AND {condition}"
    total = conn.execute(f"SELECT COUNT(*) FROM Products p{where_sql}").fetchone()[0]
    rows = conn.execute(
        f"SELECT p.* FROM Products p{where_sql} ORDER BY {ALERT_PRODUCT_SORT[sort]} {_dir(order)}, p.id ASC "
        "LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return rows, total


def low_stock_products(conn, limit, offset, sort, order):
    return _product_alert(conn, "COALESCE(p.stock, 0) <= COALESCE(p.reorder_level, 10)", limit, offset, sort, order)


def out_of_stock_products(conn, limit, offset, sort, order):
    return _product_alert(conn, "COALESCE(p.stock, 0) <= 0", limit, offset, sort, order)
