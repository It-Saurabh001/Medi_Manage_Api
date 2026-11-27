"""Users and admins: validation, persistence, serialisation (Part 3 domain).

Soft delete without schema changes: Users -> role='deleted', block=1; Admin -> role='deleted'.
Admin demotion: role='disabled'. Passwords are never serialised.
Admin signup: Admin.is_approved (existing rows default to approved) and Admin.is_owner (at most one,
enforced by the partial unique index ux_admin_owner). The owner cannot be disabled or deleted, and at
least one approved, active admin must always remain.
"""
import re
import sqlite3
import uuid

from werkzeug.security import generate_password_hash

from app.errors import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.utils.timeutil import to_iso_z, utc_now_iso
from app.utils.validators import Validator

PASSWORD_MIN = 8
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")
PIN_RE = re.compile(r"^[0-9]{4,10}$")
USER_SORT = {"created_at": "date_of_account_creation", "name": "name COLLATE NOCASE"}
ADMIN_SORT = {"created_at": "date_of_account_creation", "name": "name COLLATE NOCASE"}
PROTECTED_USER_FIELDS = ("role", "is_approved", "isApproved", "is_blocked", "block", "user_id", "is_deleted",
                         "date_of_account_creation", "created_at", "is_email_verified", "google_sub",
                         "auth_provider")
ADMIN_ROLES = ("admin", "disabled")
PROTECTED_ADMIN_FIELDS = ("role", "is_approved", "isApproved", "is_blocked", "block", "is_owner", "is_active",
                          "admin_id", "image_url", "pin_code", "is_deleted", "date_of_account_creation",
                          "created_at")


def _truthy(value):
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes")
    return bool(value)


def _like(text):
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


# ------------------------------------------------------------------ validation helpers
def add_contact_rules(v, require_email=False):
    """email / phone_number / pin_code format checks on an existing Validator."""
    v.string("email", required=require_email, max_len=200)
    v.string("phone_number", max_len=20)
    v.string("pin_code", max_len=10)
    c = v.cleaned
    if c.get("email"):
        c["email"] = c["email"].lower()
        if not EMAIL_RE.match(c["email"]):
            v.error("email", "must be a valid email address")
    if c.get("phone_number") and not PHONE_RE.match(c["phone_number"].replace(" ", "").replace("-", "")):
        v.error("phone_number", "must be 7-15 digits, optional leading +")
    if c.get("pin_code") and not PIN_RE.match(c["pin_code"]):
        v.error("pin_code", "must be 4-10 digits")
    return v


def add_password_rule(v, field="password", required=False):
    v.string(field, required=required, min_len=PASSWORD_MIN, max_len=128)
    return v


def require_current_password(v, payload, row, verify):
    """If email/password change requested, `current_password` must be present and correct."""
    if any(k in v.cleaned for k in ("password", "email")):
        current = payload.get("current_password")
        if not current:
            v.error("current_password", "required to change email or password")
        elif not verify(row, current):
            v.error("current_password", "is incorrect")
    return v


def hash_password(password):
    return generate_password_hash(password)


# ------------------------------------------------------------------ users
def serialize_user(row):
    keys = row.keys()
    role = (row["role"] or "user").lower()
    return {
        "user_id": row["user_id"],
        "name": row["name"],
        "email": row["email"],
        "phone_number": row["phone_number"],
        "address": row["address"],
        "pin_code": row["pin_code"],
        "role": "user",
        "is_approved": _truthy(row["isApproved"]),
        "is_blocked": _truthy(row["block"]),
        "is_deleted": role == "deleted",
        "image_url": row["image_url"] if "image_url" in keys else None,
        "created_at": to_iso_z(row["date_of_account_creation"]),
        **_auth_fields(row),
    }


def _auth_fields(row):
    keys = row.keys()
    return {
        "auth_provider": (row["auth_provider"] if "auth_provider" in keys else None) or "password",
        "has_password": bool(row["password"]),
        "google_linked": "google_sub" in keys and bool(row["google_sub"]),
    }


def fetch_user(conn, user_id, include_deleted=False):
    row = conn.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,)).fetchone()
    if row is None or (not include_deleted and (row["role"] or "").lower() == "deleted"):
        raise NotFoundError("User not found")
    return row


