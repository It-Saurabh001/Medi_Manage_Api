from app.db import get_db

from tests.test_orders_api import _created, _get, _insert_user, _post, _product, _purchase, _stock


import pytest


@pytest.fixture
def env(app, client, api, make_headers, admin_headers):
    _insert_user(app, "UID_A")
    _insert_user(app, "UID_B")
    return {
        "app": app, "client": client, "api": api, "admin": admin_headers,
        "a": make_headers("UID_A", "user"), "b": make_headers("UID_B", "user"),
    }


def _checkout(env, who, items, extra_headers=None, **body):
    return env["client"].post(f"{env['api']}/checkouts", json={"items": items, **body},
                              headers={**env[who], **(extra_headers or {})})


def _order_count(env):
    with env["app"].app_context():
        conn = get_db()
        n = conn.execute("SELECT COUNT(*) FROM Order_Details").fetchone()[0]
        conn.close()
    return n


def _two_products(env):
    p1 = _product(env, name="Paracetamol", price=30, mrp=32)
    p2 = _product(env, name="Cetirizine", price=20, mrp=22)
    _purchase(env, p1, "B1", 10, 200)
    _purchase(env, p2, "B2", 5, 200)
    return p1, p2


def test_checkout_creates_grouped_orders(env):
    p1, p2 = _two_products(env)
    res = _checkout(env, "a", [{"product_id": p1, "quantity": 2}, {"product_id": p2, "quantity": 1}], message="evening")
    assert res.status_code == 201, res.get_json()
    data = res.get_json()["data"]
    cid = data["checkout_id"]
    assert cid.startswith("CHK_") and len(data["orders"]) == 2
    assert all(o["checkout_id"] == cid and o["status"] == "pending" for o in data["orders"])
    assert res.headers["Location"].endswith(f"checkout_id={cid}")
    listed = _get(env, f"/orders?checkout_id={cid}", who="a").get_json()
    assert listed["pagination"]["total"] == 2
    single = _created(env, "a", p1)
    assert _get(env, f"/orders/{single}", who="a").get_json()["data"]["checkout_id"] is None


def test_checkout_out_of_stock_rolls_back_everything(env):
    p1, p2 = _two_products(env)
    before_orders, before_stock = _order_count(env), (_stock(env, p1), _stock(env, p2))
    res = _checkout(env, "a", [{"product_id": p1, "quantity": 1}, {"product_id": p2, "quantity": 6}])
    body = res.get_json()
    assert res.status_code == 409 and body["code"] == "OUT_OF_STOCK"
    assert body["fields"] == {"items[1].quantity": "available: 5"} and p2 in body["message"]
    assert _order_count(env) == before_orders
    assert (_stock(env, p1), _stock(env, p2)) == before_stock


def test_checkout_validation(env):
    p1, _ = _two_products(env)
    assert _checkout(env, "a", []).get_json()["code"] == "VALIDATION_ERROR"
    bad = _checkout(env, "a", [{"product_id": p1, "quantity": 0}]).get_json()
    assert bad["code"] == "VALIDATION_ERROR" and "items[0].quantity" in bad["fields"]
    rx = _product(env, name="Azithromycin", schedule_type="H")
    _purchase(env, rx, "B3", 5, 200)
    need = _checkout(env, "a", [{"product_id": p1, "quantity": 1}, {"product_id": rx, "quantity": 1}]).get_json()
    assert need["code"] == "PRESCRIPTION_REQUIRED" and "items[1].doctor_name" in need["fields"]
    ok = _checkout(env, "a", [{"product_id": rx, "quantity": 1, "doctor_name": "Dr. Rao"}])
    assert ok.status_code == 201
    assert _checkout(env, "admin", [{"product_id": p1, "quantity": 1}]).status_code == 403


def test_checkout_idempotent_replay(env):
    p1, p2 = _two_products(env)
    items = [{"product_id": p1, "quantity": 1}, {"product_id": p2, "quantity": 1}]
    key = {"Idempotency-Key": "chk-key-1"}
    first = _checkout(env, "a", items, extra_headers=key)
    again = _checkout(env, "a", items, extra_headers=key)
    assert first.status_code == 201 and again.status_code == 201
    assert again.headers.get("Idempotent-Replayed") == "true"
    assert again.get_json()["data"]["checkout_id"] == first.get_json()["data"]["checkout_id"]
    assert _order_count(env) == 2


def _sell(env, order_id):
    assert _post(env, f"/orders/{order_id}/approve").status_code == 200
    assert _post(env, f"/orders/{order_id}/sell").status_code == 200


def test_checkout_invoice_totals_and_partial(env):
    p1, p2 = _two_products(env)
    data = _checkout(env, "a", [{"product_id": p1, "quantity": 2}, {"product_id": p2, "quantity": 1}]).get_json()["data"]
    cid, (o1, o2) = data["checkout_id"], [o["order_id"] for o in data["orders"]]
    not_yet = _get(env, f"/checkouts/{cid}/invoice", who="a")
    assert not_yet.status_code == 409 and not_yet.get_json()["code"] == "INVALID_TRANSITION"

    _sell(env, o1)
    partial = _get(env, f"/checkouts/{cid}/invoice", who="a").get_json()["data"]
    assert [o["order_id"] for o in partial["orders"]] == [o1]
    assert partial["grand_total"] == 60.0 and partial["invoice_number"] == f"INV-{cid}"

    _sell(env, o2)
    full = _get(env, f"/checkouts/{cid}/invoice", who="a").get_json()["data"]
    single = [_get(env, f"/orders/{o}/invoice", who="a").get_json()["data"] for o in (o1, o2)]
    assert full["checkout_id"] == cid and len(full["orders"]) == 2
    assert full["grand_total"] == round(sum(s["grand_total"] for s in single), 2) == 80.0
    assert full["subtotal"] == round(sum(s["subtotal"] for s in single), 2)
    assert full["gst_total"] == round(sum(s["gst_total"] for s in single), 2)
    assert len(full["items"]) == sum(len(s["items"]) for s in single)
    assert _get(env, f"/checkouts/{cid}/invoice", who="admin").status_code == 200


def test_checkout_invoice_other_user_404(env):
    p1, _ = _two_products(env)
    cid = _checkout(env, "a", [{"product_id": p1, "quantity": 1}]).get_json()["data"]["checkout_id"]
    assert _get(env, f"/checkouts/{cid}/invoice", who="b").status_code == 404
    assert _get(env, "/checkouts/CHK_missing/invoice", who="a").status_code == 404
