import logging
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


def load_config(filename=None):
    if not filename:
        filename: Path = HOME / ".config" / CONFIG_FILE_NAME

    config = ConfigParser()
    config_file = Path(filename)

    if config_file.is_file():
        config.read(filename)
    else:
        logger.warning("Unable to find config file.")
        raise FileNotFoundError(f"Failed to find config file: {filename}")

    return config, filename
