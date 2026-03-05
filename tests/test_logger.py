"""Tests for logger module."""

import logging
from pathlib import Path

import pytest

from vidscript.utils.logger import (
    get_logger,
    reset_logger,
    setup_logger,
)


@pytest.fixture(autouse=True)
def clean_logger():
    """Reset logger before and after each test."""
    reset_logger()
    yield
    reset_logger()


class TestSetupLogger:
    """Tests for setup_logger."""

    def test_returns_logger(self, tmp_path):
        logger = setup_logger(log_dir=str(tmp_path))
        assert isinstance(logger, logging.Logger)
        assert logger.name == "vidscript"

    def test_default_level(self, tmp_path):
        logger = setup_logger(log_dir=str(tmp_path))
        assert logger.level == logging.INFO

    def test_custom_level(self, tmp_path):
        logger = setup_logger(level=logging.DEBUG, log_dir=str(tmp_path))
        assert logger.level == logging.DEBUG

    def test_quiet_mode(self, tmp_path):
        logger = setup_logger(quiet=True, log_dir=str(tmp_path))
        # In quiet mode, only file handler should be present (no RichHandler)
        handler_types = [type(h).__name__ for h in logger.handlers]
        assert "RichHandler" not in handler_types

    def test_creates_log_file(self, tmp_path):
        setup_logger(log_dir=str(tmp_path))
        log_file = tmp_path / "vidscript.log"
        assert log_file.exists()

    def test_existing_logger_updates_level(self, tmp_path):
        logger1 = setup_logger(level=logging.INFO, log_dir=str(tmp_path))
        logger2 = setup_logger(level=logging.DEBUG, log_dir=str(tmp_path))
        assert logger1 is logger2
        assert logger1.level == logging.DEBUG

    def test_no_propagation(self, tmp_path):
        logger = setup_logger(log_dir=str(tmp_path))
        assert logger.propagate is False


class TestGetLogger:
    """Tests for get_logger."""

    def test_returns_logger(self):
        logger = get_logger()
        assert isinstance(logger, logging.Logger)
        assert logger.name == "vidscript"

    def test_creates_if_not_exists(self):
        logger = get_logger()
        assert logger is not None

    def test_returns_same_logger(self, tmp_path):
        logger1 = setup_logger(log_dir=str(tmp_path))
        logger2 = get_logger()
        assert logger1 is logger2


class TestResetLogger:
    """Tests for reset_logger."""

    def test_reset_clears_logger(self, tmp_path):
        setup_logger(log_dir=str(tmp_path))
        reset_logger()
        # After reset, get_logger creates a new one
        logger = get_logger()
        assert logger is not None

    def test_reset_without_setup(self):
        # Should not raise
        reset_logger()
