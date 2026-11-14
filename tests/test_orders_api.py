import io
import json

import pytest

from app.db import db_connection, get_db
from app.services import stock_service
from app.utils.timeutil import utc_date_after, utc_today

PDF = b"%PDF-1.4\n" + b"0" * 64


# ------------------------------------------------------------------ fixtures / helpers
def _insert_user(app, user_id, approved=1, block=0, name=None):
    with app.app_context():
        with db_connection() as conn:
            conn.execute(
                """INSERT INTO Users(user_id, password, isApproved, block, name, email, phone_number, address, pin_code, role)
                   VALUES (?, 'x', ?, ?, ?, ?, '9999999999', 'Street 1', '400001', 'user')""",
                (user_id, approved, block, name or f"User {user_id}", f"{user_id.lower()}@example.com"),
            )


@pytest.fixture
def env(app, client, api, make_headers, admin_headers):
    _insert_user(app, "UID_A")
    _insert_user(app, "UID_B")
    return {
        "app": app, "client": client, "api": api, "admin": admin_headers,
        "a": make_headers("UID_A", "user"), "b": make_headers("UID_B", "user"),
    }


def _product(env, **over):
    body = {"name": "Paracetamol", "price": 112, "mrp": 120, "gst_percent": 12}
    body.update(over)
    res = env["client"].post(f"{env['api']}/products", json=body, headers=env["admin"])
    assert res.status_code == 201, res.get_json()
    return res.get_json()["data"]["product_id"]


def _purchase(env, pid, batch_no, qty, days):
    res = env["client"].post(f"{env['api']}/products/{pid}/stock/purchase", headers=env["admin"],
                             json={"batch_no": batch_no, "expiry_date": utc_date_after(days), "quantity": qty})
    assert res.status_code == 201, res.get_json()
    return res.get_json()["data"]["batch"]["batch_id"]


def _order(env, who, pid, qty=1, extra_headers=None, **body):
    payload = {"product_id": pid, "quantity": qty, **body}
    return env["client"].post(f"{env['api']}/orders", json=payload,
                              headers={**env[who], **(extra_headers or {})})


def _created(env, who, pid, qty=1, **body):
    res = _order(env, who, pid, qty, **body)
    assert res.status_code == 201, res.get_json()
    return res.get_json()["data"]["order_id"]


def _post(env, path, who="admin", json_body=None, extra_headers=None):
    return env["client"].post(f"{env['api']}{path}", json=json_body or {},
                              headers={**env[who], **(extra_headers or {})})


def _get(env, path, who="admin"):
    return env["client"].get(f"{env['api']}{path}", headers=env[who])


def _stock(env, pid):
    return _get(env, f"/products/{pid}").get_json()["data"]["stock"]


def _sales_rows(env, order_id):
    with env["app"].app_context():
        conn = get_db()
        n = conn.execute("SELECT COUNT(*) FROM Sell_History WHERE Order_id = ?", (order_id,)).fetchone()[0]
        conn.close()
    return n


