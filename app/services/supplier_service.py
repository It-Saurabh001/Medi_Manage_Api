"""Suppliers data access, validation and serialisation (Part 2 domain). Soft-delete only."""
import re
import uuid

from app.errors import ConflictError, NotFoundError
from app.utils.timeutil import to_iso_z, utc_now_iso
from app.utils.validators import Validator

WRITABLE = ("name", "contact_phone", "email", "gst_number", "address")
SORT_COLUMNS = {"name": "name COLLATE NOCASE", "created_at": "created_at", "updated_at": "updated_at"}
_PHONE = re.compile(r"^\+?[0-9]{7,15}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_GSTIN = re.compile(r"^[0-9]{2}[A-Z0-9]{10}[0-9A-Z]{3}$")


def build_validator(data, partial=False):
    v = Validator(data, partial=partial)
    v.string("name", required=True, min_len=1, max_len=200)
    v.string("contact_phone", default="", max_len=20)
    v.string("email", default="", max_len=200)
    v.string("gst_number", default="", max_len=15)
    v.string("address", default="", max_len=500)
    v.reject("is_active", "use the deactivate action")
    v.reject("supplier_id", "cannot be set")
    c = v.cleaned
    if c.get("contact_phone") and not _PHONE.match(c["contact_phone"].replace(" ", "").replace("-", "")):
        v.error("contact_phone", "must be 7-15 digits, optional leading +")
    if c.get("email") and not _EMAIL.match(c["email"]):
        v.error("email", "must be a valid email address")
    if c.get("gst_number"):
        c["gst_number"] = c["gst_number"].upper()
        if not _GSTIN.match(c["gst_number"]):
            v.error("gst_number", "must be a 15-character GSTIN")
    return v


def serialize_supplier(row):
    return {
        "supplier_id": row["Supplier_id"],
        "name": row["name"],
        "contact_phone": row["contact_phone"] or "",
        "email": row["email"] or "",
        "gst_number": row["gst_number"] or "",
        "address": row["address"] or "",
        "is_active": bool(row["is_active"]),
        "created_at": to_iso_z(row["created_at"]),
        "updated_at": to_iso_z(row["updated_at"]),
    }


def fetch(conn, supplier_id):
    row = conn.execute("SELECT * FROM Suppliers WHERE Supplier_id = ?", (supplier_id,)).fetchone()
    if row is None:
        raise NotFoundError("Supplier not found")
    return row


def ensure_gst_unique(conn, gst_number, exclude_id=None):
    if not gst_number:
        return
    row = conn.execute("SELECT 1 FROM Suppliers WHERE gst_number = ? AND Supplier_id IS NOT ?",
                       (gst_number, exclude_id)).fetchone()
    if row:
        raise ConflictError("GST number already registered", fields={"gst_number": "already in use"})


def insert(conn, cleaned):
    supplier_id = "SUP_" + uuid.uuid4().hex[:10]
    now = utc_now_iso()
    conn.execute(
        """INSERT INTO Suppliers(Supplier_id, name, contact_phone, email, gst_number, address, is_active,
               created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        (supplier_id, cleaned["name"], cleaned.get("contact_phone", ""), cleaned.get("email", ""),
         cleaned.get("gst_number", ""), cleaned.get("address", ""), now, now),
    )
    return supplier_id


def update(conn, supplier_id, cleaned):
    sets, params = [], []
    for col in WRITABLE:
        if col in cleaned:
            sets.append(f"{col} = ?")
            params.append(cleaned[col])
    sets.append("updated_at = ?")
    params.append(utc_now_iso())
    conn.execute(f"UPDATE Suppliers SET {', '.join(sets)} WHERE Supplier_id = ?", params + [supplier_id])


def set_active(conn, supplier_id, active):
    conn.execute("UPDATE Suppliers SET is_active = ?, updated_at = ? WHERE Supplier_id = ?",
                 (1 if active else 0, utc_now_iso(), supplier_id))


def list_suppliers(conn, filters, limit, offset, sort, order):
    where, params = [], []
    if filters.get("q"):
        like = "%" + filters["q"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(name LIKE ? ESCAPE '\\' OR contact_phone LIKE ? ESCAPE '\\' "
                     "OR email LIKE ? ESCAPE '\\' OR gst_number LIKE ? ESCAPE '\\')")
        params += [like] * 4
    if "is_active" in filters:
        where.append("COALESCE(is_active, 1) = ?")
        params.append(1 if filters["is_active"] else 0)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM Suppliers{where_sql}", params).fetchone()[0]
    direction = "DESC" if order == "desc" else "ASC"
    rows = conn.execute(
        f"SELECT * FROM Suppliers{where_sql} ORDER BY {SORT_COLUMNS[sort]} {direction}, rowid {direction} "
        "LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return rows, total
