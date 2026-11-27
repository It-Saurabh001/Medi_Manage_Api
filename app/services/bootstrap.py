"""Optional startup bootstrap for hosts without shell access (e.g. Render free tier).

Set BOOTSTRAP_ADMIN_EMAIL (and BOOTSTRAP_ADMIN_PASSWORD to create it when missing). On every start the
admin is created if absent, then approved and made owner. Remove the env vars once no longer needed.
"""
import os

from flask import current_app

from app.db import db_connection
from app.services import account_service as acc


def bootstrap_admin():
    email = (os.getenv("BOOTSTRAP_ADMIN_EMAIL") or "").strip()
    if not email:
        return
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or ""
    name = os.getenv("BOOTSTRAP_ADMIN_NAME") or "Owner"
    with db_connection(immediate=True) as conn:
        row = conn.execute("SELECT admin_id, is_owner FROM Admin WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
        other_owner = conn.execute(
            "SELECT admin_id FROM Admin WHERE is_owner IN (1, '1') AND COALESCE(role, 'admin') = 'admin' "
            "AND LOWER(email) <> LOWER(?) LIMIT 1", (email,)).fetchone()
        if other_owner is not None:
            # An active owner already exists: never silently move ownership or re-enable an account
            # just because old BOOTSTRAP_* variables are still set. Use `flask approve-admin --owner`.
            current_app.logger.warning("bootstrap: skipped, an active owner already exists; remove BOOTSTRAP_ADMIN_* "
                                       "env vars")
            return
        if row is None:
            if not password:
                current_app.logger.warning("bootstrap: admin not found and BOOTSTRAP_ADMIN_PASSWORD not set")
                return
            admin_id = acc.insert_admin(conn, {"email": email, "password": password, "name": name},
                                        is_approved=True, is_owner=False, email_verified=True)
        else:
            admin_id = row["admin_id"]
        if os.getenv("BOOTSTRAP_ADMIN_PASSWORD"):
            current_app.logger.warning("bootstrap: BOOTSTRAP_ADMIN_PASSWORD is still set; remove it from the "
                                       "environment now that the owner exists")
        conn.execute("UPDATE Admin SET is_owner = 0 WHERE is_owner IN (1, '1') AND admin_id <> ?", (admin_id,))
        conn.execute("UPDATE Admin SET is_approved = 1, is_owner = 1, is_email_verified = 1, role = 'admin' "
                     "WHERE admin_id = ?", (admin_id,))
    current_app.logger.warning("bootstrap: admin %s approved as owner", admin_id)