# ------------------------------------------------------------------ create rules
def test_create_order_rules(env, app, make_headers):
    pid = _product(env)
    _purchase(env, pid, "B1", 5, 200)

    bad = _order(env, "a", pid, qty=0)
    assert bad.status_code == 400 and bad.get_json()["code"] == "VALIDATION_ERROR" and "quantity" in bad.get_json()["fields"]
    assert _order(env, "a", pid, qty="x").status_code == 400
    assert _order(env, "a", "PROD_missing").status_code == 404

    oos = _order(env, "a", pid, qty=6)
    assert oos.status_code == 409 and oos.get_json()["code"] == "OUT_OF_STOCK"

    res = _order(env, "a", pid, qty=2, user_id="UID_B", message="evening dose")
    assert res.status_code == 201
    order = res.get_json()["data"]
    assert order["user_id"] == "UID_A" and order["status"] == "pending" and order["total_amount"] == 224.0
    assert res.headers["Location"].endswith(f"{env['api']}/orders/{order['order_id']}")
    assert order["created_at"].endswith("Z") and order["prescription_url"] is None
    assert _stock(env, pid) == 5  # not deducted until sale

    inactive = _product(env, name="Old")
    _purchase(env, inactive, "X", 5, 200)
    assert _post(env, f"/products/{inactive}/deactivate").status_code == 200
    gone = _order(env, "a", inactive)
    assert gone.status_code == 409 and gone.get_json()["code"] == "CONFLICT"

    _insert_user(app, "UID_BLOCKED", block=1)
    _insert_user(app, "UID_NEW", approved=0)
    env["blocked"] = make_headers("UID_BLOCKED", "user")
    env["new"] = make_headers("UID_NEW", "user")
    assert _order(env, "blocked", pid).get_json()["code"] == "ACCOUNT_BLOCKED"
    unapproved = _order(env, "new", pid)
    assert unapproved.status_code == 403 and unapproved.get_json()["code"] == "ACCOUNT_NOT_APPROVED"
    assert _order(env, "admin", pid).status_code == 403


def test_prescription_required_on_create_and_sell(env):
    pid = _product(env, name="Azithromycin", schedule_type="H")
    _purchase(env, pid, "B1", 10, 200)
    missing = _order(env, "a", pid)
    assert missing.status_code == 400 and missing.get_json()["code"] == "PRESCRIPTION_REQUIRED"
    assert {"prescription_url", "doctor_name"} <= set(missing.get_json()["fields"])
    oid = _created(env, "a", pid, prescription_url="https://cdn.test/rx.pdf", doctor_name="Dr. Rao")
    assert _post(env, f"/orders/{oid}/approve").status_code == 200
    not_verified = _post(env, f"/orders/{oid}/sell")
    assert not_verified.status_code == 409 and not_verified.get_json()["code"] == "PRESCRIPTION_NOT_VERIFIED"
    assert _post(env, f"/orders/{oid}/verify-prescription", json_body={"verified": True}).status_code == 200
    sold = _post(env, f"/orders/{oid}/sell")
    assert sold.status_code == 200 and sold.get_json()["data"]["status"] == "sold"


def test_prescription_upload_validation(env, app, monkeypatch):
    import cloudinary.uploader
    calls = []

    def fake_upload(file, **kw):
        calls.append(kw)
        return {"secure_url": f"https://cdn.test/{kw['folder']}/abc123"}

    monkeypatch.setattr(cloudinary.uploader, "upload", fake_upload)
    pid = _product(env)
    _purchase(env, pid, "B1", 10, 200)
    oid = _created(env, "a", pid)
    url = f"{env['api']}/orders/{oid}/prescription"

    ok = env["client"].post(url, headers=env["a"], content_type="multipart/form-data",
                            data={"prescription": (io.BytesIO(PDF), "../../etc/passwd.pdf", "application/pdf"),
                                  "doctor_name": "Dr. Iyer"})
    data = ok.get_json()["data"]
    assert ok.status_code == 200 and data["prescription_url"].endswith("/abc123")
    assert data["doctor_name"] == "Dr. Iyer" and data["prescription_verified"] is False
    assert "public_id" not in calls[0] and "passwd" not in data["prescription_url"]

    wrong = env["client"].post(url, headers=env["a"], content_type="multipart/form-data",
                               data={"prescription": (io.BytesIO(b"hello"), "rx.txt", "text/plain")})
    assert wrong.status_code == 415 and wrong.get_json()["code"] == "UNSUPPORTED_MEDIA_TYPE"
    app.config["MAX_UPLOAD_MB"] = 1
    big = env["client"].post(url, headers=env["a"], content_type="multipart/form-data",
                             data={"prescription": (io.BytesIO(PDF + b"0" * (1024 * 1024 + 10)), "rx.pdf",
                                                    "application/pdf")})
    assert big.status_code == 413 and big.get_json()["code"] == "PAYLOAD_TOO_LARGE"
    as_json = env["client"].post(url, headers=env["a"], json={"prescription_url": "x"})
    assert as_json.status_code == 415
    missing = env["client"].post(url, headers=env["a"], content_type="multipart/form-data", data={"doctor_name": "x"})
    assert missing.status_code == 400
    assert env["client"].post(url, headers=env["b"], content_type="multipart/form-data",
                              data={"prescription": (io.BytesIO(PDF), "rx.pdf", "application/pdf")}).status_code == 404


