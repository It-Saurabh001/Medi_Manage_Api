"""Orders, sales and invoices (Part 2 domain).

Stock is only touched through app.services.stock_service (deduct_fefo / restock_to_batch).
Callers own the transaction (`db_connection(immediate=True)`); nothing here commits.
"""
import uuid

from app.errors import ApiError, ConflictError, ForbiddenError, NotFoundError
from app.services import stock_service
from app.services.product_service import RX_SCHEDULES
from app.utils.timeutil import to_iso_z, utc_now_iso

STATUSES = ("pending", "approved", "sold", "cancelled", "returned")
# action -> (allowed from-statuses, resulting status)
TRANSITIONS = {
    "approve": ({"pending"}, "approved"),
    "reject": ({"pending", "approved"}, "cancelled"),
    "cancel": ({"pending", "approved"}, "cancelled"),
    "sell": ({"approved"}, "sold"),
    "return": ({"sold"}, "returned"),
}
USER_CANCELLABLE = {"pending"}
EDITABLE_WHILE_PENDING = ("patient_name", "doctor_name")
SERVER_COMPUTED = ("total_amount", "price", "quantity", "status", "sold", "isApproved", "is_approved",
                   "user_id", "product_id", "prescription_verified", "user_name", "product_name")

ORDER_SORT = {
    "created_at": "o.date_of_order_creation",
    "updated_at": "COALESCE(o.updated_at, o.date_of_order_creation)",
    "total_amount": "o.total_amount",
    "status": "o.status",
}
SALE_SORT = {"sold_at": "s.date_of_sell", "total_amount": "s.total_amount", "quantity": "s.quantity"}

_ORDER_SELECT = (
    "SELECT o.*, p.requires_prescription AS p_requires_rx, p.schedule_type AS p_schedule, "
    "p.image_url AS p_image_url, p.gst_percent AS p_gst "
    "FROM Order_Details o LEFT JOIN Products p ON p.Product_id = o.product_id"
)
_SALE_SELECT = (
    "SELECT s.*, p.image_url AS p_image_url, o.status AS order_status "
    "FROM Sell_History s LEFT JOIN Products p ON p.Product_id = s.product_id "
    "LEFT JOIN Order_Details o ON o.Order_id = s.Order_id"
)


class InvalidTransition(ApiError):
    status = 409
    code = "INVALID_TRANSITION"
    message = "Order status does not allow this action"


class AlreadySold(ApiError):
    status = 409
    code = "ALREADY_SOLD"
    message = "Order has already been sold"


# Doctor name stored when a customer orders a prescription medicine without a prescription.
SELF_PRESCRIBED = "Self prescribed"


class PrescriptionRequired(ApiError):
    status = 400
    code = "PRESCRIPTION_REQUIRED"
    message = "This product requires a prescription"


class PrescriptionNotVerified(ApiError):
    status = 409
    code = "PRESCRIPTION_NOT_VERIFIED"
    message = "Prescription must be verified before sale"


# ------------------------------------------------------------------ small helpers
def _truthy(value):
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


def _num(value):
    try:
        return None if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return None


def _int(value, default=0):
    try:
        return default if value is None or value == "" else int(float(value))
    except (TypeError, ValueError):
        return default


def _blank_to_none(value):
    return None if value in (None, "") else value


def money(value):
    return round(float(value or 0) + 0.0, 2)


def order_status(row):
    """Effective status (legacy rows without status fall back to flags)."""
    status = row["status"]
    if status in STATUSES:
        return status
    if _truthy(row["sold"]):
        return "sold"
    return "approved" if _truthy(row["isApproved"]) else "pending"


def order_requires_prescription(row):
    keys = row.keys()
    rx = _truthy(row["p_requires_rx"]) if "p_requires_rx" in keys else False
    schedule = row["p_schedule"] if "p_schedule" in keys else None
    return rx or (schedule in RX_SCHEDULES)


