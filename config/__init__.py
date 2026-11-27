import os
from config.development import DevelopmentConfig
from config.testing import TestingConfig
from config.production import ProductionConfig

CONFIG_MAP = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}

def get_config(config_name=None):
    """Retrieve and validate the configuration class for the given environment."""
    # Fail closed: without an explicit FLASK_ENV the strict, validated production config is used, so a
    # missing variable can never silently enable the development fallback secrets.
    config_name = (config_name or os.getenv("FLASK_ENV") or "production").strip().lower()

    config_class = CONFIG_MAP.get(config_name)
    if not config_class:
        raise ValueError(
            f"Unknown configuration environment '{config_name}'. Allowed: {list(CONFIG_MAP.keys())}"
        )

    if config_name == "production":
        config_class.validate()

    return config_class
