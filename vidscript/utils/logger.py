"""Logger module — logging berwarna dengan rich dan rotasi file harian."""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

# Default log directory
DEFAULT_LOG_DIR = "logs"
DEFAULT_LOG_FILE = "vidscript.log"
DEFAULT_LOG_LEVEL = logging.INFO
MAX_LOG_DAYS = 7

# Module-level logger
_logger: Optional[logging.Logger] = None
_console = Console(stderr=True)


def setup_logger(
    level: int = DEFAULT_LOG_LEVEL,
    log_dir: Optional[str] = None,
    quiet: bool = False,
) -> logging.Logger:
    """Setup and configure the VidScript logger.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory for log files. Defaults to 'logs/'.
        quiet: If True, suppress console output entirely.

    Returns:
        Configured logger instance.
    """
    global _logger

    if _logger is not None:
        # Update level if logger already exists
        _logger.setLevel(level)
        for handler in _logger.handlers:
            handler.setLevel(level)
        return _logger

    logger = logging.getLogger("vidscript")
    logger.setLevel(level)
    logger.propagate = False

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler with rich formatting (unless quiet mode)
    if not quiet:
        console_handler = RichHandler(
            console=_console,
            show_time=True,
            show_path=False,
            markup=True,
            rich_tracebacks=True,
        )
        console_handler.setLevel(level)
        console_format = logging.Formatter("%(message)s")
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

    # File handler with daily rotation
    log_directory = log_dir or DEFAULT_LOG_DIR
    log_path = Path(log_directory)
    log_path.mkdir(parents=True, exist_ok=True)

    file_handler = TimedRotatingFileHandler(
        filename=str(log_path / DEFAULT_LOG_FILE),
        when="midnight",
        interval=1,
        backupCount=MAX_LOG_DAYS,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)  # File always captures DEBUG
    file_format = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    _logger = logger
    return logger


def get_logger() -> logging.Logger:
    """Get the VidScript logger instance.

    Returns:
        Logger instance. Creates one with defaults if not yet setup.
    """
    global _logger
    if _logger is None:
        return setup_logger()
    return _logger


def reset_logger() -> None:
    """Reset the logger (mainly for testing)."""
    global _logger
    if _logger:
        for handler in _logger.handlers[:]:
            handler.close()
            _logger.removeHandler(handler)
    _logger = None