# ------------------------------------------------------------------ lifecycle
def test_full_lifecycle_fefo_invoice_and_return(env, app):
    pid = _product(env)
    b_soon = _purchase(env, pid, "SOON", 3, 30)
    b_late = _purchase(env, pid, "LATE", 5, 300)
    oid = _created(env, "a", pid, qty=5)

    assert _post(env, f"/orders/{oid}/sell").get_json()["code"] == "INVALID_TRANSITION"  # still pending
    pending_invoice = _get(env, f"/orders/{oid}/invoice", who="a")
    assert pending_invoice.status_code == 409 and pending_invoice.get_json()["code"] == "INVALID_TRANSITION"

    approved = _post(env, f"/orders/{oid}/approve")
    assert approved.get_json()["data"]["status"] == "approved"
    assert _post(env, f"/orders/{oid}/approve").get_json()["code"] == "INVALID_TRANSITION"

    sold = _post(env, f"/orders/{oid}/sell").get_json()["data"]
    assert sold["status"] == "sold"
    lines = sorted((s["batch_no"], s["quantity"]) for s in sold["sales"])
    assert lines == [("LATE", 2), ("SOON", 3)]
    assert all(s["sold_by"] == "AID_test_admin" and s["gst_percent"] == 12.0 for s in sold["sales"])
    assert _stock(env, pid) == 3

    again = _post(env, f"/orders/{oid}/sell")
    assert again.status_code == 409 and again.get_json()["code"] == "ALREADY_SOLD"
    assert _stock(env, pid) == 3
    assert _post(env, f"/orders/{oid}/cancel").get_json()["code"] == "INVALID_TRANSITION"

    inv = _get(env, f"/orders/{oid}/invoice", who="a").get_json()["data"]
    assert inv["grand_total"] == 560.0 and inv["subtotal"] == 500.0 and inv["gst_total"] == 60.0
    assert len(inv["items"]) == 2 and inv["items"][0]["expiry_date"] and inv["items"][0]["unit_price"] == 112.0
    assert inv["user"]["user_id"] == "UID_A" and "password" not in inv["user"]
    assert inv["issued_at"].endswith("Z") and inv["generated_at"].endswith("Z")

    ret = _post(env, f"/orders/{oid}/return", json_body={"reason": "wrong item"})
    body = ret.get_json()["data"]
    assert ret.status_code == 200 and body["status"] == "returned" and body["not_restocked"] == []
    assert sorted(r["qty"] for r in body["restocked"]) == [2, 3]
    assert _stock(env, pid) == 8
    assert _post(env, f"/orders/{oid}/return").get_json()["code"] == "INVALID_TRANSITION"

    actions = [a["action"] for a in _get(env, f"/audit-logs?entity=order&entity_id={oid}&order=asc").get_json()["data"]]
    assert actions == ["order.create", "order.approve", "order.sell", "order.return"]
    with app.app_context():
        conn = get_db()
        reasons = [r[0] for r in conn.execute(
            "SELECT reason FROM Stock_Movements WHERE reference_id = ? ORDER BY rowid", (oid,))]
        conn.close()
    assert reasons.count("SALE") == 2 and reasons.count("RETURN") == 2
    assert {b_soon, b_late}


