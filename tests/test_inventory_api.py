import io
import json

import pytest

from app.db import get_db
from app.utils.timeutil import utc_date_after

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def _product(client, api, headers, **over):
    body = {"name": "Paracetamol 500", "price": 20, "mrp": 25, "category": "Pain", "gst_percent": 12}
    body.update(over)
    res = client.post(f"{api}/products", json=body, headers=headers)
    assert res.status_code == 201, res.get_json()
    return res.get_json()["data"]


def _purchase(client, api, headers, pid, batch_no="B1", qty=10, days=400, extra_headers=None):
    hdrs = dict(headers, **(extra_headers or {}))
    return client.post(f"{api}/products/{pid}/stock/purchase", headers=hdrs,
                       json={"batch_no": batch_no, "expiry_date": utc_date_after(days), "quantity": qty})


def _audit_actions(app, entity_id):
    with app.app_context():
        conn = get_db()
        rows = [r["action"] for r in conn.execute("SELECT action FROM Audit_Log WHERE entity_id = ?", (entity_id,))]
        conn.close()
    return rows


# ------------------------------------------------------------------ products
def test_create_product_validation_errors(client, api, admin_headers):
    res = client.post(f"{api}/products", headers=admin_headers,
                      json={"gst_percent": 30, "dosage_form": "powder", "stock": 5, "hsn_code": "12ab"})
    body = res.get_json()
    assert res.status_code == 400 and body["code"] == "VALIDATION_ERROR"
    assert {"name", "price", "gst_percent", "dosage_form", "stock", "hsn_code"} <= set(body["fields"])


def test_create_product_contract_location_and_rx_forcing(app, client, api, admin_headers, user_headers):
    res = client.post(f"{api}/products", headers=admin_headers, json={
        "name": "Alprazolam", "price": 40, "mrp": 50, "schedule_type": "h1",
        "requires_prescription": False, "purchase_price": 30, "barcode": "8901"})
    assert res.status_code == 201
    data = res.get_json()["data"]
    assert res.headers["Location"].endswith(f"{api}/products/{data['product_id']}")
    assert data["schedule_type"] == "H1" and data["requires_prescription"] is True
    assert data["stock"] == 0 and data["in_stock"] is False and data["is_active"] is True
    assert data["created_at"].endswith("Z") and data["purchase_price"] == 30.0
    assert data["image_url"] is None and "generic_name" in data
    as_user = client.get(f"{api}/products/{data['product_id']}", headers=user_headers).get_json()["data"]
    assert as_user["purchase_price"] is None
    assert "product.create" in _audit_actions(app, data["product_id"])


def test_product_conflicts_and_cross_field_rules(client, api, admin_headers):
    _product(client, api, admin_headers, barcode="111")
    dup = client.post(f"{api}/products", headers=admin_headers, json={"name": "X", "price": 1, "barcode": "111"})
    assert dup.status_code == 409 and dup.get_json()["code"] == "CONFLICT"
    bad = client.post(f"{api}/products", headers=admin_headers, json={"name": "X", "price": 30, "mrp": 20})
    assert bad.status_code == 400 and "price" in bad.get_json()["fields"]


