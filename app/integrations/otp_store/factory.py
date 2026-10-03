import importlib

def get_otp_store(config):
    """Factory selecting and instantiating the OTP store provider using importlib."""
    provider = config.get("OTP_STORE_PROVIDER", "dev").lower()
    is_prod = config.get("FLASK_ENV") == "production" or not config.get("DEBUG", True)

    if is_prod and provider == "dev":
        raise RuntimeError("Cannot use development OTP store in production environment")

    if provider == "dev":
        module = importlib.import_module("app.integrations.otp_store.dev.memory_store")
        return module.MemoryOtpStore()
    elif provider == "prod":
        module = importlib.import_module("app.integrations.otp_store.prod.redis_store")
        return module.RedisOtpStore(config.get("REDIS_URL"))
    else:
        raise ValueError(f"Unknown OTP store provider: {provider}")
