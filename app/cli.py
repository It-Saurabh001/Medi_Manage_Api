"""Flask CLI commands: `flask --app wsgi init-db [--no-backup]`."""
import click
from flask.cli import with_appcontext

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


def register_cli(app):
    app.cli.add_command(init_db_command)