def require_transition(row, action):
    allowed, target = TRANSITIONS[action]
    current = order_status(row)
    if current not in allowed:
        raise InvalidTransition(f"Cannot {action} an order that is {current}")
    return target


# ------------------------------------------------------------------ serialisers
def serialize_order(row):
    keys = row.keys()
    return {
        "order_id": row["Order_id"],
        "user_id": row["user_id"],
        "user_name": row["user_name"],
        "product_id": row["product_id"],
        "product_name": row["product_name"],
        "category": row["category"],
        "quantity": _int(row["quantity"]),
        "price": _num(row["price"]),
        "total_amount": _num(row["total_amount"]),
        "status": order_status(row),
        "message": row["message"] or "",
        "requires_prescription": order_requires_prescription(row),
        "prescription_url": _blank_to_none(row["prescription_url"]),
        "prescription_verified": _truthy(row["prescription_verified"]),
        "doctor_name": row["doctor_name"] or "",
        "patient_name": row["patient_name"] or "",
        "cancel_reason": row["cancel_reason"] or "",
        "image_url": row["image_url"] or (row["p_image_url"] if "p_image_url" in keys else None),
        "created_at": to_iso_z(row["date_of_order_creation"]),
        "updated_at": to_iso_z(row["updated_at"]),
        "checkout_id": (row["checkout_id"] or None) if "checkout_id" in keys else None,
    }


def serialize_sale(row):
    keys = row.keys()
    return {
        "sale_id": row["Sell_id"],
        "order_id": row["Order_id"],
        "order_status": row["order_status"] if "order_status" in keys else None,
        "product_id": row["product_id"],
        "product_name": row["product_name"],
        "user_id": row["user_id"],
        "user_name": row["user_name"],
        "batch_id": _blank_to_none(row["batch_id"]),
        "batch_no": _blank_to_none(row["batch_no"]),
        "quantity": _int(row["quantity"]),
        "price": _num(row["price"]),
        "total_amount": _num(row["total_amount"]),
        "gst_percent": _num(row["gst_percent"]),
        "remaining_stock": _int(row["Remaining_stock"], None),
        "sold_by": _blank_to_none(row["sold_by"]),
        "image_url": row["image_url"] or (row["p_image_url"] if "p_image_url" in keys else None),
        "sold_at": to_iso_z(row["date_of_sell"]),
    }


# ------------------------------------------------------------------ users
def fetch_customer(conn, user_id):
    row = conn.execute(
        "SELECT user_id, name, email, phone_number, address, pin_code, isApproved, block FROM Users WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if row is None:
        raise ForbiddenError("User account not found")
    return row


def ensure_customer_can_order(user_row):
    if _truthy(user_row["block"]):
        raise ApiError("Account is blocked", 403, "ACCOUNT_BLOCKED")
    if not _truthy(user_row["isApproved"]):
        raise ApiError("Account is not approved yet", 403, "ACCOUNT_NOT_APPROVED")


def serialize_customer(row):
    if row is None:
        return None
    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "email": row["email"],
        "phone_number": row["phone_number"],
        "address": row["address"],
        "pin_code": row["pin_code"],
    }


# ------------------------------------------------------------------ orders
def fetch_order(conn, order_id, owner_id=None):
    """Order row; with owner_id set, other users' orders are reported as 404 (no ID probing)."""
    sql, params = f"{_ORDER_SELECT} WHERE o.Order_id = ?", [order_id]
    if owner_id is not None:
        sql += " AND o.user_id = ?"
        params.append(owner_id)
    row = conn.execute(sql, params).fetchone()
    if row is None:
        raise NotFoundError("Order not found")
    return row


