"""Flask CLI commands.

- `flask --app wsgi init-db [--no-backup]`
- `flask --app wsgi approve-admin --email <email> [--owner]` (emergency recovery; no HTTP exposure)
"""
import click
from flask.cli import with_appcontext

from app.db import db_connection
from app.services.audit_service import write_audit
from app.services.db_init import init_db


@click.command("init-db")
@click.option("--no-backup", is_flag=True, help="Skip the <db>.bak-<timestamp> copy.")
@with_appcontext
def init_db_command(no_backup):
    """Create/upgrade the schema idempotently (additive only, never drops data)."""
    result = init_db(backup=False if no_backup else None)
    click.echo(f"Database ready: {result['database']}")
    if result["backup"]:
        click.echo(f"Backup written: {result['backup']}")


@click.command("approve-admin")
@click.option("--email", required=True, help="Email of the admin account to approve.")
@click.option("--owner", is_flag=True, help="Also make this admin the owner (ownership moves from any previous owner).")
@with_appcontext
def approve_admin_command(email, owner):
    """Approve (and re-activate) an admin by email; optionally transfer ownership. Audited as system:cli."""
    init_db(backup=None)  # make sure is_approved/is_owner exist on older databases (additive only)
    with db_connection(immediate=True) as conn:
        row = conn.execute("SELECT admin_id, role FROM Admin WHERE LOWER(email) = LOWER(?)", (email,)).fetchone()
        if row is None:
            raise click.ClickException(f"No admin account with email {email}")
        admin_id, previous_role = row["admin_id"], row["role"]
        if owner:
            conn.execute("UPDATE Admin SET is_owner = 0 WHERE is_owner IN (1, '1') AND admin_id <> ?", (admin_id,))
        conn.execute(
            "UPDATE Admin SET is_approved = 1, role = 'admin'" + (", is_owner = 1" if owner else "")
            + " WHERE admin_id = ?", (admin_id,))
        write_audit(conn, "system:cli", "system", "admin.approve", "admin", admin_id,
                    {"is_approved": True, "previous_role": previous_role, "owner": bool(owner), "via": "cli"})
    click.echo(f"Admin {admin_id} approved and active" + (" (owner)" if owner else "") + ".")


def register_cli(app):
    app.cli.add_command(init_db_command)
    app.cli.add_command(approve_admin_command)
