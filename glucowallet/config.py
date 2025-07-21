"""
Handle all config settings, mainly credentials, for connecting.
"""

import logging
import os
from configparser import ConfigParser
from pathlib import Path


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)

HOME: Path = Path.home()
CONFIG_FILE_NAME: str = "glucowallet-config.ini"


def validate_config(config):
    """Make sure we have the settings we need."""
    missing = [
        f"{section}.{key}"
        for section, values in config.items()
        for key, val in values.items()
        if not val
    ]
    if missing:
        raise EnvironmentError(f"Missing required env variables: {', '.join(missing)}")


def _load_config_from_environment() -> dict:
    """Read LibreLinkUp and InfluxDB credentials from environment variables."""
    config = {
        "influx": {
            "url": os.environ.get("GLUCOWALLET_INFLUXDB_URL"),
            "bucket": os.environ.get("GLUCOWALLET_INFLUXDB_BUCKET"),
            "org": os.environ.get("GLUCOWALLET_INFLUXDB_ORG"),
            "token": os.environ.get("GLUCOWALLET_INFLUXDB_TOKEN"),
        },
        "libre-linkup": {
            "username": os.environ.get("GLUCOWALLET_LINKUP_USERNAME"),
            "password": os.environ.get("GLUCOWALLET_LINKUP_PASSWORD"),
        },
    }

    validate_config(config)

    return config


def load_config(filename=None):
    """Attempt to load from the user's ~/.config/glucowallet/glucowallet-config.ini file, fail over to env
    variables if there is no file"""
    if not filename:
        filename = HOME / ".config" / CONFIG_FILE_NAME

    config_file = Path(filename)

    if not config_file.is_file():
        logger.info("Unable to find config file, trying environment variables")
        # fail over to env variables
        return _load_config_from_environment(), None

    config = ConfigParser()
    config.read(filename)

    return config, filename