def test_list_filters_pagination_and_visibility(client, api, admin_headers, user_headers):
    a = _product(client, api, admin_headers, name="Ibuprofen", category="Pain", generic_name="ibuprofen")
    b = _product(client, api, admin_headers, name="Azithral", category="Antibiotic", schedule_type="H")
    c = _product(client, api, admin_headers, name="Old Syrup", category="Cough")
    assert client.post(f"{api}/products/{c['product_id']}/deactivate", headers=admin_headers).status_code == 200

    users = client.get(f"{api}/products", headers=user_headers).get_json()
    assert users["pagination"] == {"limit": 20, "offset": 0, "total": 2}
    assert c["product_id"] not in [p["product_id"] for p in users["data"]]

    admins = client.get(f"{api}/products?is_active=false", headers=admin_headers).get_json()
    assert [p["product_id"] for p in admins["data"]] == [c["product_id"]]

    page = client.get(f"{api}/products?limit=1&offset=1&sort=name&order=asc", headers=user_headers).get_json()
    assert len(page["data"]) == 1 and page["data"][0]["product_id"] == a["product_id"]
    assert page["pagination"]["total"] == 2

    q = client.get(f"{api}/products?q=IBUPRO", headers=user_headers).get_json()["data"]
    assert [p["product_id"] for p in q] == [a["product_id"]]
    rx = client.get(f"{api}/products?requires_prescription=true", headers=user_headers).get_json()["data"]
    assert [p["product_id"] for p in rx] == [b["product_id"]]
    cat = client.get(f"{api}/products?category=antibiotic", headers=user_headers).get_json()["data"]
    assert [p["product_id"] for p in cat] == [b["product_id"]]
    future = client.get(f"{api}/products?updated_since=2999-01-01T00:00:00Z", headers=user_headers).get_json()
    assert future["data"] == [] and future["pagination"]["total"] == 0

    bad = client.get(f"{api}/products?sort=password&in_stock=maybe", headers=user_headers)
    assert bad.status_code == 400 and set(bad.get_json()["fields"]) >= {"in_stock"}
    bad_sort = client.get(f"{api}/products?sort=password", headers=user_headers)
    assert bad_sort.status_code == 400 and "sort" in bad_sort.get_json()["fields"]

    # trailing slash tolerated
    assert client.get(f"{api}/products/", headers=user_headers).status_code == 200


def test_barcode_lookup_and_deactivate_cycle(client, api, admin_headers, user_headers):
    p = _product(client, api, admin_headers, barcode="890123")
    assert client.get(f"{api}/products/by-barcode/890123", headers=user_headers).get_json()["data"]["product_id"] == p["product_id"]
    assert client.get(f"{api}/products/by-barcode/000", headers=user_headers).status_code == 404

    pid = p["product_id"]
    assert client.post(f"{api}/products/{pid}/deactivate", headers=admin_headers).status_code == 200
    again = client.post(f"{api}/products/{pid}/deactivate", headers=admin_headers)
    assert again.status_code == 409 and again.get_json()["code"] == "CONFLICT"
    assert client.get(f"{api}/products/{pid}", headers=user_headers).status_code == 404
    assert client.get(f"{api}/products/by-barcode/890123", headers=user_headers).status_code == 404
    assert client.get(f"{api}/products/{pid}", headers=admin_headers).get_json()["data"]["is_active"] is False
    assert client.post(f"{api}/products/{pid}/reactivate", headers=admin_headers).status_code == 200
    assert client.get(f"{api}/products/{pid}", headers=user_headers).status_code == 200


def test_patch_product(client, api, admin_headers):
    pid = _product(client, api, admin_headers)["product_id"]
    res = client.patch(f"{api}/products/{pid}", headers=admin_headers, json={"price": 22.5, "schedule_type": "X"})
    data = res.get_json()["data"]
    assert res.status_code == 200 and data["price"] == 22.5 and data["requires_prescription"] is True
    assert client.patch(f"{api}/products/{pid}", headers=admin_headers, json={}).status_code == 400
    stock = client.patch(f"{api}/products/{pid}", headers=admin_headers, json={"stock": 5})
    assert stock.status_code == 400 and "stock" in stock.get_json()["fields"]
    assert client.patch(f"{api}/products/NOPE", headers=admin_headers, json={"price": 1}).status_code == 404


def test_product_image_upload(client, api, admin_headers, monkeypatch):
    import cloudinary.uploader
    monkeypatch.setattr(cloudinary.uploader, "upload",
                        lambda file, **kw: {"secure_url": f"https://cdn.test/{kw['folder']}/{file.filename}"})
    ok = client.post(f"{api}/products", headers=admin_headers, content_type="multipart/form-data",
                     data={"name": "Img", "price": "5", "image": (io.BytesIO(PNG), "p.png", "image/png")})
    assert ok.status_code == 201 and ok.get_json()["data"]["image_url"].endswith("/p.png")
    wrong = client.post(f"{api}/products", headers=admin_headers, content_type="multipart/form-data",
                        data={"name": "Img", "price": "5", "image": (io.BytesIO(b"hello"), "p.txt", "text/plain")})
    assert wrong.status_code == 415 and wrong.get_json()["code"] == "UNSUPPORTED_MEDIA_TYPE"
    fake = client.post(f"{api}/products", headers=admin_headers, content_type="multipart/form-data",
                       data={"name": "Img", "price": "5", "image": (io.BytesIO(b"notapng!" * 4), "p.png", "image/png")})
    assert fake.status_code == 415


