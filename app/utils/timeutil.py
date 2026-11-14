from datetime import date, datetime, timedelta, timezone


def utc_now():
    return datetime.now(timezone.utc)


def utc_now_iso():
    """Current UTC time as ISO-8601 with `Z`, second precision."""
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_today():
    """Current UTC date as YYYY-MM-DD."""
    return utc_now().date().isoformat()


def utc_date_after(days):
    return (utc_now().date() + timedelta(days=int(days))).isoformat()


def utc_iso_before(hours):
    return (utc_now() - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_iso_z(value):
    """Normalise a stored datetime-ish value to ISO-8601 `Z`; None stays None.

    Plain dates (YYYY-MM-DD) are returned unchanged.
    """
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    if len(text) == 10:
        return text
    try:
        return to_iso_z(parse_iso_datetime(text))
    except ValueError:
        return text


def parse_iso_datetime(text):
    """Parse ISO-8601 datetime (accepts trailing Z or a date). Returns aware UTC datetime."""
    text = str(text).strip()
    if len(text) == 10:
        dt = datetime.strptime(text, "%Y-%m-%d")
    else:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00").replace("z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
