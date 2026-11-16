"""Check a real Turso database with the app's HTTP client. Read-only: it writes nothing.

PowerShell:
    $env:TURSO_DATABASE_URL="libsql://<db>-<org>.turso.io"; $env:TURSO_AUTH_TOKEN="<token>"
    python scripts/dev/check_turso.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from app.turso_http import TursoConnection  # noqa: E402


def main():
    url, token = os.getenv("TURSO_DATABASE_URL", ""), os.getenv("TURSO_AUTH_TOKEN", "")
    if not url or not token:
        sys.exit("Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN first.")
    conn = TursoConnection(url, token, setup_sql=("PRAGMA foreign_keys=ON",))
    try:
        start = time.perf_counter()
        print("SELECT 1            ->", conn.execute("SELECT 1 AS ok").fetchone()["ok"])
        print("round trip          -> %.0f ms" % ((time.perf_counter() - start) * 1000))
        print("foreign_keys        ->", conn.execute("PRAGMA foreign_keys").fetchone()[0])
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        print("tables              ->", ", ".join(tables) or "(empty database)")
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("SELECT count(*) FROM sqlite_master").fetchone()
        conn.rollback()
        print("BEGIN IMMEDIATE     -> ok (rolled back, nothing written)")
        print("\nTurso connection OK.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
