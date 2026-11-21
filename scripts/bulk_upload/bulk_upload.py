"""Bulk-upload medical products (with image + opening stock) to the MediManage API as an admin.

Usage (run on your own machine; your password/OTP never leave it except to your own server):

    pip install requests
    python scripts/bulk_upload/make_images.py          # once: creates images/<dosage_form>.png
    python scripts/bulk_upload/bulk_upload.py --dry-run  # check the CSV, no login, no upload
    python scripts/bulk_upload/bulk_upload.py            # login (email + password + OTP) and upload

Options:
    --csv PATH        CSV to upload (default: products.csv next to this script)
    --base-url URL    API base (default: https://medi-manage-api.onrender.com/api/v1)
    --no-stock        only create products, skip the opening-stock purchase
    --no-images       do not attach the generic dosage-form image

What it does for each CSV row:
  1. Checks the row locally (required fields, enums, price <= mrp, dates).
  2. Skips it if a product with the same name + strength already exists (safe to re-run).
  3. POST /products (multipart) with all product fields + images/<dosage_form>.png.
  4. POST /products/{id}/stock/purchase with batch_no / expiry / quantity (Idempotency-Key set,
     so a network retry never adds the stock twice).
Failed rows are written to failed_rows.csv next to the CSV so you can fix and re-run only those.
The access token is refreshed automatically if the upload runs longer than its 1-hour life.
"""
import argparse
import csv
import getpass
import sys
import time
from datetime import date
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("The 'requests' package is missing. Run:  pip install requests")

HERE = Path(__file__).resolve().parent
DEFAULT_BASE = "https://medi-manage-api.onrender.com/api/v1"

PRODUCT_FIELDS = ("name", "generic_name", "brand_name", "manufacturer", "category", "dosage_form",
                  "strength", "pack_size", "unit", "hsn_code", "gst_percent", "price", "mrp",
                  "purchase_price", "schedule_type", "requires_prescription", "storage_conditions",
                  "reorder_level", "barcode")
STOCK_FIELDS = ("batch_no", "mfg_date", "expiry_date", "quantity", "supplier_name", "invoice_no")
DOSAGE_FORMS = ("Tablet", "Capsule", "Syrup", "Injection", "Ointment", "Drops", "Other")
SCHEDULE_TYPES = ("OTC", "H", "H1", "X", "NARCOTIC")


# ------------------------------------------------------------------ local checks
def _float(row, key, errors, required=False, lo=None, hi=None):
    raw = (row.get(key) or "").strip()
    if not raw:
        if required:
            errors.append(f"{key} is required")
        return None
    try:
        val = float(raw)
    except ValueError:
        errors.append(f"{key} must be a number (got {raw!r})")
        return None
    if lo is not None and val < lo or hi is not None and val > hi:
        errors.append(f"{key} must be between {lo} and {hi}")
    return val


def _date(row, key, errors, required=False):
    raw = (row.get(key) or "").strip()
    if not raw:
        if required:
            errors.append(f"{key} is required (YYYY-MM-DD)")
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        errors.append(f"{key} must be YYYY-MM-DD (got {raw!r})")
        return None


def check_row(row, with_stock):
    errors = []
    if not (row.get("name") or "").strip():
        errors.append("name is required")
    price = _float(row, "price", errors, required=True, lo=0)
    mrp = _float(row, "mrp", errors, lo=0)
    _float(row, "purchase_price", errors, lo=0)
    _float(row, "gst_percent", errors, lo=0, hi=28)
    if price is not None and mrp and price > mrp:
        errors.append("price must not exceed mrp")
    form = (row.get("dosage_form") or "").strip()
    if form and form not in DOSAGE_FORMS:
        errors.append(f"dosage_form must be one of {', '.join(DOSAGE_FORMS)}")
    sched = (row.get("schedule_type") or "").strip()
    if sched and sched not in SCHEDULE_TYPES:
        errors.append(f"schedule_type must be one of {', '.join(SCHEDULE_TYPES)}")
    hsn = (row.get("hsn_code") or "").strip()
    if hsn and not (hsn.isdigit() and 4 <= len(hsn) <= 8):
        errors.append("hsn_code must be 4-8 digits")
    if with_stock and (row.get("batch_no") or "").strip():
        mfg = _date(row, "mfg_date", errors)
        exp = _date(row, "expiry_date", errors, required=True)
        qty = _float(row, "quantity", errors, required=True, lo=1)
        if qty is not None and qty != int(qty):
            errors.append("quantity must be a whole number")
        if exp and exp < date.today():
            errors.append("expiry_date is in the past")
        if mfg and exp and mfg >= exp:
            errors.append("mfg_date must be before expiry_date")
    return errors


