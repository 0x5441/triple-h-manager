"""Console and rotating-file logging configuration."""

import logging
from logging.handlers import RotatingFileHandler

from app.config import APPLICATION_LOG_FILE, ensure_runtime_directories


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: int = logging.INFO) -> None:
    """Configure the root logger once for console and local file output."""
    ensure_runtime_directories()
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if any(getattr(handler, "_triple_h_v2", False) for handler in root_logger.handlers):
        return

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    console_handler = logging.StreamHandler()
    file_handler = RotatingFileHandler(
        APPLICATION_LOG_FILE,
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )

    for handler in (console_handler, file_handler):
        handler.setLevel(level)
        handler.setFormatter(formatter)
        handler._triple_h_v2 = True  # type: ignore[attr-defined]
        root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named application logger."""
    return logging.getLogger(name)

