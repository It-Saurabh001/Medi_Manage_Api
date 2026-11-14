from app.errors import ValidationError

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def parse_pagination(args, allowed_sort=None, default_sort=None, default_order="asc"):
    """Parse limit/offset/sort/order from a query-arg mapping.

    Returns (limit, offset, sort, order). `sort` is validated against `allowed_sort`
    (iterable of names; mapping name->SQL column is the caller's job). limit is clamped
    to MAX_LIMIT. Raises ValidationError with a `fields` map.
    """
    fields = {}
    limit, offset = DEFAULT_LIMIT, 0

    raw_limit = args.get("limit")
    if raw_limit not in (None, ""):
        try:
            limit = int(raw_limit)
            if limit < 1:
                fields["limit"] = "must be >= 1"
            limit = min(limit, MAX_LIMIT)
        except (TypeError, ValueError):
            fields["limit"] = "must be an integer"

    raw_offset = args.get("offset")
    if raw_offset not in (None, ""):
        try:
            offset = int(raw_offset)
            if offset < 0:
                fields["offset"] = "must be >= 0"
        except (TypeError, ValueError):
            fields["offset"] = "must be an integer"

    allowed = list(allowed_sort or [])
    sort = args.get("sort") or default_sort or (allowed[0] if allowed else None)
    if allowed and sort not in allowed:
        fields["sort"] = f"must be one of: {', '.join(allowed)}"

    order = (args.get("order") or default_order or "asc").lower()
    if order not in ("asc", "desc"):
        fields["order"] = "must be 'asc' or 'desc'"

    if fields:
        raise ValidationError("Invalid pagination parameters", fields=fields)
    return limit, offset, sort, order
