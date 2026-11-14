"""Dashboard, sales reports and audit-log queries (Part 2 domain, read-only).

Sales totals exclude Sell_History rows whose order is `returned` (net sales).
"""
import json

from app.utils.timeutil import to_iso_z, utc_date_after, utc_today

_NET_SALES = ("FROM Sell_History s LEFT JOIN Order_Details o ON o.Order_id = s.Order_id "
              "WHERE COALESCE(o.status, '') <> 'returned'")
AUDIT_SORT = {"created_at": "created_at"}
TOP_SORT = {"quantity": "quantity", "revenue": "revenue"}
GROUP_SORT = {"day": {"key": "day", "quantity": "quantity", "revenue": "revenue"},
              "product": {"key": "product_name COLLATE NOCASE", "quantity": "quantity", "revenue": "revenue"}}


def _scalar(conn, sql, params=()):
    value = conn.execute(sql, params).fetchone()[0]
    return value or 0


def dashboard_summary(conn, near_expiry_days):
    today = utc_today()
    return {
        "date": today,
        "products": int(_scalar(conn, "SELECT COUNT(*) FROM Products WHERE COALESCE(is_active, 1) = 1")),
        "low_stock": int(_scalar(conn, "SELECT COUNT(*) FROM Products WHERE COALESCE(is_active, 1) = 1 "
                                       "AND COALESCE(stock, 0) <= COALESCE(reorder_level, 10)")),
        "out_of_stock": int(_scalar(conn, "SELECT COUNT(*) FROM Products WHERE COALESCE(is_active, 1) = 1 "
                                          "AND COALESCE(stock, 0) <= 0")),
        "near_expiry_batches": int(_scalar(
            conn, "SELECT COUNT(*) FROM Product_Batches WHERE quantity > 0 AND expiry_date >= ? AND expiry_date <= ?",
            (today, utc_date_after(near_expiry_days)))),
        "expired_batches": int(_scalar(
            conn, "SELECT COUNT(*) FROM Product_Batches WHERE quantity > 0 AND expiry_date < ?", (today,))),
        "pending_orders": int(_scalar(conn, "SELECT COUNT(*) FROM Order_Details WHERE status = 'pending'")),
        "approved_orders": int(_scalar(conn, "SELECT COUNT(*) FROM Order_Details WHERE status = 'approved'")),
        "today_sales_total": round(float(_scalar(
            conn, f"SELECT SUM(s.total_amount) {_NET_SALES} AND substr(s.date_of_sell, 1, 10) = ?", (today,))), 2),
        "today_sales_count": int(_scalar(
            conn, f"SELECT COUNT(DISTINCT s.Order_id) {_NET_SALES} AND substr(s.date_of_sell, 1, 10) = ?", (today,))),
        "near_expiry_days": near_expiry_days,
    }


def sales_report(conn, date_from, date_to, group_by, limit, offset, sort, order):
    """Returns (rows, total_groups, summary). group_by: day | product."""
    key = "substr(s.date_of_sell, 1, 10)" if group_by == "day" else "s.product_id"
    select = (f"{key} AS day" if group_by == "day"
              else "s.product_id AS product_id, MAX(s.product_name) AS product_name")
    where = f"{_NET_SALES} AND substr(s.date_of_sell, 1, 10) >= ? AND substr(s.date_of_sell, 1, 10) <= ?"
    params = [date_from, date_to]
    total = _scalar(conn, f"SELECT COUNT(DISTINCT {key}) {where}", params)
    direction = "DESC" if order == "desc" else "ASC"
    rows = conn.execute(
        f"SELECT {select}, SUM(s.quantity) AS quantity, ROUND(SUM(s.total_amount), 2) AS revenue, "
        f"COUNT(DISTINCT s.Order_id) AS orders {where} GROUP BY {key} "
        f"ORDER BY {GROUP_SORT[group_by][sort]} {direction} LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    summary_row = conn.execute(
        f"SELECT COALESCE(SUM(s.quantity), 0), COALESCE(ROUND(SUM(s.total_amount), 2), 0), "
        f"COUNT(DISTINCT s.Order_id) {where}", params).fetchone()
    data = []
    for r in rows:
        item = {"day": r["day"]} if group_by == "day" else {"product_id": r["product_id"],
                                                             "product_name": r["product_name"]}
        item.update({"quantity": int(r["quantity"] or 0), "revenue": float(r["revenue"] or 0),
                     "orders": int(r["orders"] or 0)})
        data.append(item)
    summary = {"from": date_from, "to": date_to, "group_by": group_by, "quantity": int(summary_row[0]),
               "revenue": float(summary_row[1]), "orders": int(summary_row[2])}
    return data, int(total), summary


def top_products(conn, date_from, date_to, limit, offset, sort, order):
    where = f"{_NET_SALES} AND substr(s.date_of_sell, 1, 10) >= ? AND substr(s.date_of_sell, 1, 10) <= ?"
    params = [date_from, date_to]
    total = _scalar(conn, f"SELECT COUNT(DISTINCT s.product_id) {where}", params)
    direction = "DESC" if order == "desc" else "ASC"
    rows = conn.execute(
        f"SELECT s.product_id AS product_id, MAX(s.product_name) AS product_name, SUM(s.quantity) AS quantity, "
        f"ROUND(SUM(s.total_amount), 2) AS revenue {where} GROUP BY s.product_id "
        f"ORDER BY {TOP_SORT[sort]} {direction}, product_id ASC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    data = [{"product_id": r["product_id"], "product_name": r["product_name"],
             "quantity": int(r["quantity"] or 0), "revenue": float(r["revenue"] or 0)} for r in rows]
    return data, int(total)


def serialize_audit(row):
    try:
        details = json.loads(row["details"] or "{}")
    except ValueError:
        details = {}
    return {
        "audit_id": row["Audit_id"],
        "actor_id": row["actor_id"],
        "actor_role": row["actor_role"],
        "action": row["action"],
        "entity": row["entity"],
        "entity_id": row["entity_id"],
        "details": details,
        "created_at": to_iso_z(row["created_at"]),
    }


def list_audit_logs(conn, filters, limit, offset, sort, order):
    where, params = [], []
    for key in ("entity", "entity_id", "actor_id", "action"):
        if filters.get(key):
            where.append(f"{key} = ?")
            params.append(filters[key])
    if filters.get("from"):
        where.append("created_at >= ?")
        params.append(filters["from"])
    if filters.get("to"):
        where.append("created_at <= ?")
        params.append(filters["to"])
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    total = _scalar(conn, f"SELECT COUNT(*) FROM Audit_Log{where_sql}", params)
    direction = "DESC" if order == "desc" else "ASC"
    rows = conn.execute(
        f"SELECT * FROM Audit_Log{where_sql} ORDER BY {AUDIT_SORT[sort]} {direction}, rowid {direction} "
        "LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    return [serialize_audit(r) for r in rows], int(total)