def test_categories(client, api, admin_headers, user_headers):
    _product(client, api, admin_headers, category="Pain")
    _product(client, api, admin_headers, name="B", category="Pain")
    _product(client, api, admin_headers, name="C", category="Skin")
    res = client.get(f"{api}/product-categories?sort=product_count&order=desc", headers=user_headers).get_json()
    assert res["data"][0] == {"name": "Pain", "product_count": 2}
    assert res["pagination"]["total"] == 2


# ------------------------------------------------------------------ batches & stock
def test_purchase_create_topup_and_conflicts(app, client, api, admin_headers):
    pid = _product(client, api, admin_headers)["product_id"]
    first = _purchase(client, api, admin_headers, pid, qty=10)
    body = first.get_json()["data"]
    assert first.status_code == 201 and body["batch_created"] is True and body["product_stock"] == 10
    assert first.headers["Location"].endswith(f"{api}/batches/{body['batch']['batch_id']}")
    assert body["movement"]["reason"] == "PURCHASE" and body["batch"]["mrp"] == 25.0

    second = _purchase(client, api, admin_headers, pid, qty=5).get_json()["data"]
    assert second["batch_created"] is False and second["product_stock"] == 15

    diff = _purchase(client, api, admin_headers, pid, qty=1, days=100)
    assert diff.status_code == 409 and diff.get_json()["code"] == "CONFLICT"
    expired = _purchase(client, api, admin_headers, pid, batch_no="OLD", qty=1, days=-1)
    assert expired.status_code == 409 and expired.get_json()["code"] == "BATCH_EXPIRED"
    invalid = client.post(f"{api}/products/{pid}/stock/purchase", headers=admin_headers, json={"quantity": 0})
    assert invalid.status_code == 400 and {"batch_no", "expiry_date", "quantity"} <= set(invalid.get_json()["fields"])
    assert _purchase(client, api, admin_headers, "NOPE").status_code == 404
    assert "stock.purchase" in _audit_actions(app, pid)


def test_purchase_idempotency_replay(client, api, admin_headers):
    pid = _product(client, api, admin_headers)["product_id"]
    key = {"Idempotency-Key": "abc-123"}
    first = _purchase(client, api, admin_headers, pid, qty=10, extra_headers=key)
    replay = _purchase(client, api, admin_headers, pid, qty=10, extra_headers=key)
    assert first.status_code == replay.status_code == 201
    assert replay.headers.get("Idempotent-Replayed") == "true"
    assert json.loads(replay.data) == json.loads(first.data)
    assert replay.headers["Location"] == first.headers["Location"]
    assert client.get(f"{api}/products/{pid}", headers=admin_headers).get_json()["data"]["stock"] == 10
    other = _purchase(client, api, admin_headers, pid, qty=10, extra_headers={"Idempotency-Key": "other"})
    assert other.get_json()["data"]["product_stock"] == 20


