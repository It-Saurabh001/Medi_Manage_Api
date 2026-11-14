import json

import pytest

from app.db import db_connection
from app.errors import ValidationError
from app.services.audit_service import write_audit
from app.utils.pagination import parse_pagination
from app.utils.timeutil import utc_now_iso
from app.utils.validators import Validator, parse_bool


def test_validator_collects_all_errors():
    v = Validator({"qty": "-1", "price": "abc", "form": "TABLET", "d": "2025-13-01", "flag": "maybe"})
    v.integer("qty", min_value=1).number("price").enum("form", ("Tablet", "Syrup"))
    v.iso_date("d").boolean("flag").string("name", required=True)
    with pytest.raises(ValidationError) as exc:
        v.validate()
    fields = exc.value.fields
    assert set(fields) == {"qty", "price", "d", "flag", "name"}
    assert v.cleaned["form"] == "Tablet"  # case-insensitive, canonical value


def test_validator_defaults_and_partial():
    full = Validator({}).integer("n", default=10).string("s", default="").validate()
    assert full == {"n": 10, "s": ""}
    partial = Validator({"n": "5"}, partial=True).integer("n").string("s", required=True).validate()
    assert partial == {"n": 5}
    with pytest.raises(ValidationError):
        Validator({"s": ""}, partial=True).string("s", required=True).validate()


def test_validator_iso_datetime_and_bool():
    out = Validator({"t": "2025-01-31T10:00:00+05:30"}).iso_datetime("t").validate()
    assert out["t"] == "2025-01-31T04:30:00Z"
    assert parse_bool("true") is True and parse_bool(0) is False
    with pytest.raises(ValueError):
        parse_bool("2")


def test_pagination_defaults_clamp_and_errors():
    assert parse_pagination({}, ("name",)) == (20, 0, "name", "asc")
    assert parse_pagination({"limit": "500", "offset": "3", "order": "DESC"}, ("name",))[:2] == (100, 3)
    with pytest.raises(ValidationError) as exc:
        parse_pagination({"limit": "x", "offset": "-1", "sort": "evil;", "order": "up"}, ("name",))
    assert set(exc.value.fields) == {"limit", "offset", "sort", "order"}


def test_utc_now_iso_format():
    assert utc_now_iso().endswith("Z") and "T" in utc_now_iso()


def test_write_audit_strips_secrets(app):
    with app.app_context():
        with db_connection() as conn:
            audit_id = write_audit(conn, "AID1", "admin", "user.update", "user", "U1",
                                   {"name": "x", "password": "p", "nested": {"otp": "1", "ok": 1}})
        with db_connection() as conn:
            row = conn.execute("SELECT * FROM Audit_Log WHERE Audit_id = ?", (audit_id,)).fetchone()
    details = json.loads(row["details"])
    assert details == {"name": "x", "nested": {"ok": 1}}
    assert row["created_at"].endswith("Z")