def test_oversell_at_sale_rolls_back(env):
    pid = _product(env)
    bid = _purchase(env, pid, "B1", 5, 200)
    oid = _created(env, "a", pid, qty=5)
    _post(env, f"/orders/{oid}/approve")
    adj = _post(env, f"/products/{pid}/stock/adjust",
                json_body={"batch_id": bid, "change_qty": -3, "reason": "breakage"})
    assert adj.status_code == 200
    res = _post(env, f"/orders/{oid}/sell")
    assert res.status_code == 409 and res.get_json()["code"] == "OUT_OF_STOCK"
    assert _stock(env, pid) == 2 and _sales_rows(env, oid) == 0
    assert _get(env, f"/orders/{oid}").get_json()["data"]["status"] == "approved"


def test_return_skips_expired_batch(env):
    pid = _product(env)
    bid = _purchase(env, pid, "B1", 4, 200)
    oid = _created(env, "a", pid, qty=2)
    _post(env, f"/orders/{oid}/approve")
    assert _post(env, f"/orders/{oid}/sell").status_code == 200
    assert env["client"].patch(f"{env['api']}/batches/{bid}", headers=env["admin"],
                               json={"expiry_date": utc_date_after(-1)}).status_code == 200
    body = _post(env, f"/orders/{oid}/return").get_json()["data"]
    assert body["status"] == "returned" and body["restocked"] == []
    assert body["not_restocked"] == [{"batch_id": bid, "batch_no": "B1", "qty": 2, "reason": "BATCH_EXPIRED"}]
    assert _stock(env, pid) == 2


def test_idempotent_create_and_sell(env):
    pid = _product(env)
    _purchase(env, pid, "B1", 10, 200)
    key = {"Idempotency-Key": "order-1"}
    first = _order(env, "a", pid, qty=3, extra_headers=key)
    replay = _order(env, "a", pid, qty=3, extra_headers=key)
    assert first.status_code == replay.status_code == 201
    assert replay.headers["Idempotent-Replayed"] == "true"
    assert json.loads(replay.data) == json.loads(first.data)
    assert _get(env, "/orders", who="a").get_json()["pagination"]["total"] == 1

    oid = first.get_json()["data"]["order_id"]
    _post(env, f"/orders/{oid}/approve")
    s1 = _post(env, f"/orders/{oid}/sell", extra_headers={"Idempotency-Key": "sell-1"})
    s2 = _post(env, f"/orders/{oid}/sell", extra_headers={"Idempotency-Key": "sell-1"})
    assert s1.status_code == s2.status_code == 200 and s2.headers["Idempotent-Replayed"] == "true"
    assert _stock(env, pid) == 7 and _sales_rows(env, oid) == 1


def test_cancel_rules_and_restock_only_when_deducted(env, app):
    pid = _product(env)
    _purchase(env, pid, "B1", 10, 200)

    o1 = _created(env, "a", pid, qty=2)
    res = _post(env, f"/orders/{o1}/cancel", who="a", json_body={"cancel_reason": "changed my mind"})
    data = res.get_json()["data"]
    assert res.status_code == 200 and data["status"] == "cancelled" and data["cancel_reason"] == "changed my mind"
    assert data["restocked"] == [] and _stock(env, pid) == 10
    assert _post(env, f"/orders/{o1}/cancel", who="a").get_json()["code"] == "INVALID_TRANSITION"

    o2 = _created(env, "a", pid, qty=2)
    _post(env, f"/orders/{o2}/approve")
    user_cancel = _post(env, f"/orders/{o2}/cancel", who="a")
    assert user_cancel.status_code == 409 and user_cancel.get_json()["code"] == "INVALID_TRANSITION"
    # Simulate stock already deducted against this approved order
    with app.app_context():
        with db_connection(immediate=True) as conn:
            stock_service.deduct_fefo(conn, pid, 2, o2, "AID_test_admin")
    assert _stock(env, pid) == 8
    admin_cancel = _post(env, f"/orders/{o2}/cancel", json_body={"cancel_reason": "pharmacy closed"})
    assert admin_cancel.status_code == 200 and admin_cancel.get_json()["data"]["restocked"][0]["qty"] == 2
    assert _stock(env, pid) == 10

    o3 = _created(env, "a", pid)
    rej = _post(env, f"/orders/{o3}/reject", json_body={"reason": "duplicate"})
    assert rej.get_json()["data"]["status"] == "cancelled" and "duplicate" in rej.get_json()["data"]["cancel_reason"]


