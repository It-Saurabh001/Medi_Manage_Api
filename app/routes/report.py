"""Dashboard, reports and audit-log endpoints under API_PREFIX (admin only, Part 2 domain)."""
from flask import current_app, request

from app.db import get_db
from app.errors import ValidationError
from app.services import report_service as rs
from app.utils.api_blueprint import ApiBlueprint
from app.utils.decorators import role_required
from app.utils.pagination import parse_pagination
from app.utils.responses import api_response, paginated_response
from app.utils.timeutil import utc_date_after, utc_today
from app.utils.validators import Validator, parse_iso_date, parse_iso_datetime_z

report_bp = ApiBlueprint("report", __name__)
ADMIN = ["admin"]


def _date_range(args, default_days=30):
    v = Validator(args.to_dict())
    v.iso_date("from", default=utc_date_after(-default_days))
    v.iso_date("to", default=utc_today())
    cleaned = v.validate("Invalid query parameters")
    if cleaned["from"] > cleaned["to"]:
        raise ValidationError("Invalid query parameters", fields={"from": "must be on or before 'to'"})
    return cleaned["from"], cleaned["to"]


@report_bp.get("/dashboard/summary")
@role_required(ADMIN)
def dashboard_summary():
    conn = get_db()
    try:
        data = rs.dashboard_summary(conn, int(current_app.config.get("NEAR_EXPIRY_DAYS", 90)))
    finally:
        conn.close()
    return api_response(data, "Dashboard summary")


@report_bp.get("/reports/sales")
@role_required(ADMIN)
def sales_report():
    date_from, date_to = _date_range(request.args)
    v = Validator(request.args.to_dict())
    v.enum("group_by", ("day", "product"), default="day")
    group_by = v.validate("Invalid query parameters")["group_by"]
    limit, offset, sort, order = parse_pagination(request.args, ("key", "quantity", "revenue"),
                                                  default_sort="key", default_order="asc")
    conn = get_db()
    try:
        data, total, summary = rs.sales_report(conn, date_from, date_to, group_by, limit, offset, sort, order)
    finally:
        conn.close()
    return api_response(data, "Sales report", pagination={"limit": limit, "offset": offset, "total": total},
                        summary=summary)


@report_bp.get("/reports/top-products")
@role_required(ADMIN)
def top_products():
    date_from, date_to = _date_range(request.args)
    limit, offset, sort, order = parse_pagination(request.args, rs.TOP_SORT, default_sort="quantity",
                                                  default_order="desc")
    conn = get_db()
    try:
        data, total = rs.top_products(conn, date_from, date_to, limit, offset, sort, order)
    finally:
        conn.close()
    return paginated_response(data, limit, offset, total, "Top products")


@report_bp.get("/audit-logs")
@role_required(ADMIN)
def list_audit_logs():
    args = request.args.to_dict()
    v = Validator(args)
    for key in ("entity", "entity_id", "actor_id", "action"):
        v.string(key, max_len=100)
    filters = {k: val for k, val in v.validate("Invalid query parameters").items() if val}
    errors = {}
    for key, suffix in (("from", "T00:00:00Z"), ("to", "T23:59:59Z")):
        raw = (args.get(key) or "").strip()
        if raw:
            try:
                filters[key] = parse_iso_date(raw) + suffix if len(raw) == 10 else parse_iso_datetime_z(raw)
            except ValueError as exc:
                errors[key] = str(exc)
    if errors:
        raise ValidationError("Invalid query parameters", fields=errors)
    limit, offset, sort, order = parse_pagination(request.args, rs.AUDIT_SORT, default_sort="created_at",
                                                  default_order="desc")
    conn = get_db()
    try:
        data, total = rs.list_audit_logs(conn, filters, limit, offset, sort, order)
    finally:
        conn.close()
    return paginated_response(data, limit, offset, total, "Audit logs fetched successfully")