def insert_order(conn, user_row, product_row, quantity, data, checkout_id=None):
    order_id = "ORD_" + uuid.uuid4().hex[:12]
    now = utc_now_iso()
    price = money(product_row["price"])
    conn.execute(
        """INSERT INTO Order_Details(Order_id, user_id, product_id, isApproved, quantity, date_of_order_creation,
               price, total_amount, product_name, user_name, message, category, sold, image_url,
               prescription_url, doctor_name, patient_name, prescription_verified, status, cancel_reason, updated_at,
               checkout_id)
           VALUES (?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 0, 'pending', '', ?, ?)""",
        (order_id, user_row["user_id"], product_row["Product_id"], quantity, now, price, money(price * quantity),
         product_row["name"], user_row["name"], data.get("message", ""), product_row["category"],
         product_row["image_url"], data.get("prescription_url", ""), data.get("doctor_name", ""),
         data.get("patient_name", ""), now, checkout_id),
    )
    return order_id


def set_order_fields(conn, order_id, **fields):
    """Update whitelisted Order_Details columns (names are code constants, never client input)."""
    allowed = {"status", "isApproved", "sold", "cancel_reason", "prescription_verified", "prescription_url",
               "doctor_name", "patient_name"}
    sets, params = [], []
    for col, value in fields.items():
        if col not in allowed:
            raise ValueError(f"column not updatable: {col}")
        sets.append(f"{col} = ?")
        params.append(value)
    sets.append("updated_at = ?")
    params.append(utc_now_iso())
    conn.execute(f"UPDATE Order_Details SET {', '.join(sets)} WHERE Order_id = ?", params + [order_id])