def test_patch_order_whitelist(env):
    pid = _product(env)
    _purchase(env, pid, "B1", 10, 200)
    oid = _created(env, "a", pid)
    url = f"{env['api']}/orders/{oid}"
    ok = env["client"].patch(url, headers=env["a"], json={"patient_name": "Ravi"})
    assert ok.status_code == 200 and ok.get_json()["data"]["patient_name"] == "Ravi"
    bad = env["client"].patch(url, headers=env["a"], json={"total_amount": 1, "quantity": 9})
    assert bad.status_code == 400 and {"total_amount", "quantity"} <= set(bad.get_json()["fields"])
    assert env["client"].patch(url, headers=env["b"], json={"patient_name": "x"}).status_code == 404
    _post(env, f"/orders/{oid}/approve")
    late = env["client"].patch(url, headers=env["a"], json={"doctor_name": "Dr. X"})
    assert late.status_code == 409 and late.get_json()["code"] == "INVALID_TRANSITION"


def test_ownership_returns_404(env):
    pid = _product(env)
    _purchase(env, pid, "B1", 10, 200)
    oa = _created(env, "a", pid)
    ob = _created(env, "b", pid)
    _post(env, f"/orders/{oa}/approve")
    _post(env, f"/orders/{oa}/sell")

    assert _get(env, f"/orders/{oa}", who="b").status_code == 404
    assert _get(env, f"/orders/{oa}/invoice", who="b").status_code == 404
    assert _get(env, f"/orders/{oa}/invoice", who="a").status_code == 200
    assert _post(env, f"/orders/{ob}/cancel", who="a").status_code == 404
    assert _get(env, "/users/UID_A/orders", who="b").status_code == 404
    mine = _get(env, "/users/UID_B/orders", who="b").get_json()
    assert [o["order_id"] for o in mine["data"]] == [ob]
    own_list = _get(env, "/orders?user_id=UID_A", who="b").get_json()
    assert [o["order_id"] for o in own_list["data"]] == [ob]  # user filter ignored for users
    assert _get(env, "/orders", who="admin").get_json()["pagination"]["total"] == 2
    assert _get(env, "/users/UID_A/orders?status=sold", who="admin").get_json()["pagination"]["total"] == 1


def test_order_and_sales_filters(env):
    p1 = _product(env, name="Alpha")
    p2 = _product(env, name="Beta")
    _purchase(env, p1, "B1", 20, 200)
    _purchase(env, p2, "B2", 20, 200)
    for who, pid in (("a", p1), ("a", p2), ("b", p1)):
        oid = _created(env, who, pid, qty=2)
        _post(env, f"/orders/{oid}/approve")
        _post(env, f"/orders/{oid}/sell")
    _created(env, "a", p1)  # pending

    assert _get(env, "/orders?status=pending").get_json()["pagination"]["total"] == 1
    assert _get(env, f"/orders?product_id={p1}").get_json()["pagination"]["total"] == 3
    assert _get(env, "/orders?updated_since=2999-01-01T00:00:00Z").get_json()["data"] == []
    assert _get(env, "/orders?status=bogus").status_code == 400

    sales = _get(env, "/sales").get_json()
    assert sales["pagination"]["total"] == 3 and sales["data"][0]["sold_at"].endswith("Z")
    assert _get(env, f"/sales?product_id={p1}").get_json()["pagination"]["total"] == 2
    assert _get(env, "/sales?user_id=UID_B").get_json()["pagination"]["total"] == 1
    today = utc_today()
    assert _get(env, f"/sales?from={today}&to={today}").get_json()["pagination"]["total"] == 3
    assert _get(env, "/sales?to=2000-01-01").get_json()["pagination"]["total"] == 0
    page = _get(env, "/sales?limit=2&offset=2").get_json()
    assert len(page["data"]) == 1 and page["pagination"] == {"limit": 2, "offset": 2, "total": 3}
    assert _get(env, "/sales?from=nope").status_code == 400


