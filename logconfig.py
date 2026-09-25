"""Shared logging: rotating files under logs/ + optional console."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_LOG_DIR = Path(__file__).resolve().parent / "logs"
_LOGGER_NAME = "wtmd"

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

_configured = False


def resolve_level(level: str | int | None) -> int:
    if isinstance(level, int):
        return level
    if not level:
        return logging.INFO
    return _LEVELS.get(str(level).upper(), logging.INFO)


def setup_logging(
    *,
    app_name: str = "app",
    log_dir: Path | str | None = None,
    level: str | int | None = "INFO",
    to_console: bool = True,
    max_bytes: int = 2_000_000,
    backup_count: int = 5,
) -> Path:
    """Configure root `wtmd` logger. Idempotent. Returns the main log file path."""
    global _configured
    directory = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    directory.mkdir(parents=True, exist_ok=True)
    log_file = directory / f"{app_name}.log"

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(resolve_level(level))

    # Clear previous handlers on re-setup (GUI restart / tests)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(resolve_level(level))
    logger.addHandler(file_handler)

    if to_console:
        console = logging.StreamHandler(sys.stderr)
        console.setFormatter(fmt)
        console.setLevel(resolve_level(level))
        logger.addHandler(console)

    logger.propagate = False
    _configured = True
    logger.info("logging initialized app=%s level=%s file=%s", app_name, logging.getLevelName(resolve_level(level)), log_file)
    return log_file


def get_logger(child: str | None = None) -> logging.Logger:
    """Return `wtmd` or `wtmd.child` logger (creates handlers on first use)."""
    logger = logging.getLogger(_LOGGER_NAME if not child else f"{_LOGGER_NAME}.{child}")
    if not _configured and not logging.getLogger(_LOGGER_NAME).handlers:
        setup_logging(app_name="app", to_console=True)
    return logger


def log_file_path(app_name: str = "app", log_dir: Path | str | None = None) -> Path:
    directory = Path(log_dir) if log_dir else DEFAULT_LOG_DIR
    return directory / f"{app_name}.log"