# ------------------------------------------------------------------ API client
class ApiError(Exception):
    def __init__(self, status, body):
        self.status, self.body = status, body
        super().__init__(f"HTTP {status}: {body}")


class Client:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.http = requests.Session()
        self.access = self.refresh_token = None

    def _send(self, method, path, auth=True, **kw):
        kw.setdefault("timeout", 90)
        headers = kw.pop("headers", {})
        for attempt in range(3):
            if auth:
                headers["Authorization"] = f"Bearer {self.access}"
            try:
                r = self.http.request(method, self.base + path, headers=headers, **kw)
            except requests.RequestException as exc:
                if attempt == 2:
                    raise ApiError(0, f"network error: {exc}")
                print(f"    network error, retrying in {5 * (attempt + 1)}s ...")
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code == 401 and auth and self.refresh_token and attempt == 0:
                self._refresh()
                continue
            if r.status_code in (502, 503, 504) and attempt < 2:
                print(f"    server busy ({r.status_code}), retrying in {5 * (attempt + 1)}s ...")
                time.sleep(5 * (attempt + 1))
                continue
            try:
                body = r.json()
            except ValueError:
                body = {"message": r.text[:300]}
            if r.status_code >= 400:
                raise ApiError(r.status_code, body)
            return body
        raise ApiError(0, "gave up after retries")

    def _refresh(self):
        print("    access token expired, refreshing ...")
        r = self.http.post(self.base + "/auth/refresh", timeout=60,
                           headers={"Authorization": f"Bearer {self.refresh_token}"})
        if r.status_code != 200:
            sys.exit("Session expired and refresh failed. Run the script again (already-uploaded rows are skipped).")
        self._store_tokens(r.json()["data"])

    def _store_tokens(self, data):
        self.access, self.refresh_token = data["access_token"], data["refresh_token"]

    def wake_up(self):
        root = self.base.split("/api/")[0]
        print("Waking up the server (Render free plan can take up to a minute) ...")
        for _ in range(4):
            try:
                if self.http.get(root + "/health", timeout=90).status_code < 500:
                    return
            except requests.RequestException:
                pass
            time.sleep(5)
        print("  server did not answer /health; continuing anyway.")

    def login(self):
        email = input("Admin email: ").strip()
        password = getpass.getpass("Password (hidden): ")
        data = self._send("POST", "/auth/login", auth=False,
                          json={"email": email, "password": password, "account_type": "admin"})["data"]
        print("A 6-digit code was sent to your email.")
        for _ in range(3):
            otp = input("OTP: ").strip()
            try:
                tokens = self._send("POST", "/auth/verify-otp", auth=False, json={
                    "account_id": data["account_id"], "otp": otp, "account_type": "admin"})["data"]
            except ApiError as exc:
                print(f"  {message_of(exc)}")
                continue
            if tokens.get("role") != "admin":
                sys.exit("This account is not an active admin.")
            self._store_tokens(tokens)
            print("Logged in.\n")
            return
        sys.exit("Too many wrong OTP attempts.")

    def find_existing(self, name, strength):
        body = self._send("GET", "/products", params={"q": name, "limit": 100})
        for p in body.get("data") or []:
            if p["name"].strip().lower() == name.strip().lower() and \
                    (p.get("strength") or "").strip().lower() == (strength or "").strip().lower():
                return p
        return None

    def create_product(self, fields, image_path):
        files = {"image": (image_path.name, image_path.read_bytes(), "image/png")} if image_path else None
        return self._send("POST", "/products", data=fields, files=files, timeout=120)["data"]

    def has_batch(self, product_id, batch_no):
        body = self._send("GET", f"/products/{product_id}/batches", params={"limit": 100})
        return any((b.get("batch_no") or "").strip() == batch_no for b in body.get("data") or [])

    def purchase_stock(self, product_id, stock):
        key = f"bulk-upload-{product_id}-{stock['batch_no']}"
        return self._send("POST", f"/products/{product_id}/stock/purchase", json=stock,
                          headers={"Idempotency-Key": key})["data"]