# ------------------------------------------------------------------ suppliers
def test_suppliers_crud(env, app):
    good = {"name": "Apex Pharma", "contact_phone": "+919876543210", "email": "sales@apex.test",
            "gst_number": "27abcde1234f1z5", "address": "Pune"}
    res = _post(env, "/suppliers", json_body=good)
    assert res.status_code == 201
    sup = res.get_json()["data"]
    assert sup["gst_number"] == "27ABCDE1234F1Z5" and sup["is_active"] is True
    assert res.headers["Location"].endswith(f"{env['api']}/suppliers/{sup['supplier_id']}")

    bad = _post(env, "/suppliers", json_body={"email": "nope", "gst_number": "123", "contact_phone": "abc"})
    assert bad.status_code == 400 and {"name", "email", "gst_number", "contact_phone"} <= set(bad.get_json()["fields"])
    dup = _post(env, "/suppliers", json_body={**good, "name": "Other"})
    assert dup.status_code == 409 and dup.get_json()["code"] == "CONFLICT"

    sid = sup["supplier_id"]
    patched = env["client"].patch(f"{env['api']}/suppliers/{sid}", headers=env["admin"], json={"address": "Mumbai"})
    assert patched.status_code == 200 and patched.get_json()["data"]["address"] == "Mumbai"
    assert env["client"].patch(f"{env['api']}/suppliers/{sid}", headers=env["admin"], json={}).status_code == 400
    assert _get(env, f"/suppliers/{sid}").get_json()["data"]["name"] == "Apex Pharma"
    assert _get(env, "/suppliers/SUP_missing").status_code == 404
    assert _get(env, "/suppliers?q=apex").get_json()["pagination"]["total"] == 1

    assert _post(env, f"/suppliers/{sid}/deactivate").get_json()["data"]["is_active"] is False
    assert _post(env, f"/suppliers/{sid}/deactivate").status_code == 409
    assert _get(env, "/suppliers?is_active=true").get_json()["pagination"]["total"] == 0
    assert _get(env, f"/suppliers/{sid}").status_code == 200  # soft-deleted, still readable
    actions = {a["action"] for a in _get(env, f"/audit-logs?entity=supplier&entity_id={sid}").get_json()["data"]}
    assert actions == {"supplier.create", "supplier.update", "supplier.deactivate"}


# ------------------------------------------------------------------ dashboard & reports
def test_dashboard_and_reports(env):
    p1 = _product(env, name="Alpha", reorder_level=50)
    p2 = _product(env, name="Beta", reorder_level=1)
    _purchase(env, p1, "A1", 10, 30)
    _purchase(env, p2, "B1", 10, 400)
    for pid, qty in ((p1, 3), (p2, 1), (p1, 2)):
        oid = _created(env, "a", pid, qty=qty)
        _post(env, f"/orders/{oid}/approve")
        _post(env, f"/orders/{oid}/sell")
    _created(env, "b", p2)  # pending

    summary = _get(env, "/dashboard/summary").get_json()["data"]
    assert summary["products"] == 2 and summary["pending_orders"] == 1 and summary["low_stock"] == 1
    assert summary["near_expiry_batches"] == 1 and summary["expired_batches"] == 0
    assert summary["today_sales_total"] == 112.0 * 6 and summary["today_sales_count"] == 3

    by_day = _get(env, "/reports/sales?group_by=day").get_json()
    assert by_day["data"] == [{"day": utc_today(), "quantity": 6, "revenue": 672.0, "orders": 3}]
    assert by_day["summary"]["revenue"] == 672.0 and by_day["pagination"]["total"] == 1
    by_product = _get(env, "/reports/sales?group_by=product&sort=revenue&order=desc").get_json()["data"]
    assert [(r["product_id"], r["quantity"]) for r in by_product] == [(p1, 5), (p2, 1)]
    top = _get(env, "/reports/top-products").get_json()["data"]
    assert top[0]["product_id"] == p1 and top[0]["revenue"] == 560.0
    assert _get(env, "/reports/sales?group_by=week").status_code == 400
    assert _get(env, "/reports/sales?from=2025-02-01&to=2025-01-01").status_code == 400
    assert _get(env, "/reports/top-products?from=1999-01-01&to=2000-01-01").get_json()["data"] == []


