import os
import ast
import pytest
from config.production import ProductionConfig

def test_no_static_dev_imports_in_shared_code():
    """Ensure no module outside tests/ and dev/ directories directly imports from a dev package."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app_dir = os.path.join(root_dir, "app")

    violations = []

    for root, dirs, files in os.walk(app_dir):
        # Skip the dev provider implementations themselves
        if os.path.basename(root) == "dev":
            continue

        for file in files:
            if not file.endswith(".py"):
                continue

            file_path = os.path.join(root, file)
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    tree = ast.parse(f.read(), filename=file_path)
                except SyntaxError:
                    continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if ".dev." in node.module or node.module.endswith(".dev") or "integrations.email.dev" in node.module or "integrations.otp_store.dev" in node.module:
                        violations.append(f"{os.path.relpath(file_path, root_dir)} imports from {node.module}")
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if ".dev." in alias.name or alias.name.endswith(".dev") or "integrations.email.dev" in alias.name or "integrations.otp_store.dev" in alias.name:
                            violations.append(f"{os.path.relpath(file_path, root_dir)} imports {alias.name}")

    assert not violations, f"Dev package import violations found in shared code:\n" + "\n".join(violations)

def test_production_config_rejects_dev_email_provider(monkeypatch):
    """Verify ProductionConfig fails validation if EMAIL_PROVIDER is set to dev."""
    monkeypatch.setenv("SECRET_KEY", "prod-secret")
    monkeypatch.setenv("JWT_SECRET_KEY", "prod-jwt-secret")
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "secret")
    monkeypatch.setenv("SMTP_HOST", "smtp.sendgrid.net")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "apikey")
    monkeypatch.setenv("SMTP_PASS", "token")
    monkeypatch.setenv("MAIL_DEFAULT_SENDER", "notifications@company.com")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("EMAIL_PROVIDER", "dev")

    with pytest.raises(ValueError) as excinfo:
        ProductionConfig.validate()
    assert "EMAIL_PROVIDER (cannot be 'dev' in production; must be 'prod')" in str(excinfo.value)

def test_production_config_rejects_dev_otp_store(monkeypatch):
    """Verify ProductionConfig fails validation if OTP_STORE_PROVIDER is set to dev."""
    monkeypatch.setenv("SECRET_KEY", "prod-secret")
    monkeypatch.setenv("JWT_SECRET_KEY", "prod-jwt-secret")
    monkeypatch.setenv("CLOUDINARY_CLOUD_NAME", "cloud")
    monkeypatch.setenv("CLOUDINARY_API_KEY", "key")
    monkeypatch.setenv("CLOUDINARY_API_SECRET", "secret")
    monkeypatch.setenv("SMTP_HOST", "smtp.sendgrid.net")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "apikey")
    monkeypatch.setenv("SMTP_PASS", "token")
    monkeypatch.setenv("MAIL_DEFAULT_SENDER", "notifications@company.com")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("OTP_STORE_PROVIDER", "dev")

    with pytest.raises(ValueError) as excinfo:
        ProductionConfig.validate()
    assert "OTP_STORE_PROVIDER (cannot be 'dev' in production; must be 'prod')" in str(excinfo.value)
