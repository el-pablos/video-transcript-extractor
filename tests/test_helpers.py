"""Tests for helpers module."""

import os
import tempfile
from pathlib import Path

import pytest

from vidscript.utils.helpers import (
    ensure_directory,
    format_duration,
    format_file_size,
    get_config_dir,
    get_project_root,
    is_valid_mp4,
    sanitize_filename,
    truncate_text,
)


class TestFormatDuration:
    """Tests for format_duration."""

    def test_seconds_only(self):
        assert format_duration(45) == "45s"

    def test_minutes_and_seconds(self):
        assert format_duration(150) == "2m 30s"

    def test_hours_minutes_seconds(self):
        assert format_duration(5025) == "1h 23m 45s"

    def test_zero(self):
        assert format_duration(0) == "0s"

    def test_negative(self):
        assert format_duration(-5) == "0s"

    def test_exact_hour(self):
        assert format_duration(3600) == "1h 0s"

    def test_float_truncated(self):
        assert format_duration(61.9) == "1m 1s"


class TestFormatFileSize:
    """Tests for format_file_size."""

    def test_bytes(self):
        assert format_file_size(500) == "500 B"

    def test_kilobytes(self):
        result = format_file_size(2048)
        assert "KB" in result

    def test_megabytes(self):
        result = format_file_size(5 * 1024 * 1024)
        assert "MB" in result

    def test_gigabytes(self):
        result = format_file_size(2 * 1024 * 1024 * 1024)
        assert "GB" in result

    def test_zero(self):
        assert format_file_size(0) == "0 B"

    def test_negative(self):
        assert format_file_size(-1) == "0 B"


class TestSanitizeFilename:
    """Tests for sanitize_filename."""

    def test_normal_filename(self):
        assert sanitize_filename("video.mp4") == "video.mp4"

    def test_special_characters(self):
        result = sanitize_filename('file<>:"/\\|?*.mp4')
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result

    def test_leading_trailing_dots(self):
        result = sanitize_filename("...file...")
        assert not result.startswith(".")
        assert not result.endswith(".")

    def test_empty_becomes_unnamed(self):
        assert sanitize_filename("") == "unnamed"

    def test_long_filename_truncated(self):
        long_name = "a" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_dots_and_spaces_only(self):
        assert sanitize_filename("... ...") == "unnamed"


class TestTruncateText:
    """Tests for truncate_text."""

    def test_short_text_unchanged(self):
        assert truncate_text("hello", 80) == "hello"

    def test_long_text_truncated(self):
        text = "a" * 100
        result = truncate_text(text, 20)
        assert len(result) == 20
        assert result.endswith("...")

    def test_custom_suffix(self):
        result = truncate_text("a" * 50, 20, suffix="~")
        assert result.endswith("~")

    def test_exact_length(self):
        text = "a" * 80
        assert truncate_text(text, 80) == text


class TestEnsureDirectory:
    """Tests for ensure_directory."""

    def test_creates_directory(self, tmp_path):
        new_dir = str(tmp_path / "new" / "nested" / "dir")
        result = ensure_directory(new_dir)
        assert result.exists()
        assert result.is_dir()

    def test_existing_directory(self, tmp_path):
        result = ensure_directory(str(tmp_path))
        assert result.exists()


class TestGetProjectRoot:
    """Tests for get_project_root."""

    def test_returns_path(self):
        root = get_project_root()
        assert isinstance(root, Path)


class TestGetConfigDir:
    """Tests for get_config_dir."""

    def test_returns_path(self):
        config_dir = get_config_dir()
        assert isinstance(config_dir, Path)
        assert config_dir.exists()

    def test_is_in_home(self):
        config_dir = get_config_dir()
        assert ".vidscript" in str(config_dir)


class TestIsValidMp4:
    """Tests for is_valid_mp4."""

    def test_valid_mp4(self, tmp_path):
        mp4 = tmp_path / "test.mp4"
        mp4.write_bytes(b"\x00" * 100)
        assert is_valid_mp4(str(mp4)) is True

    def test_nonexistent_file(self):
        assert is_valid_mp4("/nonexistent/file.mp4") is False

    def test_wrong_extension(self, tmp_path):
        txt = tmp_path / "test.txt"
        txt.write_text("hello")
        assert is_valid_mp4(str(txt)) is False

    def test_empty_mp4(self, tmp_path):
        mp4 = tmp_path / "empty.mp4"
        mp4.write_bytes(b"")
        assert is_valid_mp4(str(mp4)) is False