def ensure_user_unique(conn, email=None, phone=None, exclude_id=None):
    if email:
        if conn.execute("SELECT 1 FROM Users WHERE LOWER(email) = LOWER(?) AND user_id IS NOT ?",
                        (email, exclude_id)).fetchone():
            raise ConflictError("Email already registered", fields={"email": "already registered"})
    if phone:
        if conn.execute("SELECT 1 FROM Users WHERE phone_number = ? AND user_id IS NOT ?",
                        (phone, exclude_id)).fetchone():
            raise ConflictError("Phone number already registered", fields={"phone_number": "already registered"})


def insert_user(conn, cleaned, email_verified=True, password_hash=None):
    """email_verified=False: the customer must confirm the address (OTP) before they can log in."""
    user_id = "UID_" + uuid.uuid4().hex[:12]
    try:
        conn.execute(
            """INSERT INTO Users(user_id, password, date_of_account_creation, isApproved, block, name, address,
                   email, phone_number, pin_code, role, image_url, is_email_verified)
               VALUES (?, ?, ?, 0, 0, ?, ?, ?, ?, ?, 'user', ?, ?)""",
            (user_id, password_hash or hash_password(cleaned["password"]), utc_now_iso(), cleaned["name"],
             cleaned.get("address"), cleaned.get("email"), cleaned.get("phone_number"), cleaned.get("pin_code"),
             cleaned.get("image_url"), 1 if email_verified else 0),
        )
    except sqlite3.IntegrityError:
        raise ConflictError("Account already exists")
    return user_id


def insert_google_user(conn, email, name, google_sub):
    """Google sign-up: no password (authenticate() then always fails), email verified, awaiting approval."""
    user_id = "UID_" + uuid.uuid4().hex[:12]
    try:
        conn.execute(
            """INSERT INTO Users(user_id, password, date_of_account_creation, isApproved, block, name, email,
                   role, is_email_verified, google_sub, auth_provider)
               VALUES (?, NULL, ?, 0, 0, ?, ?, 'user', 1, ?, 'google')""",
            (user_id, utc_now_iso(), name or email.split("@")[0], email, google_sub),
        )
    except sqlite3.IntegrityError:
        raise ConflictError("Account already exists")
    return user_id


USER_COLUMNS = ("name", "address", "phone_number", "pin_code", "email", "image_url", "is_email_verified")


def update_user(conn, user_id, cleaned):
    """Whitelisted update (+ password hash). Raises 404 if nothing matched."""
    sets, params = [], []
    for col in USER_COLUMNS:
        if col in cleaned:
            sets.append(f"{col} = ?")
            params.append(cleaned[col])
    if "password" in cleaned:
        sets.append("password = ?")
        params.append(hash_password(cleaned["password"]))
    if not sets:
        return
    try:
        cur = conn.execute(
            f"UPDATE Users SET {', '.join(sets)} WHERE user_id = ? AND COALESCE(role, 'user') <> 'deleted'",
            params + [user_id])
    except sqlite3.IntegrityError:
        raise ConflictError("Email or phone number already registered")
    if cur.rowcount == 0:
        raise NotFoundError("User not found")


def set_user_flags(conn, user_id, **flags):
    """flags: isApproved / block as 0/1; or role='deleted'. 404 via rowcount."""
    allowed = {"isApproved", "block", "role"}
    sets, params = [], []
    for col, value in flags.items():
        if col not in allowed:
            raise ValueError(col)
        sets.append(f"{col} = ?")
        params.append(value)
    cur = conn.execute(
        f"UPDATE Users SET {', '.join(sets)} WHERE user_id = ? AND COALESCE(role, 'user') <> 'deleted'",
        params + [user_id])
    if cur.rowcount == 0:
        raise NotFoundError("User not found")


def list_users(conn, filters, limit, offset, sort, order):
    where, params = [], []
    if not filters.get("include_deleted"):
        where.append("COALESCE(role, 'user') <> 'deleted'")
    if filters.get("q"):
        where.append("(name LIKE ? ESCAPE '\\' OR email LIKE ? ESCAPE '\\' OR phone_number LIKE ? ESCAPE '\\')")
        params += [_like(filters["q"])] * 3
    if "is_approved" in filters:
        where.append("CASE WHEN isApproved IN (1, '1', 'true', 'True') THEN 1 ELSE 0 END = ?")
        params.append(1 if filters["is_approved"] else 0)
    if "is_blocked" in filters:
        where.append("CASE WHEN block IN (1, '1', 'true', 'True') THEN 1 ELSE 0 END = ?")
        params.append(1 if filters["is_blocked"] else 0)
    if filters.get("updated_since"):
        # Users has no updated_at column: filters by account creation time (see response.md).
        where.append("date_of_account_creation >= ?")
        params.append(filters["updated_since"])
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM Users{where_sql}", params).fetchone()[0]
    direction = "DESC" if order == "desc" else "ASC"
    rows = conn.execute(
        f"SELECT * FROM Users{where_sql} ORDER BY {USER_SORT[sort]} {direction}, id {direction} LIMIT ? OFFSET ?",
        params + [limit, offset]).fetchall()
    return rows, total


