"""Product catalogue data access, validation rules and serialisation (Part 1 domain)."""
import uuid

from app.errors import ConflictError, NotFoundError
from app.utils.timeutil import to_iso_z, utc_now_iso, utc_today
from app.utils.validators import Validator

DOSAGE_FORMS = ("Tablet", "Capsule", "Syrup", "Injection", "Ointment", "Drops", "Other")
SCHEDULE_TYPES = ("OTC", "H", "H1", "X", "NARCOTIC")
RX_SCHEDULES = frozenset({"H", "H1", "X", "NARCOTIC"})

# Client field -> Products column (fixed allow-list; the only names ever placed in SQL text)
WRITABLE_COLUMNS = {
    "name": "name",
    "generic_name": "generic_name",
    "brand_name": "brand_name",
    "manufacturer": "manufacturer",
    "category": "category",
    "dosage_form": "dosage_form",
    "strength": "strength",
    "pack_size": "pack_size",
    "unit": "unit",
    "hsn_code": "hsn_code",
    "gst_percent": "gst_percent",
    "price": "price",
    "mrp": "mrp",
    "purchase_price": "purchase_price",
    "schedule_type": "schedule_type",
    "requires_prescription": "requires_prescription",
    "storage_conditions": "storage_conditions",
    "reorder_level": "reorder_level",
    "barcode": "barcode",
    "image_url": "image_url",
}

SORT_COLUMNS = {
    "name": "p.name COLLATE NOCASE",
    "price": "p.price",
    "mrp": "p.mrp",
    "stock": "p.stock",
    "created_at": "p.created_at",
    "updated_at": "p.updated_at",
}

# Non-expired quantity; needs one `?` bound to today's date
SELLABLE_SQL = (
    "(SELECT COALESCE(SUM(b.quantity), 0) FROM Product_Batches b "
    "WHERE b.Product_id = p.Product_id AND b.expiry_date >= ?)"
)


def _num(value):
    try:
        return None if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return None


def _int(value, default=None):
    try:
        return default if value is None or value == "" else int(float(value))
    except (TypeError, ValueError):
        return default


def _flag(value, default=False):
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


def serialize_product(row, include_cost=False):
    """Products row (+ optional sellable_stock) -> R7 dict. Cost price only for admins."""
    keys = row.keys()
    stock = _int(row["stock"], 0)
    sellable = _int(row["sellable_stock"], stock) if "sellable_stock" in keys else stock
    return {
        "product_id": row["Product_id"],
        "name": row["name"],
        "generic_name": row["generic_name"] or "",
        "brand_name": row["brand_name"] or "",
        "manufacturer": row["manufacturer"] or "Unknown",
        "category": row["category"] or "General",
        "dosage_form": row["dosage_form"] or "Tablet",
        "strength": row["strength"] or "",
        "pack_size": row["pack_size"] or "",
        "unit": row["unit"] or "strip",
        "hsn_code": row["hsn_code"] or "",
        "gst_percent": _num(row["gst_percent"]),
        "price": _num(row["price"]),
        "mrp": _num(row["mrp"]),
        "purchase_price": _num(row["purchase_price"]) if include_cost else None,
        "schedule_type": row["schedule_type"] or "OTC",
        "requires_prescription": _flag(row["requires_prescription"]),
        "storage_conditions": row["storage_conditions"] or "",
        "reorder_level": _int(row["reorder_level"], 10),
        "barcode": row["barcode"] or "",
        "image_url": row["image_url"],
        "stock": stock,
        "sellable_stock": sellable,
        "in_stock": sellable > 0,
        "is_active": _flag(row["is_active"], True),
        "created_at": to_iso_z(row["created_at"]),
        "updated_at": to_iso_z(row["updated_at"]),
    }


