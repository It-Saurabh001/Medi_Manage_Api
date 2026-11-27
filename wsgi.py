import os

from app import create_app

# No database work at import time. Schema migration and the bootstrap admin run once in
# scripts/prod/migrate.py before gunicorn starts, so each worker opens its own fresh connections.
# Fail closed: no FLASK_ENV means production (validated config, no fallback secrets).
# Local development sets FLASK_ENV=development explicitly (scripts/dev/run_dev.ps1).
env = os.getenv("FLASK_ENV") or "production"
app = create_app(env)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config.get("DEBUG", False))
