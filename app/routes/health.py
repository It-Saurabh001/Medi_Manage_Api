from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)

@health_bp.route("/health", methods=["GET"])
def health():
    """Health check endpoint indicating service availability."""
    return jsonify({
        "status": "healthy",
        "service": "Medi_Manage_Api"
    }), 200
