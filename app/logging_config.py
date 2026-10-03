import logging
import sys

def configure_logging(app):
    """Configure environment-aware logging."""
    is_debug = app.config.get("DEBUG", False)
    log_level = logging.DEBUG if is_debug else logging.INFO

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(formatter)

    # Avoid duplicate handlers if already present
    app.logger.handlers.clear()
    app.logger.addHandler(handler)
    app.logger.setLevel(log_level)
