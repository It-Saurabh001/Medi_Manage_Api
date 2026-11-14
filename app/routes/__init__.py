from app.routes.health import health_bp
from app.routes.auth import auth_bp
from app.routes.admin import admin_bp
from app.routes.user import user_bp
from app.routes.product import product_bp
from app.routes.order import order_bp
from app.routes.inventory import inventory_bp
from app.routes.supplier import supplier_bp
from app.routes.report import report_bp
from app.routes.meta import meta_bp
from app.routes.docs import docs_bp

def register_blueprints(app):
    """Register all route blueprints with the application."""
    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(product_bp)
    app.register_blueprint(order_bp)
    app.register_blueprint(inventory_bp)  # Part 1: batches/stock/alerts under API_PREFIX
    app.register_blueprint(supplier_bp)  # Part 2: suppliers under API_PREFIX
    app.register_blueprint(report_bp)  # Part 2: dashboard/reports/audit-logs under API_PREFIX
    app.register_blueprint(meta_bp)  # Part 3: index/app-config/openapi/devices under API_PREFIX
    app.register_blueprint(docs_bp)  # Part 3: /api/docs and legacy /dox redirect