def test_batches_crud_adjust_writeoff_and_movements(app, client, api, admin_headers):
    pid = _product(client, api, admin_headers)["product_id"]
    other = _product(client, api, admin_headers, name="Other")["product_id"]
    created = client.post(f"{api}/products/{pid}/batches", headers=admin_headers, json={
        "batch_no": "LOT-1", "expiry_date": utc_date_after(300), "mfg_date": utc_date_after(-30), "quantity": 8})
    assert created.status_code == 201
    bid = created.get_json()["data"]["batch"]["batch_id"]
    assert client.post(f"{api}/products/{pid}/batches", headers=admin_headers,
                       json={"batch_no": "LOT-1", "expiry_date": utc_date_after(300)}).status_code == 409
    bad_dates = client.post(f"{api}/products/{pid}/batches", headers=admin_headers, json={
        "batch_no": "LOT-2", "expiry_date": utc_date_after(-60), "mfg_date": utc_date_after(-30)})
    assert bad_dates.status_code == 400 and "expiry_date" in bad_dates.get_json()["fields"]

    listing = client.get(f"{api}/products/{pid}/batches", headers=admin_headers).get_json()
    assert listing["pagination"]["total"] == 1 and listing["data"][0]["quantity"] == 8
    assert client.get(f"{api}/batches/{bid}", headers=admin_headers).get_json()["data"]["batch_no"] == "LOT-1"

    # adjust
    over = client.post(f"{api}/products/{pid}/stock/adjust", headers=admin_headers,
                       json={"batch_id": bid, "change_qty": -9, "reason": "count correction"})
    assert over.status_code == 409 and over.get_json()["code"] == "OUT_OF_STOCK"
    missing = client.post(f"{api}/products/{pid}/stock/adjust", headers=admin_headers, json={"batch_id": bid, "change_qty": -1})
    assert missing.status_code == 400 and "reason" in missing.get_json()["fields"]
    wrong_product = client.post(f"{api}/products/{other}/stock/adjust", headers=admin_headers,
                                json={"batch_id": bid, "change_qty": -1, "reason": "oops"})
    assert wrong_product.status_code == 404
    ok = client.post(f"{api}/products/{pid}/stock/adjust", headers=admin_headers,
                     json={"batch_id": bid, "change_qty": -3, "reason": "damaged strips"})
    assert ok.status_code == 200 and ok.get_json()["data"]["product_stock"] == 5

    # patch: quantity is not editable; expiry moves batch into the expired alert
    assert client.patch(f"{api}/batches/{bid}", headers=admin_headers, json={"quantity": 1}).status_code == 400
    patched = client.patch(f"{api}/batches/{bid}", headers=admin_headers, json={"expiry_date": utc_date_after(-1)})
    assert patched.status_code == 200 and patched.get_json()["data"]["is_expired"] is True
    expired = client.get(f"{api}/inventory/expired", headers=admin_headers).get_json()
    assert [b["batch_id"] for b in expired["data"]] == [bid]

    # write-off
    woff = client.post(f"{api}/batches/{bid}/write-off", headers=admin_headers, json={"note": "expired"})
    assert woff.status_code == 200 and woff.get_json()["data"]["batch"]["quantity"] == 0
    assert woff.get_json()["data"]["movement"]["reason"] == "EXPIRED_WRITEOFF"
    assert client.post(f"{api}/batches/{bid}/write-off", headers=admin_headers).status_code == 409
    assert client.get(f"{api}/batches/{bid}", headers=admin_headers).status_code == 200  # never deleted

    moves = client.get(f"{api}/stock-movements?product_id={pid}&order=asc", headers=admin_headers).get_json()
    assert [m["reason"] for m in moves["data"]] == ["PURCHASE", "ADJUSTMENT", "EXPIRED_WRITEOFF"]
    assert sum(m["change_qty"] for m in moves["data"]) == 0
    only_adj = client.get(f"{api}/stock-movements?product_id={pid}&reason=ADJUSTMENT", headers=admin_headers).get_json()
    assert only_adj["pagination"]["total"] == 1
    assert client.get(f"{api}/stock-movements?from=2999-01-01", headers=admin_headers).get_json()["data"] == []
    assert client.get(f"{api}/stock-movements?from=bad", headers=admin_headers).status_code == 400
    assert {"batch.create", "batch.update", "batch.write_off"} <= set(_audit_actions(app, bid))
    assert "stock.adjust" in _audit_actions(app, pid)