def message_of(exc):
    """Error envelope is {"status", "message", "code", "fields"?}."""
    body = exc.body if isinstance(exc.body, dict) else {"message": str(exc.body)}
    fields = body.get("fields")
    return f"HTTP {exc.status} {body.get('message') or 'error'}" + (f" {fields}" if fields else "")


# ------------------------------------------------------------------ main
def split_row(row, with_stock):
    fields = {k: row[k].strip() for k in PRODUCT_FIELDS if (row.get(k) or "").strip()}
    stock = None
    if with_stock and (row.get("batch_no") or "").strip():
        stock = {k: row[k].strip() for k in STOCK_FIELDS if (row.get(k) or "").strip()}
        stock["quantity"] = int(float(stock["quantity"]))
    return fields, stock


def image_for(row, use_images):
    if not use_images:
        return None
    path = HERE / "images" / f"{(row.get('dosage_form') or 'Other').strip().lower()}.png"
    return path if path.exists() else None


def main():
    ap = argparse.ArgumentParser(description="Bulk-upload products to the MediManage API")
    ap.add_argument("--csv", default=str(HERE / "products.csv"))
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--dry-run", action="store_true", help="only check the CSV")
    ap.add_argument("--no-stock", action="store_true")
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args()
    with_stock, use_images = not args.no_stock, not args.no_images

    csv_path = Path(args.csv)
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    print(f"{len(rows)} rows in {csv_path.name}")

    bad = {}
    for line, row in enumerate(rows, start=2):
        errs = check_row(row, with_stock)
        if errs:
            bad[line] = errs
            print(f"  line {line} ({row.get('name')}): " + "; ".join(errs))
    if use_images and not (HERE / "images").exists():
        print("  images/ folder missing: run make_images.py first (or pass --no-images)")
        bad[0] = ["images missing"]
    if bad:
        sys.exit(f"\n{len(bad)} problem(s) found. Fix the CSV and run again. Nothing was uploaded.")
    print("CSV looks good.")
    if args.dry_run:
        return

    client = Client(args.base_url)
    client.wake_up()
    client.login()

    created = skipped = 0
    failed = []
    for line, row in enumerate(rows, start=2):
        name = row["name"].strip()
        fields, stock = split_row(row, with_stock)
        tag = f"[{line - 1}/{len(rows)}] {name}"
        try:
            existing = client.find_existing(name, fields.get("strength"))
            if existing:
                pid = existing["product_id"]
                # A previous run may have created the product but failed on stock: finish that part only.
                if stock and not client.has_batch(pid, stock["batch_no"]):
                    result = client.purchase_stock(pid, stock)
                    created += 1
                    print(f"{tag}: already existed ({pid}); added missing stock {result['product_stock']}")
                else:
                    skipped += 1
                    print(f"{tag}: already exists ({pid}), skipped")
                continue
            product = client.create_product(fields, image_for(row, use_images))
            pid = product["product_id"]
            note = "with image" if product.get("image_url") else "no image"
            if stock:
                result = client.purchase_stock(pid, stock)
                note += f", stock {result['product_stock']} (batch {stock['batch_no']})"
            created += 1
            print(f"{tag}: created {pid} ({note})")
        except ApiError as exc:
            reason = message_of(exc)
            failed.append({**row, "error": reason})
            print(f"{tag}: FAILED {reason}")
        time.sleep(0.3)

    print(f"\nDone: {created} created, {skipped} skipped (already existed), {len(failed)} failed.")
    if failed:
        out = csv_path.with_name("failed_rows.csv")
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) + ["error"])
            w.writeheader()
            w.writerows(failed)
        print(f"Failed rows saved to {out}. Fix them and run:  python {Path(__file__).name} --csv \"{out}\"")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit("\nStopped. Re-run any time: products already uploaded are skipped.")
