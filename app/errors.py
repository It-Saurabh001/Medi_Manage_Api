from werkzeug.exceptions import HTTPException
from app.utils.responses import error_response

def register_error_handlers(app):
    """Register centralized JSON error handlers across the application."""

    @app.errorhandler(400)
    def bad_request(error):
        message = getattr(error, "description", "Bad Request")
        return error_response(message=message, status_code=400)

    @app.errorhandler(401)
    def unauthorized(error):
        message = getattr(error, "description", "Unauthorized")
        return error_response(message=message, status_code=401)

    @app.errorhandler(403)
    def forbidden(error):
        message = getattr(error, "description", "Access Forbidden")
        return error_response(message=message, status_code=403)

    @app.errorhandler(404)
    def not_found(error):
        message = getattr(error, "description", "Resource Not Found")
        return error_response(message=message, status_code=404)

    @app.errorhandler(405)
    def method_not_allowed(error):
        return error_response(message="Method Not Allowed", status_code=405)

    @app.errorhandler(422)
    def unprocessable_entity(error):
        message = getattr(error, "description", "Unprocessable Entity")
        return error_response(message=message, status_code=422)

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        code = error.code if error.code else 500
        return error_response(message=error.description, status_code=code)

    @app.errorhandler(Exception)
    def handle_generic_exception(error):
        app.logger.exception("Unhandled server exception: %s", error)
        if app.config.get("DEBUG", False):
            return error_response(message=str(error), status_code=500)
        return error_response(message="Internal Server Error", status_code=500)
