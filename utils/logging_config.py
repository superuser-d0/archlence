"""Production logging with rotation, redaction and user-facing error IDs."""

import logging
import re
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

from utils.app_paths import log_dir

_LOGGER_NAME = "archlence"
_configured = False


class SensitiveDataFilter(logging.Filter):
    """Redact common key/token shapes if a dependency includes one in a log."""

    _patterns = (
        re.compile(r"(?i)(api[_-]?key|token|password|secret|encryption[_-]?key)"
                   r"\s*[:=]\s*\S+"),
        re.compile(r"AEADv1:[A-Za-z0-9+/=]+"),
    )

    def filter(self, record):
        message = record.getMessage()
        for pattern in self._patterns:
            message = pattern.sub(r"\1=[REDACTED]" if pattern.groups else
                                  "[REDACTED_CIPHERTEXT]", message)
        record.msg = message
        record.args = ()
        return True


def get_logger():
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    destination = Path(log_dir())
    destination.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        destination / "archlence.log",
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.addFilter(SensitiveDataFilter())
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(module)s.%(funcName)s "
        "%(message)s"
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    _configured = True
    return logger


def log_integrity_error(error):
    """Log metadata and traceback without plaintext; return a support ID."""
    error_id = uuid.uuid4().hex[:12]
    get_logger().error(
        "error_id=%s financial_data_invalid table=%s record_id=%s field=%s",
        error_id,
        error.table,
        error.record_id,
        error.field,
        exc_info=(type(error), error, error.__traceback__),
    )
    return error_id
