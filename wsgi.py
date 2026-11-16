import os

from app import create_app

# No database work at import time. Schema migration and the bootstrap admin run once in
# scripts/prod/migrate.py before gunicorn starts, so each worker opens its own fresh connections.
env = os.getenv("FLASK_ENV", "development")
app = create_app(env)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config.get("DEBUG", False))
