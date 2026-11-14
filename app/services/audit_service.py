"""Append-only audit trail. Callers own the transaction; this never commits."""
import json
import uuid

from app.utils.timeutil import utc_now_iso

_SENSITIVE_MARKERS = ("password", "otp", "token", "secret")


def _scrub(value):
    if isinstance(value, dict):
        return {
            k: _scrub(v)
            for k, v in value.items()
            if not any(marker in str(k).lower() for marker in _SENSITIVE_MARKERS)
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    return value


def write_audit(conn, actor_id, actor_role, action, entity, entity_id, details=None):
    """Insert one Audit_Log row (password/otp/token/secret keys stripped). Returns Audit_id."""
    audit_id = "AUD_" + uuid.uuid4().hex[:16]
    conn.execute(
        """INSERT INTO Audit_Log(Audit_id, actor_id, actor_role, action, entity, entity_id, details, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            audit_id,
            None if actor_id is None else str(actor_id),
            actor_role,
            action,
            entity,
            None if entity_id is None else str(entity_id),
            json.dumps(_scrub(details or {}), default=str, sort_keys=True),
            utc_now_iso(),
        ),
    )
    return audit_id
