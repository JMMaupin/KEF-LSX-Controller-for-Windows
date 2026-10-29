"""The log file: %APPDATA%\\KefLSXController\\kef-controller.log.

The executable has no console: without a log, a decision taken at boot --
switch the speaker to USB or leave it alone -- leaves no trace.
"""

import logging
from logging.handlers import RotatingFileHandler

from . import __version__, paths

LOGGER_NAME = "kef_controller"


def setup():
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    try:
        handler = RotatingFileHandler(
            paths.log_file(), maxBytes=256 * 1024, backupCount=2, encoding="utf-8")
    except OSError:
        handler = logging.NullHandler()
    handler.setFormatter(logging.Formatter(
        f"%(asctime)s [{__version__}] %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger
