from flask import Flask
from config import get_config
from app.extensions import init_extensions
from app.logging_config import configure_logging
from app.errors import register_error_handlers
from app.routes import register_blueprints

def create_app(config_name=None):
    """Application factory for Medi_Manage_Api."""
    config_class = get_config(config_name)

    app = Flask(__name__, template_folder="templates")
    app.config.from_object(config_class)

    # Initialize extensions and provider integrations
    init_extensions(app)

    # Strict production guards
    is_prod = app.config.get("FLASK_ENV") == "production" or (not app.config.get("DEBUG", True) and not app.config.get("TESTING", False))
    if is_prod:
        email_sender = app.extensions.get("email_sender")
        otp_store = app.extensions.get("otp_store")
        if email_sender and "dev" in email_sender.__class__.__module__:
            raise RuntimeError("Development email provider cannot run in production")
        if otp_store and "dev" in otp_store.__class__.__module__:
            raise RuntimeError("Development OTP store cannot run in production")

    # Configure logging
    configure_logging(app)
    sender = app.extensions.get("email_sender")
    app.logger.info("Email sender: %s, provider=%s, key_set=%s, sender_set=%s",
                    type(sender).__name__, app.config.get("EMAIL_API_PROVIDER"),
                    bool(app.config.get("EMAIL_API_KEY")), bool(app.config.get("MAIL_DEFAULT_SENDER")))
    if is_prod:
        if app.config.get("TURSO_DATABASE_URL"):
            app.logger.info("Database: Turso (hosted libSQL)")
        else:
            app.logger.warning("TURSO_DATABASE_URL is not set: using the local SQLite file %s. On hosts with an "
                               "ephemeral disk (e.g. Render free) all data is lost on every restart or deploy.",
                               app.config.get("DATABASE_NAME"))
    if is_prod and not app.config.get("ADMIN_SIGNUP_CODE"):
        app.logger.warning("ADMIN_SIGNUP_CODE is not set: anyone can request an admin account via "
                           "POST /admins/register (accounts still need approval). Set it in production.")

    # Register centralized error handlers
    register_error_handlers(app)

    # Register all application blueprints
    register_blueprints(app)

    # Part 1: CLI commands (flask init-db)
    from app.cli import register_cli
    register_cli(app)

    # Part 3: JWT blocklist, ProxyFix, CORS, X-App-Version gate
    from app.platform import init_platform
    init_platform(app)

    return app
