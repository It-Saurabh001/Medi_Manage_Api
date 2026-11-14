"""Input validation that collects every problem into a `fields` map (R3/R6)."""
import math
from datetime import datetime

from flask import request

from app.errors import ApiError, ValidationError
from app.utils.timeutil import parse_iso_datetime

MISSING = object()
_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off"}


# ---------- single-value parsers (raise ValueError with a client-safe message) ----------

def parse_int(value, min_value=None, max_value=None):
    if isinstance(value, bool):
        raise ValueError("must be an integer")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError("must be an integer")
        value = int(value)
    try:
        result = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("must be an integer")
    if min_value is not None and result < min_value:
        raise ValueError(f"must be >= {min_value}")
    if max_value is not None and result > max_value:
        raise ValueError(f"must be <= {max_value}")
    return result


def parse_number(value, min_value=None, max_value=None):
    if isinstance(value, bool):
        raise ValueError("must be a number")
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("must be a number")
    if math.isnan(result) or math.isinf(result):
        raise ValueError("must be a finite number")
    if min_value is not None and result < min_value:
        raise ValueError(f"must be >= {min_value}")
    if max_value is not None and result > max_value:
        raise ValueError(f"must be <= {max_value}")
    return result


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    text = str(value).strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ValueError("must be true or false")


def parse_enum(value, choices):
    text = str(value).strip()
    for choice in choices:
        if text.lower() == str(choice).lower():
            return choice
    raise ValueError(f"must be one of: {', '.join(map(str, choices))}")


def parse_iso_date(value):
    text = str(value).strip()
    try:
        return datetime.strptime(text, "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ValueError("must be a date in YYYY-MM-DD format")


def parse_iso_datetime_z(value):
    try:
        return parse_iso_datetime(value).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        raise ValueError("must be an ISO-8601 datetime, e.g. 2025-01-31T10:00:00Z")


# ---------- request body ----------

def request_payload():
    """Return the request body as a dict (JSON object or form fields).

    Raises 400 for malformed JSON and 415 for unsupported content types with a body.
    """
    if request.is_json:
        data = request.get_json(silent=True)
        if data is None:
            raise ValidationError("Malformed JSON body")
        if not isinstance(data, dict):
            raise ValidationError("JSON body must be an object")
        return data
    if request.mimetype in ("multipart/form-data", "application/x-www-form-urlencoded"):
        return request.form.to_dict()
    if not request.get_data(cache=True):
        return {}
    raise ApiError("Unsupported media type", 415, "UNSUPPORTED_MEDIA_TYPE")


# ---------- collector ----------

class Validator:
    """Chainable validator. Each rule writes a clean value into `.cleaned` or an error into `.errors`.

    partial=True (PATCH): absent fields are skipped; required fields sent empty are errors;
    defaults are not applied.
    """

    def __init__(self, data, partial=False):
        self.data = data or {}
        self.partial = partial
        self.errors = {}
        self.cleaned = {}

    def _value(self, name, required, default, blank_is_missing=True):
        raw = self.data.get(name, None)
        missing = raw is None or (blank_is_missing and isinstance(raw, str) and raw.strip() == "")
        if missing:
            if self.partial:
                if name in self.data and required:
                    self.errors[name] = "cannot be empty"
                return MISSING
            if required:
                self.errors[name] = "is required"
            elif default is not MISSING:
                self.cleaned[name] = default
            return MISSING
        return raw

    def _apply(self, name, required, default, parser, blank_is_missing=True):
        raw = self._value(name, required, default, blank_is_missing)
        if raw is MISSING:
            return self
        try:
            self.cleaned[name] = parser(raw)
        except ValueError as exc:
            self.errors[name] = str(exc)
        return self

    def required(self, name):
        self._value(name, True, MISSING)
        return self

    def string(self, name, required=False, default=MISSING, max_len=255, min_len=0):
        def parse(raw):
            if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
                raise ValueError("must be a string")
            text = str(raw).strip()
            if len(text) < min_len:
                raise ValueError(f"must be at least {min_len} characters")
            if len(text) > max_len:
                raise ValueError(f"must be at most {max_len} characters")
            return text

        # Optional strings may be sent as "" to clear them.
        return self._apply(name, required, default, parse, blank_is_missing=required)

    def integer(self, name, required=False, default=MISSING, min_value=None, max_value=None):
        return self._apply(name, required, default, lambda v: parse_int(v, min_value, max_value))

    def number(self, name, required=False, default=MISSING, min_value=None, max_value=None):
        return self._apply(name, required, default, lambda v: parse_number(v, min_value, max_value))

    def enum(self, name, choices, required=False, default=MISSING):
        return self._apply(name, required, default, lambda v: parse_enum(v, choices))

    def iso_date(self, name, required=False, default=MISSING):
        return self._apply(name, required, default, parse_iso_date)

    def iso_datetime(self, name, required=False, default=MISSING):
        return self._apply(name, required, default, parse_iso_datetime_z)

    def boolean(self, name, required=False, default=MISSING):
        return self._apply(name, required, default, parse_bool)

    def reject(self, name, message):
        if name in self.data:
            self.errors[name] = message
        return self

    def error(self, name, message):
        self.errors[name] = message
        return self

    @property
    def ok(self):
        return not self.errors

    def validate(self, message="Validation failed"):
        """Return cleaned data or raise ValidationError(fields=errors)."""
        if self.errors:
            raise ValidationError(message, fields=dict(self.errors))
        return self.cleaned
