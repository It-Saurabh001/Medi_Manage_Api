import cloudinary
from flask_jwt_extended import JWTManager
from app.integrations.email.factory import get_email_sender
from app.integrations.otp_store.factory import get_otp_store

jwt = JWTManager()

def init_extensions(app):
    """Initialize Flask and third-party extensions."""
    jwt.init_app(app)

    # Configure Cloudinary using app config
    cloudinary.config(
        cloud_name=app.config.get("CLOUDINARY_CLOUD_NAME"),
        api_key=app.config.get("CLOUDINARY_API_KEY"),
        api_secret=app.config.get("CLOUDINARY_API_SECRET"),
        secure=True
    )

    # Initialize integration providers once per application
    app.extensions["email_sender"] = get_email_sender(app.config)
    app.extensions["otp_store"] = get_otp_store(app.config)

def get_current_email_sender():
    from flask import current_app
    return current_app.extensions["email_sender"]

def get_current_otp_store():
    from flask import current_app
    return current_app.extensions["otp_store"]
