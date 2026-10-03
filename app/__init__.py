from flask import Flask
from config import get_config
from app.extensions import init_extensions
from app.logging_config import configure_logging
from app.errors import register_error_handlers
from app.routes.health import health_bp

def create_app(config_name=None):
    """Application factory for Medi_Manage_Api."""
    config_class = get_config(config_name)

    app = Flask(__name__, template_folder="templates")
    app.config.from_object(config_class)

    # Initialize extensions
    init_extensions(app)

    # Configure logging
    configure_logging(app)

    # Register centralized error handlers
    register_error_handlers(app)

    # Register foundational routes
    app.register_blueprint(health_bp)

    return app