def build_product_validator(data, partial=False):
    """Validator with every product rule; caller adds cross-field checks then calls .validate()."""
    v = Validator(data, partial=partial)
    v.string("name", required=True, min_len=1, max_len=200)
    v.string("generic_name", default="", max_len=200)
    v.string("brand_name", default="", max_len=200)
    v.string("manufacturer", default="Unknown", max_len=200)
    v.string("category", default="General", max_len=100)
    v.enum("dosage_form", DOSAGE_FORMS, default="Tablet")
    v.string("strength", default="", max_len=50)
    v.string("pack_size", default="", max_len=50)
    v.string("unit", default="strip", max_len=30)
    v.string("hsn_code", default="", max_len=8)
    v.number("gst_percent", default=12.0, min_value=0, max_value=28)
    v.number("price", required=True, min_value=0)
    v.number("mrp", default=0.0, min_value=0)
    v.number("purchase_price", default=0.0, min_value=0)
    v.enum("schedule_type", SCHEDULE_TYPES, default="OTC")
    v.boolean("requires_prescription", default=False)
    v.string("storage_conditions", default="", max_len=255)
    v.integer("reorder_level", default=10, min_value=0)
    v.string("barcode", default="", max_len=64)
    v.reject("stock", "stock is managed through batches (use stock/purchase or stock/adjust)")
    v.reject("is_active", "use the deactivate / reactivate actions")
    v.reject("image_url", "upload an image file in the 'image' field")
    v.reject("product_id", "cannot be set")

    hsn = v.cleaned.get("hsn_code")
    if hsn and not (hsn.isdigit() and 4 <= len(hsn) <= 8):
        v.error("hsn_code", "must be 4-8 digits")
    return v


def apply_product_rules(v, current=None):
    """Cross-field rules on merged (current + cleaned) values. Mutates v.cleaned."""
    merged = dict(current or {})
    merged.update(v.cleaned)
    schedule = merged.get("schedule_type") or "OTC"
    if schedule in RX_SCHEDULES:
        # Scheduled drugs always need a prescription, whatever the client sent.
        if not _flag(merged.get("requires_prescription")) or "schedule_type" in v.cleaned:
            v.cleaned["requires_prescription"] = True
    price, mrp = _num(merged.get("price")), _num(merged.get("mrp"))
    if price is not None and mrp and price > mrp and ("price" in v.cleaned or "mrp" in v.cleaned):
        v.error("price", "must not exceed mrp")
    return v


def ensure_barcode_unique(conn, barcode, exclude_product_id=None):
    if not barcode:
        return
    row = conn.execute(
        "SELECT Product_id FROM Products WHERE barcode = ? AND Product_id IS NOT ?",
        (barcode, exclude_product_id),
    ).fetchone()
    if row:
        raise ConflictError("Barcode already assigned to another product", fields={"barcode": "already in use"})


def fetch_product(conn, product_id, active_only=False):
    """Products row with sellable_stock, or raise 404."""
    sql = f"SELECT p.*, {SELLABLE_SQL} AS sellable_stock FROM Products p WHERE p.Product_id = ?"
    params = [utc_today(), product_id]
    if active_only:
        sql += " AND COALESCE(p.is_active, 1) = 1"
    row = conn.execute(sql, params).fetchone()
    if row is None:
        raise NotFoundError("Product not found")
    return row


def fetch_product_by_barcode(conn, barcode, active_only=False):
    sql = (f"SELECT p.*, {SELLABLE_SQL} AS sellable_stock FROM Products p "
           "WHERE p.barcode = ? AND p.barcode <> ''")
    if active_only:
        sql += " AND COALESCE(p.is_active, 1) = 1"
    sql += " ORDER BY COALESCE(p.is_active, 1) DESC, p.id ASC LIMIT 1"
    row = conn.execute(sql, (utc_today(), barcode)).fetchone()
    if row is None:
        raise NotFoundError("No product with this barcode")
    return row


