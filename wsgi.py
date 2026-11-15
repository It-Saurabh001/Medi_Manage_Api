import os
from app import create_app

env = os.getenv("FLASK_ENV", "development")
app = create_app(env)

# Auto-create missing tables on startup (idempotent, additive only, no backup copy).
with app.app_context():
    from app.services.db_init import init_db
    init_db(backup=False)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=app.config.get("DEBUG", False))
