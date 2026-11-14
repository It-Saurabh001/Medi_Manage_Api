"""The ONLY module allowed to change stock.

Every change goes through a batch row, writes an append-only Stock_Movements row and
recomputes Products.stock as the sum of batch quantities.

Transactions: callers open `BEGIN IMMEDIATE` (e.g. `app.db.db_connection(immediate=True)`)
and commit. This module never commits; each public function runs inside a SAVEPOINT so a
raised error leaves nothing changed even if the caller forgets to roll back.
"""
import uuid
from contextlib import contextmanager

from app.errors import ApiError, NotFoundError, ValidationError
from app.utils.timeutil import utc_now_iso, utc_today

REASONS = ("PURCHASE", "SALE", "ADJUSTMENT", "EXPIRED_WRITEOFF", "RETURN", "CANCEL_RESTOCK")


class OutOfStock(ApiError):
    status = 409
    code = "OUT_OF_STOCK"
    message = "Not enough stock available"


class BatchExpired(ApiError):
    status = 409
    code = "BATCH_EXPIRED"
    message = "Batch is expired"


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


def _check_qty(qty, allow_negative=False):
    if isinstance(qty, bool) or not isinstance(qty, int):
        raise ValidationError(fields={"quantity": "must be an integer"})
    if qty == 0 or (qty < 0 and not allow_negative):
        raise ValidationError(fields={"quantity": "must be non-zero" if allow_negative else "must be >= 1"})


def _insert_movement(conn, product_id, batch_id, change_qty, reason, reference_id, performed_by):
    movement_id = "MOV_" + uuid.uuid4().hex[:16]
    created_at = utc_now_iso()
    conn.execute(
        """INSERT INTO Stock_Movements(Movement_id, Product_id, Batch_id, change_qty, reason,
               reference_id, performed_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (movement_id, product_id, batch_id, change_qty, reason,
         reference_id or "", performed_by or "", created_at),
    )
    return {
        "movement_id": movement_id,
        "product_id": product_id,
        "batch_id": batch_id,
        "change_qty": change_qty,
        "reason": reason,
        "reference_id": reference_id or "",
        "performed_by": performed_by or "",
        "created_at": created_at,
    }


def _change_batch(conn, product_id, batch_id, change_qty):
    """Atomically apply a delta to one batch, never letting it go negative."""
    now = utc_now_iso()
    if change_qty < 0:
        cur = conn.execute(
            """UPDATE Product_Batches SET quantity = quantity - ?, updated_at = ?
               WHERE Batch_id = ? AND Product_id = ? AND quantity >= ?""",
            (-change_qty, now, batch_id, product_id, -change_qty),
        )
    else:
        cur = conn.execute(
            """UPDATE Product_Batches SET quantity = quantity + ?, updated_at = ?
               WHERE Batch_id = ? AND Product_id = ?""",
            (change_qty, now, batch_id, product_id),
        )
    if cur.rowcount == 1:
        return
    exists = conn.execute(
        "SELECT 1 FROM Product_Batches WHERE Batch_id = ? AND Product_id = ?", (batch_id, product_id)
    ).fetchone()
    if not exists:
        raise NotFoundError("Batch not found for this product")
    raise OutOfStock("Batch quantity cannot go below zero")


def recompute_stock(conn, product_id):
    """Set Products.stock = SUM(batch quantities) and bump updated_at. Returns the new stock."""
    total = conn.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM Product_Batches WHERE Product_id = ?", (product_id,)
    ).fetchone()[0]
    conn.execute(
        "UPDATE Products SET stock = ?, updated_at = ? WHERE Product_id = ?",
        (int(total), utc_now_iso(), product_id),
    )
    return int(total)


def apply_stock_change(conn, product_id, batch_id, change_qty, reason, reference_id, performed_by):
    """Apply a signed delta to one batch, write a movement, recompute stock. Returns the movement dict."""
    if reason not in REASONS:
        raise ValidationError(fields={"reason": f"must be one of: {', '.join(REASONS)}"})
    _check_qty(change_qty, allow_negative=True)
    with _savepoint(conn):
        _change_batch(conn, product_id, batch_id, change_qty)
        movement = _insert_movement(conn, product_id, batch_id, change_qty, reason, reference_id, performed_by)
        movement["product_stock"] = recompute_stock(conn, product_id)
    return movement


def deduct_fefo(conn, product_id, qty, reference_id, performed_by):
    """Deduct `qty` First-Expiry-First-Out from non-expired batches (reason SALE).

    Returns [{"batch_id","batch_no","qty"}]. Raises OutOfStock with nothing changed if the
    non-expired quantity is insufficient.
    """
    _check_qty(qty)
    today = utc_today()
    batches = conn.execute(
        """SELECT Batch_id, batch_no, quantity FROM Product_Batches
           WHERE Product_id = ? AND quantity > 0 AND expiry_date >= ?
           ORDER BY expiry_date ASC, COALESCE(received_date, '') ASC, Batch_id ASC""",
        (product_id, today),
    ).fetchall()
    available = sum(b["quantity"] for b in batches)
    if available < qty:
        raise OutOfStock(f"Only {available} unit(s) available", fields={"quantity": f"available: {available}"})

    allocations = []
    with _savepoint(conn):
        remaining = qty
        for batch in batches:
            if remaining == 0:
                break
            take = min(remaining, batch["quantity"])
            cur = conn.execute(
                """UPDATE Product_Batches SET quantity = quantity - ?, updated_at = ?
                   WHERE Batch_id = ? AND quantity >= ?""",
                (take, utc_now_iso(), batch["Batch_id"], take),
            )
            if cur.rowcount != 1:
                raise OutOfStock("Stock changed concurrently; retry")
            _insert_movement(conn, product_id, batch["Batch_id"], -take, "SALE", reference_id, performed_by)
            allocations.append({"batch_id": batch["Batch_id"], "batch_no": batch["batch_no"], "qty": take})
            remaining -= take
        recompute_stock(conn, product_id)
    return allocations


def restock_to_batch(conn, batch_id, qty, reason, reference_id, performed_by):
    """Add `qty` back to a batch (RETURN / CANCEL_RESTOCK / PURCHASE / ADJUSTMENT).

    RETURN into an expired batch is refused with BATCH_EXPIRED. Returns the movement dict.
    """
    _check_qty(qty)
    batch = conn.execute(
        "SELECT Product_id, expiry_date FROM Product_Batches WHERE Batch_id = ?", (batch_id,)
    ).fetchone()
    if batch is None:
        raise NotFoundError("Batch not found")
    if reason == "RETURN" and batch["expiry_date"] < utc_today():
        raise BatchExpired("Cannot return stock into an expired batch")
    return apply_stock_change(conn, batch["Product_id"], batch_id, qty, reason, reference_id, performed_by)