def list_products(conn, filters, limit, offset, sort, order):
    """filters: q, category, schedule_type, requires_prescription, is_active, in_stock, updated_since.

    Returns (rows, total).
    """
    today = utc_today()
    where, params = [], []
    if filters.get("q"):
        like = "%" + filters["q"].replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        where.append("(p.name LIKE ? ESCAPE '\\' OR p.generic_name LIKE ? ESCAPE '\\' "
                     "OR p.brand_name LIKE ? ESCAPE '\\' OR p.barcode LIKE ? ESCAPE '\\')")
        params += [like] * 4
    if filters.get("category"):
        where.append("LOWER(COALESCE(NULLIF(p.category, ''), 'General')) = LOWER(?)")
        params.append(filters["category"])
    if filters.get("schedule_type"):
        where.append("COALESCE(p.schedule_type, 'OTC') = ?")
        params.append(filters["schedule_type"])
    if "requires_prescription" in filters:
        where.append("COALESCE(p.requires_prescription, 0) = ?")
        params.append(1 if filters["requires_prescription"] else 0)
    if "is_active" in filters:
        where.append("COALESCE(p.is_active, 1) = ?")
        params.append(1 if filters["is_active"] else 0)
    if "in_stock" in filters:
        where.append(f"{SELLABLE_SQL} {'>' if filters['in_stock'] else '<='} 0")
        params.append(today)
    if filters.get("updated_since"):
        where.append("p.updated_at >= ?")
        params.append(filters["updated_since"])

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM Products p{where_sql}", params).fetchone()[0]
    order_sql = f"{SORT_COLUMNS[sort]} {'DESC' if order == 'desc' else 'ASC'}, p.id ASC"
    rows = conn.execute(
        f"SELECT p.*, {SELLABLE_SQL} AS sellable_stock FROM Products p{where_sql} "
        f"ORDER BY {order_sql} LIMIT ? OFFSET ?",
        [today] + params + [limit, offset],
    ).fetchall()
    return rows, total


def insert_product(conn, cleaned):
    """Insert a new product (stock 0, active). Returns Product_id."""
    product_id = "PROD_" + uuid.uuid4().hex[:10]
    now = utc_now_iso()
    values = {col: cleaned.get(field) for field, col in WRITABLE_COLUMNS.items() if field in cleaned}
    values["requires_prescription"] = 1 if cleaned.get("requires_prescription") else 0
    values.update({"Product_id": product_id, "stock": 0, "is_active": 1, "created_at": now, "updated_at": now})
    columns = list(values)
    conn.execute(
        f"INSERT INTO Products({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
        [values[c] for c in columns],
    )
    return product_id


def update_product_fields(conn, product_id, cleaned):
    """Partial update of whitelisted columns + updated_at."""
    sets, params = [], []
    for field, col in WRITABLE_COLUMNS.items():
        if field in cleaned:
            value = cleaned[field]
            if field == "requires_prescription":
                value = 1 if value else 0
            sets.append(f"{col} = ?")
            params.append(value)
    sets.append("updated_at = ?")
    params.append(utc_now_iso())
    conn.execute(f"UPDATE Products SET {', '.join(sets)} WHERE Product_id = ?", params + [product_id])


def set_product_active(conn, product_id, active):
    conn.execute(
        "UPDATE Products SET is_active = ?, updated_at = ? WHERE Product_id = ?",
        (1 if active else 0, utc_now_iso(), product_id),
    )


def list_categories(conn, active_only, limit, offset, sort, order):
    where = " WHERE COALESCE(is_active, 1) = 1" if active_only else ""
    name_sql = "COALESCE(NULLIF(category, ''), 'General')"
    total = conn.execute(f"SELECT COUNT(DISTINCT {name_sql}) FROM Products{where}").fetchone()[0]
    sort_sql = {"name": "name COLLATE NOCASE", "product_count": "product_count"}[sort]
    rows = conn.execute(
        f"SELECT {name_sql} AS name, COUNT(*) AS product_count FROM Products{where} "
        f"GROUP BY {name_sql} ORDER BY {sort_sql} {'DESC' if order == 'desc' else 'ASC'}, name ASC "
        "LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [{"name": r["name"], "product_count": int(r["product_count"])} for r in rows], total
