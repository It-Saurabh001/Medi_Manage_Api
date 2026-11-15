import logging
import sys

def configure_logging(app):
    """Configure environment-aware logging."""
    is_debug = app.config.get("DEBUG", False)
    log_level = logging.DEBUG if is_debug else logging.INFO

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )

    # Under gunicorn reuse its (unbuffered stderr) handlers so app/module logs reach Render logs;
    # otherwise stderr, which is never block-buffered like stdout is without PYTHONUNBUFFERED.
    gunicorn_handlers = logging.getLogger("gunicorn.error").handlers
    if gunicorn_handlers:
        handlers = list(gunicorn_handlers)
    else:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(log_level)
        handler.setFormatter(formatter)
        handlers = [handler]

    # Avoid duplicate handlers if already present
    app.logger.handlers.clear()
    for handler in handlers:
        app.logger.addHandler(handler)
    app.logger.setLevel(log_level)
    app.logger.propagate = False

    # Root logger: module loggers (e.g. app.integrations.email.prod.api_sender) propagate here.
    root = logging.getLogger()
    root.handlers.clear()
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(log_level)