def test_audit_log_filters(env):
    _post(env, "/suppliers", json_body={"name": "S1"})
    logs = _get(env, "/audit-logs?actor_id=AID_test_admin&action=supplier.create").get_json()
    assert logs["pagination"]["total"] == 1 and logs["data"][0]["created_at"].endswith("Z")
    assert isinstance(logs["data"][0]["details"], dict)
    assert _get(env, "/audit-logs?from=2999-01-01").get_json()["data"] == []
    assert _get(env, "/audit-logs?from=bad").status_code == 400


def test_legacy_urls_removed(client, admin_headers):
    for method, url in (("POST", "/user/createOrder"), ("GET", "/admin/getAllOrders"),
                        ("POST", "/admin/recordSell"), ("GET", "/admin/getSellHistory"),
                        ("PATCH", "/admin/updateOrder"), ("POST", "/admin/deleteOrder")):
        assert client.open(url, method=method, headers=admin_headers).status_code == 404


# ------------------------------------------------------------------ auth matrix
ENDPOINTS = [
    # (method, path, allowed roles)
    ("GET", "/orders", {"admin", "user"}),
    ("POST", "/orders", {"user"}),
    ("GET", "/orders/O1", {"admin", "user"}),
    ("PATCH", "/orders/O1", {"admin", "user"}),
    ("GET", "/users/U1/orders", {"admin", "user"}),
    ("POST", "/orders/O1/cancel", {"admin", "user"}),
    ("POST", "/orders/O1/approve", {"admin"}),
    ("POST", "/orders/O1/reject", {"admin"}),
    ("POST", "/orders/O1/verify-prescription", {"admin"}),
    ("POST", "/orders/O1/return", {"admin"}),
    ("POST", "/orders/O1/sell", {"admin"}),
    ("GET", "/orders/O1/invoice", {"admin", "user"}),
    ("POST", "/orders/O1/prescription", {"admin", "user"}),
    ("GET", "/sales", {"admin"}),
    ("GET", "/suppliers", {"admin"}),
    ("POST", "/suppliers", {"admin"}),
    ("GET", "/suppliers/S1", {"admin"}),
    ("PATCH", "/suppliers/S1", {"admin"}),
    ("POST", "/suppliers/S1/deactivate", {"admin"}),
    ("GET", "/dashboard/summary", {"admin"}),
    ("GET", "/reports/sales", {"admin"}),
    ("GET", "/reports/top-products", {"admin"}),
    ("GET", "/audit-logs", {"admin"}),
]


@pytest.mark.parametrize("method,path,roles", ENDPOINTS)
def test_part2_auth_matrix(client, api, admin_headers, user_headers, method, path, roles):
    res = client.open(f"{api}{path}", method=method, json={})
    assert res.status_code == 401 and res.get_json()["code"] == "UNAUTHORIZED"
    for role, headers in (("admin", admin_headers), ("user", user_headers)):
        if role not in roles:
            res = client.open(f"{api}{path}", method=method, json={}, headers=headers)
            assert res.status_code == 403 and res.get_json()["code"] == "FORBIDDEN"