# ------------------------------------------------------------------ admins
def serialize_admin(row):
    keys = row.keys()
    role = (row["role"] or "admin").lower()
    return {
        "admin_id": row["admin_id"],
        "name": row["name"],
        "email": row["email"],
        "phone_number": row["phone_number"],
        "role": role,
        "is_active": role == "admin" and email_is_verified(row),
        "is_email_verified": email_is_verified(row),
        "is_approved": admin_is_approved(row),
        "is_owner": admin_is_owner(row),
        "image_url": row["image_url"] if "image_url" in keys else None,
        "created_at": to_iso_z(row["date_of_account_creation"]),
        **_auth_fields(row),
    }


def email_is_verified(row):
    """Rows from before the is_email_verified column existed count as verified."""
    keys = row.keys()
    return "is_email_verified" not in keys or row["is_email_verified"] is None or _truthy(row["is_email_verified"])


def admin_is_approved(row):
    """Rows from before the is_approved column existed count as approved."""
    return "is_approved" not in row.keys() or row["is_approved"] is None or _truthy(row["is_approved"])


def admin_is_owner(row):
    return "is_owner" in row.keys() and _truthy(row["is_owner"])


def fetch_admin(conn, admin_id, include_deleted=False):
    row = conn.execute("SELECT * FROM Admin WHERE admin_id = ?", (admin_id,)).fetchone()
    if row is None or (not include_deleted and (row["role"] or "").lower() == "deleted"):
        raise NotFoundError("Admin not found")
    return row


APPROVED_ACTIVE_SQL = "COALESCE(role, 'admin') = 'admin' AND COALESCE(is_approved, 1) IN (1, '1')"
LAST_ADMIN_MESSAGE = "At least one approved admin is required"
OWNER_MESSAGE = "Owner account is protected"


def approved_admin_count(conn):
    return conn.execute(f"SELECT COUNT(*) FROM Admin WHERE {APPROVED_ACTIVE_SQL}").fetchone()[0]


def ensure_not_owner(admin_row):
    """403 for any attempt to delete, disable (block) or unapprove the owner account."""
    if admin_is_owner(admin_row):
        raise ForbiddenError(OWNER_MESSAGE)


def ensure_not_last_admin(conn, admin_row):
    """409 if removing this admin (delete/disable/unapprove) would leave no approved, active admin."""
    is_counted = (admin_row["role"] or "admin").lower() == "admin" and admin_is_approved(admin_row)
    if is_counted and approved_admin_count(conn) <= 1:
        raise ConflictError(LAST_ADMIN_MESSAGE)


def ensure_admin_removable(conn, admin_row):
    ensure_not_owner(admin_row)
    ensure_not_last_admin(conn, admin_row)


def has_live_admin(conn):
    """True if any admin account exists that is not soft-deleted (or an owner is recorded)."""
    return conn.execute(
        "SELECT 1 FROM Admin WHERE COALESCE(role, 'admin') <> 'deleted' OR is_owner IN (1, '1') LIMIT 1"
    ).fetchone() is not None


def ensure_admin_unique(conn, email=None, phone=None, exclude_id=None):
    if email and conn.execute("SELECT 1 FROM Admin WHERE LOWER(email) = LOWER(?) AND admin_id IS NOT ?",
                              (email, exclude_id)).fetchone():
        raise ConflictError("Email already registered", fields={"email": "already registered"})
    if phone and conn.execute("SELECT 1 FROM Admin WHERE phone_number = ? AND admin_id IS NOT ?",
                              (phone, exclude_id)).fetchone():
        raise ConflictError("Phone number already registered", fields={"phone_number": "already registered"})


