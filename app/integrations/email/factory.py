import importlib

def get_email_sender(config):
    """Factory selecting and instantiating the email provider using importlib."""
    provider = config.get("EMAIL_PROVIDER", "dev").lower()
    is_prod = (config.get("FLASK_ENV") == "production" or not config.get("DEBUG", True)) and not config.get("TESTING", False)

    if is_prod and provider == "dev":
        raise RuntimeError("Cannot use development email provider in production environment")

    if provider == "dev":
        module = importlib.import_module("app.integrations.email.dev.smtp_debug_sender")
        return module.SmtpDebugSender(config)
    elif provider == "prod" and (config.get("EMAIL_BACKEND") or "smtp").lower() == "api":
        module = importlib.import_module("app.integrations.email.prod.api_sender")
        return module.ApiEmailSender(config)
    elif provider == "prod":
        module = importlib.import_module("app.integrations.email.prod.smtp_sender")
        return module.SmtpSender(config)
    else:
        raise ValueError(f"Unknown email provider: {provider}")
