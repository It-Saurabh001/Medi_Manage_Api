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
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development").lower()

    config_class = CONFIG_MAP.get(config_name)
    if not config_class:
        raise ValueError(
            f"Unknown configuration environment '{config_name}'. Allowed: {list(CONFIG_MAP.keys())}"
        )

    if config_name == "production":
        config_class.validate()

    return config_class
