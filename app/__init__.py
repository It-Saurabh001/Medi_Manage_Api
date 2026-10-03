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

    # Register centralized error handlers
    register_error_handlers(app)

    # Register all application blueprints
    register_blueprints(app)

    return app
