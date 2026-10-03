import cloudinary
from flask_jwt_extended import JWTManager

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