def test_inventory_alerts(client, api, admin_headers):
    soon = _product(client, api, admin_headers, name="Soon", reorder_level=10)["product_id"]
    later = _product(client, api, admin_headers, name="Later", reorder_level=1)["product_id"]
    empty = _product(client, api, admin_headers, name="Empty")["product_id"]
    _purchase(client, api, admin_headers, soon, qty=5, days=30)
    _purchase(client, api, admin_headers, later, qty=50, days=400)

    near = client.get(f"{api}/inventory/near-expiry?days=60", headers=admin_headers).get_json()
    assert [b["product_id"] for b in near["data"]] == [soon]
    assert near["data"][0]["days_to_expiry"] == 30
    assert client.get(f"{api}/inventory/near-expiry?days=10", headers=admin_headers).get_json()["data"] == []
    assert client.get(f"{api}/inventory/near-expiry?days=0", headers=admin_headers).status_code == 400
    default = client.get(f"{api}/inventory/near-expiry", headers=admin_headers).get_json()
    assert default["pagination"]["total"] == 1

    low = {p["product_id"] for p in client.get(f"{api}/inventory/low-stock", headers=admin_headers).get_json()["data"]}
    assert low == {soon, empty}
    out = [p["product_id"] for p in client.get(f"{api}/inventory/out-of-stock", headers=admin_headers).get_json()["data"]]
    assert out == [empty]


# ------------------------------------------------------------------ errors & auth
def test_error_shapes(client, api, admin_headers, expired_headers):
    nf = client.get(f"{api}/does-not-exist", headers=admin_headers)
    assert nf.status_code == 404 and nf.get_json() == {"status": 404, "message": "Resource not found", "code": "NOT_FOUND"}
    mna = client.delete(f"{api}/products", headers=admin_headers)
    assert mna.status_code == 405 and mna.get_json()["code"] == "METHOD_NOT_ALLOWED" and "GET" in mna.headers["Allow"]
    exp = client.get(f"{api}/products", headers=expired_headers)
    assert exp.status_code == 401 and exp.get_json()["code"] == "TOKEN_EXPIRED"
    bad = client.get(f"{api}/products", headers={"Authorization": "Bearer not.a.jwt"})
    assert bad.status_code == 401 and bad.get_json()["code"] == "TOKEN_INVALID"
    none = client.get(f"{api}/products")
    assert none.status_code == 401 and none.get_json()["code"] == "UNAUTHORIZED"
    malformed = client.post(f"{api}/products", headers=admin_headers, data="{bad", content_type="application/json")
    assert malformed.status_code == 400 and malformed.get_json()["code"] == "VALIDATION_ERROR"
    text = client.post(f"{api}/products", headers=admin_headers, data="hello", content_type="text/plain")
    assert text.status_code == 415 and text.get_json()["code"] == "UNSUPPORTED_MEDIA_TYPE"


ENDPOINTS = [
    # (method, path, admin_only)
    ("GET", "/products", False),
    ("POST", "/products", True),
    ("GET", "/products/P1", False),
    ("PATCH", "/products/P1", True),
    ("GET", "/products/by-barcode/123", False),
    ("POST", "/products/P1/deactivate", True),
    ("POST", "/products/P1/reactivate", True),
    ("GET", "/product-categories", False),
    ("GET", "/products/P1/batches", True),
    ("POST", "/products/P1/batches", True),
    ("GET", "/batches/B1", True),
    ("PATCH", "/batches/B1", True),
    ("POST", "/products/P1/stock/purchase", True),
    ("POST", "/products/P1/stock/adjust", True),
    ("POST", "/batches/B1/write-off", True),
    ("GET", "/stock-movements", True),
    ("GET", "/inventory/near-expiry", True),
    ("GET", "/inventory/expired", True),
    ("GET", "/inventory/low-stock", True),
    ("GET", "/inventory/out-of-stock", True),
]


@pytest.mark.parametrize("method,path,admin_only", ENDPOINTS)
def test_auth_required_and_roles(client, api, user_headers, method, path, admin_only):
    res = client.open(f"{api}{path}", method=method, json={})
    assert res.status_code == 401 and res.get_json()["code"] == "UNAUTHORIZED"
    if admin_only:
        res = client.open(f"{api}{path}", method=method, json={}, headers=user_headers)
        assert res.status_code == 403 and res.get_json()["code"] == "FORBIDDEN"