def list_orders(conn, filters, limit, offset, sort, order):
    where, params = [], []
    for key, col in (("user_id", "o.user_id"), ("product_id", "o.product_id"), ("status", "o.status"),
                     ("checkout_id", "o.checkout_id")):
        if filters.get(key):
            where.append(f"{col} = ?")
            params.append(filters[key])
    if filters.get("from"):
        where.append("substr(o.date_of_order_creation, 1, 10) >= ?")
        params.append(filters["from"])
    if filters.get("to"):
        where.append("substr(o.date_of_order_creation, 1, 10) <= ?")
        params.append(filters["to"])
    if filters.get("updated_since"):
        where.append("COALESCE(o.updated_at, o.date_of_order_creation) >= ?")
        params.append(filters["updated_since"])
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM Order_Details o{where_sql}", params).fetchone()[0]
    direction = "DESC" if order == "desc" else "ASC"
    rows = conn.execute(
        f"{_ORDER_SELECT}{where_sql} ORDER BY {ORDER_SORT[sort]} {direction}, o.id {direction} LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return rows, total


# ------------------------------------------------------------------ sales
def sales_for_order(conn, order_id):
    return conn.execute(f"{_SALE_SELECT} WHERE s.Order_id = ? ORDER BY s.id ASC", (order_id,)).fetchall()


def list_sales(conn, filters, limit, offset, sort, order):
    where, params = [], []
    for key, col in (("product_id", "s.product_id"), ("user_id", "s.user_id"), ("order_id", "s.Order_id"),
                     ("batch_id", "s.batch_id")):
        if filters.get(key):
            where.append(f"{col} = ?")
            params.append(filters[key])
    if filters.get("from"):
        where.append("substr(s.date_of_sell, 1, 10) >= ?")
        params.append(filters["from"])
    if filters.get("to"):
        where.append("substr(s.date_of_sell, 1, 10) <= ?")
        params.append(filters["to"])
    if filters.get("updated_since"):
        where.append("s.date_of_sell >= ?")
        params.append(filters["updated_since"])
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM Sell_History s{where_sql}", params).fetchone()[0]
    direction = "DESC" if order == "desc" else "ASC"
    rows = conn.execute(
        f"{_SALE_SELECT}{where_sql} ORDER BY {SALE_SORT[sort]} {direction}, s.id {direction} LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return rows, total


def sell_order(conn, order_row, sold_by):
    """Deduct FEFO stock and write one Sell_History row per batch. Returns list of sale rows.

    Raises AlreadySold / InvalidTransition / PrescriptionNotVerified / OutOfStock. The caller's
    transaction must be rolled back on any error.
    """
    order_id = order_row["Order_id"]
    if order_status(order_row) == "sold" or conn.execute(
            "SELECT 1 FROM Sell_History WHERE Order_id = ? LIMIT 1", (order_id,)).fetchone():
        raise AlreadySold()
    require_transition(order_row, "sell")
    if order_requires_prescription(order_row) and not _truthy(order_row["prescription_verified"]):
        raise PrescriptionNotVerified()

    quantity = _int(order_row["quantity"])
    allocations = stock_service.deduct_fefo(conn, order_row["product_id"], quantity, order_id, sold_by)
    remaining = conn.execute("SELECT stock FROM Products WHERE Product_id = ?",
                             (order_row["product_id"],)).fetchone()[0]
    price = money(order_row["price"])
    gst = _num(order_row["p_gst"]) or 0.0
    now = utc_now_iso()
    for alloc in allocations:
        conn.execute(
            """INSERT INTO Sell_History(Sell_id, product_id, Order_id, isApproved, quantity, Remaining_stock,
                   date_of_sell, total_amount, price, product_name, user_id, user_name, image_url,
                   batch_id, batch_no, gst_percent, sold_by)
               VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("SELL_" + uuid.uuid4().hex[:12], order_row["product_id"], order_id, alloc["qty"], remaining, now,
             money(price * alloc["qty"]), price, order_row["product_name"], order_row["user_id"],
             order_row["user_name"], order_row["image_url"] or order_row["p_image_url"],
             alloc["batch_id"], alloc["batch_no"], gst, sold_by),
        )
    set_order_fields(conn, order_id, status="sold", sold=1, isApproved=1)
    return sales_for_order(conn, order_id)


def restock_deducted(conn, order_id, performed_by):
    """Put back any stock still deducted for this order (net of SALE/RETURN/CANCEL_RESTOCK movements)."""
    rows = conn.execute(
        """SELECT Batch_id, SUM(change_qty) AS net FROM Stock_Movements
           WHERE reference_id = ? AND reason IN ('SALE', 'RETURN', 'CANCEL_RESTOCK') AND Batch_id IS NOT NULL
           GROUP BY Batch_id HAVING SUM(change_qty) < 0""",
        (order_id,),
    ).fetchall()
    restocked = []
    for row in rows:
        qty = -int(row["net"])
        stock_service.restock_to_batch(conn, row["Batch_id"], qty, "CANCEL_RESTOCK", order_id, performed_by)
        restocked.append({"batch_id": row["Batch_id"], "qty": qty})
    return restocked


def return_order(conn, order_row, performed_by):
    """Restore stock per Sell_History batch with RETURN; expired / batch-less lines are reported, not restocked."""
    require_transition(order_row, "return")
    order_id = order_row["Order_id"]
    restocked, not_restocked = [], []
    for sale in sales_for_order(conn, order_id):
        qty = _int(sale["quantity"])
        line = {"batch_id": _blank_to_none(sale["batch_id"]), "batch_no": _blank_to_none(sale["batch_no"]), "qty": qty}
        if not sale["batch_id"]:
            not_restocked.append({**line, "reason": "NO_BATCH"})
            continue
        try:
            stock_service.restock_to_batch(conn, sale["batch_id"], qty, "RETURN", order_id, performed_by)
            restocked.append(line)
        except stock_service.BatchExpired:
            not_restocked.append({**line, "reason": "BATCH_EXPIRED"})
        except NotFoundError:
            not_restocked.append({**line, "reason": "BATCH_NOT_FOUND"})
    return restocked, not_restocked


# ------------------------------------------------------------------ invoice
def build_invoice(conn, order_row):
    """Invoice JSON for a sold/returned order. Prices are GST-inclusive (Indian retail MRP convention)."""
    status = order_status(order_row)
    if status not in ("sold", "returned"):
        raise InvalidTransition("Invoice is available only after the order is sold")
    sales = conn.execute(
        """SELECT s.*, b.expiry_date AS expiry_date FROM Sell_History s
           LEFT JOIN Product_Batches b ON b.Batch_id = s.batch_id
           WHERE s.Order_id = ? ORDER BY s.id ASC""",
        (order_row["Order_id"],),
    ).fetchall()
    items, subtotal, gst_total, grand_total = [], 0.0, 0.0, 0.0
    issued_at = None
    for sale in sales:
        qty = _int(sale["quantity"])
        unit = money(sale["price"])
        gst_pct = _num(sale["gst_percent"]) or 0.0
        line_total = money(unit * qty)
        taxable = money(line_total * 100 / (100 + gst_pct))
        gst_amount = money(line_total - taxable)
        subtotal += taxable
        gst_total += gst_amount
        grand_total += line_total
        issued_at = issued_at or to_iso_z(sale["date_of_sell"])
        items.append({
            "product_id": sale["product_id"],
            "product_name": sale["product_name"],
            "batch_id": _blank_to_none(sale["batch_id"]),
            "batch_no": _blank_to_none(sale["batch_no"]),
            "expiry_date": sale["expiry_date"],
            "quantity": qty,
            "unit_price": unit,
            "gst_percent": gst_pct,
            "taxable_amount": taxable,
            "gst_amount": gst_amount,
            "line_total": line_total,
        })
    user = conn.execute(
        "SELECT user_id, name, email, phone_number, address, pin_code FROM Users WHERE user_id = ?",
        (order_row["user_id"],),
    ).fetchone()
    return {
        "invoice_number": f"INV-{order_row['Order_id']}",
        "currency": "INR",
        "prices_include_gst": True,
        "order": serialize_order(order_row),
        "user": serialize_customer(user),
        "items": items,
        "subtotal": money(subtotal),
        "gst_total": money(gst_total),
        "grand_total": money(grand_total),
        "issued_at": issued_at,
        "generated_at": utc_now_iso(),
    }


def fetch_checkout_orders(conn, checkout_id, owner_id=None):
    """All orders of one checkout (oldest first); other users' checkouts are reported as 404."""
    sql, params = f"{_ORDER_SELECT} WHERE o.checkout_id = ?", [checkout_id]
    if owner_id is not None:
        sql += " AND o.user_id = ?"
        params.append(owner_id)
    rows = conn.execute(sql + " ORDER BY o.id ASC", params).fetchall()
    if not rows:
        raise NotFoundError("Checkout not found")
    return rows


def build_checkout_invoice(conn, checkout_id, owner_id=None):
    """One invoice for every sold/returned order of a checkout (same shape as build_invoice)."""
    rows = fetch_checkout_orders(conn, checkout_id, owner_id)
    billed = [r for r in rows if order_status(r) in ("sold", "returned")]
    if not billed:
        raise InvalidTransition("Invoice is available only after an order of this checkout is sold")
    parts = [build_invoice(conn, r) for r in billed]
    items = [item for part in parts for item in part["items"]]
    issued = sorted(p["issued_at"] for p in parts if p["issued_at"])
    return {
        "invoice_number": f"INV-{checkout_id}",
        "checkout_id": checkout_id,
        "currency": "INR",
        "prices_include_gst": True,
        "order": parts[0]["order"],
        "orders": [p["order"] for p in parts],
        "user": parts[0]["user"],
        "items": items,
        "subtotal": money(sum(p["subtotal"] for p in parts)),
        "gst_total": money(sum(p["gst_total"] for p in parts)),
        "grand_total": money(sum(p["grand_total"] for p in parts)),
        "issued_at": issued[0] if issued else None,
        "generated_at": utc_now_iso(),
    }
