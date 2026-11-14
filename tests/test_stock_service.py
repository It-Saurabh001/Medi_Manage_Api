import pytest

from app.db import db_connection, get_db
from app.services import inventory_service as inv
from app.services import product_service as ps
from app.services import stock_service as ss
from app.utils.timeutil import utc_date_after


def _setup(app):
    """Product with batches: A (30d, 3), B (200d, 5), EXPIRED (-5d, 10)."""
    with app.app_context():
        with db_connection(immediate=True) as conn:
            pid = ps.insert_product(conn, {"name": "Amoxicillin", "price": 50.0})
            ids = {}
            for name, days, qty in (("A", 30, 3), ("B", 200, 5), ("EXP", -5, 10)):
                bid = inv.insert_batch(conn, pid, {"batch_no": name, "expiry_date": utc_date_after(days)})
                ss.apply_stock_change(conn, pid, bid, qty, "PURCHASE", bid, "tester")
                ids[name] = bid
    return pid, ids


def _state(app, pid):
    with app.app_context():
        conn = get_db()
        try:
            batches = {r["batch_no"]: r["quantity"] for r in conn.execute(
                "SELECT batch_no, quantity FROM Product_Batches WHERE Product_id = ?", (pid,))}
            stock = conn.execute("SELECT stock FROM Products WHERE Product_id = ?", (pid,)).fetchone()[0]
            moves = conn.execute("SELECT COUNT(*) FROM Stock_Movements WHERE Product_id = ?", (pid,)).fetchone()[0]
        finally:
            conn.close()
    return batches, stock, moves


def test_purchase_movements_and_stock_equals_sum(app):
    pid, _ = _setup(app)
    batches, stock, moves = _state(app, pid)
    assert batches == {"A": 3, "B": 5, "EXP": 10}
    assert stock == sum(batches.values()) == 18
    assert moves == 3


def test_fefo_splits_across_batches_and_skips_expired(app):
    pid, ids = _setup(app)
    with app.app_context():
        with db_connection(immediate=True) as conn:
            alloc = ss.deduct_fefo(conn, pid, 6, "ORD_X", "tester")
    assert alloc == [{"batch_id": ids["A"], "batch_no": "A", "qty": 3},
                     {"batch_id": ids["B"], "batch_no": "B", "qty": 3}]
    batches, stock, moves = _state(app, pid)
    assert batches == {"A": 0, "B": 2, "EXP": 10}
    assert stock == 12 == sum(batches.values())
    assert moves == 5
    with app.app_context():
        conn = get_db()
        sale = conn.execute("SELECT SUM(change_qty) FROM Stock_Movements WHERE reason='SALE' AND reference_id='ORD_X'").fetchone()[0]
        conn.close()
    assert sale == -6


def test_oversell_raises_and_changes_nothing(app):
    pid, _ = _setup(app)
    before = _state(app, pid)
    with app.app_context():
        with pytest.raises(ss.OutOfStock):
            with db_connection(immediate=True) as conn:
                ss.deduct_fefo(conn, pid, 9, "ORD_Y", "tester")  # only 8 non-expired
        # Even if a caller swallows the error and commits, the savepoint undid everything
        with db_connection(immediate=True) as conn:
            with pytest.raises(ss.OutOfStock):
                ss.apply_stock_change(conn, pid, inv.fetch_batch_by_no(conn, pid, "A")["Batch_id"], -4,
                                      "ADJUSTMENT", "R", "tester")
    assert _state(app, pid) == before


def test_never_negative_and_validation(app):
    pid, ids = _setup(app)
    with app.app_context():
        with db_connection(immediate=True) as conn:
            with pytest.raises(ss.OutOfStock):
                ss.apply_stock_change(conn, pid, ids["B"], -6, "ADJUSTMENT", "R", "t")
            with pytest.raises(ss.ValidationError):
                ss.apply_stock_change(conn, pid, ids["B"], 1, "BOGUS", "R", "t")
            with pytest.raises(ss.NotFoundError):
                ss.apply_stock_change(conn, pid, "BAT_missing", 1, "ADJUSTMENT", "R", "t")
            moved = ss.apply_stock_change(conn, pid, ids["B"], -5, "ADJUSTMENT", "R", "t")
    assert moved["product_stock"] == 13
    assert _state(app, pid)[0]["B"] == 0


def test_restock_refuses_return_into_expired_batch(app):
    pid, ids = _setup(app)
    with app.app_context():
        with db_connection(immediate=True) as conn:
            with pytest.raises(ss.BatchExpired):
                ss.restock_to_batch(conn, ids["EXP"], 1, "RETURN", "ORD", "t")
            ss.restock_to_batch(conn, ids["A"], 2, "RETURN", "ORD", "t")
            ss.restock_to_batch(conn, ids["EXP"], 1, "CANCEL_RESTOCK", "ORD", "t")
    batches, stock, _ = _state(app, pid)
    assert batches == {"A": 5, "B": 5, "EXP": 11} and stock == 21