def insert_admin(conn, cleaned, is_approved=True, is_owner=False, password_hash=None, email_verified=True):
    """Insert an admin. `password_hash` lets callers hash outside a write-locked transaction."""
    admin_id = "AID_" + uuid.uuid4().hex[:12]
    try:
        conn.execute(
            """INSERT INTO Admin(admin_id, password, name, email, phone_number, date_of_account_creation, role,
                   image_url, is_approved, is_owner, is_email_verified) VALUES (?, ?, ?, ?, ?, ?, 'admin', ?, ?, ?, ?)""",
            (admin_id, password_hash or hash_password(cleaned["password"]), cleaned["name"], cleaned["email"],
             cleaned.get("phone_number") or None, utc_now_iso(), cleaned.get("image_url"),
             1 if is_approved else 0, 1 if is_owner else 0, 1 if email_verified else 0),
        )
    except sqlite3.IntegrityError as exc:
        if "is_owner" in str(exc):
            raise ConflictError("An owner admin already exists; try again")
        raise ConflictError("Email or phone number already registered")
    return admin_id


def insert_google_admin(conn, email, name, google_sub, phone_number=None, is_approved=False, is_owner=False):
    """Google admin signup: no password (password login always fails until one is set via reset),
    email already verified by Google."""
    admin_id = insert_admin(conn, {"email": email, "name": name or email.split("@")[0], "phone_number": phone_number},
                            is_approved=is_approved, is_owner=is_owner, password_hash="!", email_verified=True)
    try:
        conn.execute("UPDATE Admin SET password = NULL, google_sub = ?, auth_provider = 'google' WHERE admin_id = ?",
                     (google_sub, admin_id))
    except sqlite3.IntegrityError:
        raise ConflictError("Account already exists")
    return admin_id


def approve_admin(conn, admin_id):
    cur = conn.execute(
        "UPDATE Admin SET is_approved = 1 WHERE admin_id = ? AND COALESCE(role, 'admin') <> 'deleted'", (admin_id,))
    if cur.rowcount == 0:
        raise NotFoundError("Admin not found")


ADMIN_COLUMNS = ("name", "phone_number", "email", "image_url", "role")


def update_admin(conn, admin_id, cleaned):
    sets, params = [], []
    for col in ADMIN_COLUMNS:
        if col in cleaned:
            sets.append(f"{col} = ?")
            params.append(cleaned[col])
    if "password" in cleaned:
        sets.append("password = ?")
        params.append(hash_password(cleaned["password"]))
    if not sets:
        return
    try:
        cur = conn.execute(
            f"UPDATE Admin SET {', '.join(sets)} WHERE admin_id = ? AND COALESCE(role, 'admin') <> 'deleted'",
            params + [admin_id])
    except sqlite3.IntegrityError:
        raise ConflictError("Email or phone number already registered")
    if cur.rowcount == 0:
        raise NotFoundError("Admin not found")


def list_admins(conn, filters, limit, offset, sort, order):
    where, params = ["COALESCE(role, 'admin') <> 'deleted'"], []
    if filters.get("q"):
        where.append("(name LIKE ? ESCAPE '\\' OR email LIKE ? ESCAPE '\\')")
        params += [_like(filters["q"])] * 2
    if filters.get("role"):
        where.append("COALESCE(role, 'admin') = ?")
        params.append(filters["role"])
    if "is_approved" in filters:
        where.append("CASE WHEN COALESCE(is_approved, 1) IN (1, '1') THEN 1 ELSE 0 END = ?")
        params.append(1 if filters["is_approved"] else 0)
    where_sql = " WHERE " + " AND ".join(where)
    total = conn.execute(f"SELECT COUNT(*) FROM Admin{where_sql}", params).fetchone()[0]
    direction = "DESC" if order == "desc" else "ASC"
    rows = conn.execute(
        f"SELECT * FROM Admin{where_sql} ORDER BY {ADMIN_SORT[sort]} {direction}, id {direction} LIMIT ? OFFSET ?",
        params + [limit, offset]).fetchall()
    return rows, total


def profile_validator(payload, partial=True):
    """Shared base for user profile writes (name/address + contact)."""
    v = Validator(payload, partial=partial)
    v.string("name", required=True, min_len=1, max_len=200)
    v.string("address", max_len=500)
    add_contact_rules(v)
    return v


def reject_fields(v, fields, message="cannot be changed here"):
    for field in fields:
        v.reject(field, message)
    return v


def validation_error_if(cond, field, message):
    if cond:
        raise ValidationError(fields={field: message})
