"""Tests for settings module."""

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from vidscript.config.settings import (
    AppSettings,
    OutputSettings,
    RedisSettings,
    TranscriptionSettings,
    get_settings,
    show_settings,
)


class TestRedisSettings:
    """Tests for RedisSettings."""

    def test_defaults(self):
        """Test default Redis settings."""
        with patch.dict("os.environ", {}, clear=True):
            rs = RedisSettings.from_env()
            assert rs.host == "localhost"
            assert rs.port == 6379
            assert rs.db == 0
            assert rs.cache_ttl == 604800

    def test_from_env(self):
        """Test Redis settings from environment."""
        env = {
            "REDIS_HOST": "custom-host",
            "REDIS_PORT": "1234",
            "REDIS_DB": "3",
            "REDIS_USERNAME": "myuser",
            "REDIS_PASSWORD": "mypass",
            "REDIS_CACHE_TTL": "3600",
        }
        with patch.dict("os.environ", env, clear=True):
            rs = RedisSettings.from_env()
            assert rs.host == "custom-host"
            assert rs.port == 1234
            assert rs.db == 3
            assert rs.username == "myuser"
            assert rs.password == "mypass"
            assert rs.cache_ttl == 3600


class TestTranscriptionSettings:
    """Tests for TranscriptionSettings."""

    def test_defaults(self):
        """Test default transcription settings."""
        ts = TranscriptionSettings()
        assert ts.model == "base"
        assert ts.language == "auto"
        assert ts.device == "auto"
        assert ts.compute_type == "int8"
        assert ts.word_timestamps is True


class TestOutputSettings:
    """Tests for OutputSettings."""

    def test_defaults(self):
        """Test default output settings."""
        os_ = OutputSettings()
        assert os_.format == "txt"
        assert os_.output_dir is None


class TestAppSettings:
    """Tests for AppSettings."""

    def test_defaults(self):
        """Test default app settings."""
        with patch.dict("os.environ", {}, clear=True):
            settings = AppSettings()
            assert settings.verbose is False
            assert settings.quiet is False
            assert isinstance(settings.redis, RedisSettings)
            assert isinstance(settings.transcription, TranscriptionSettings)
            assert isinstance(settings.output, OutputSettings)

    def test_to_dict(self):
        """Test converting settings to dictionary."""
        settings = AppSettings(
            redis=RedisSettings(host="test", port=1234, db=0,
                                username="u", password="p", cache_ttl=100),
            transcription=TranscriptionSettings(),
            output=OutputSettings(),
        )
        d = settings.to_dict()
        assert isinstance(d, dict)
        assert d["redis"]["host"] == "test"
        assert d["transcription"]["model"] == "base"

    def test_load_without_config_file(self, tmp_dir):
        """Test loading settings without config file."""
        with patch("vidscript.config.settings.CONFIG_FILE", tmp_dir / "nonexistent.json"):
            settings = AppSettings.load()
            assert settings.transcription.model == "base"

    def test_load_with_config_file(self, tmp_dir):
        """Test loading settings from config file."""
        config_file = tmp_dir / "config.json"
        config_data = {
            "transcription": {"model": "small", "language": "id"},
            "output": {"format": "json"},
        }
        config_file.write_text(json.dumps(config_data))

        with patch("vidscript.config.settings.CONFIG_FILE", config_file):
            settings = AppSettings.load()
            assert settings.transcription.model == "small"
            assert settings.transcription.language == "id"
            assert settings.output.format == "json"

    def test_load_with_invalid_config_file(self, tmp_dir):
        """Test loading with invalid JSON config file."""
        config_file = tmp_dir / "config.json"
        config_file.write_text("invalid json {{{")

        with patch("vidscript.config.settings.CONFIG_FILE", config_file):
            # Should not raise, just use defaults
            settings = AppSettings.load()
            assert settings.transcription.model == "base"

    def test_save(self, tmp_dir):
        """Test saving settings to config file."""
        config_dir = tmp_dir / "vidscript_config"
        config_file = config_dir / "config.json"

        with patch("vidscript.config.settings.CONFIG_DIR", config_dir):
            with patch("vidscript.config.settings.CONFIG_FILE", config_file):
                settings = AppSettings(
                    transcription=TranscriptionSettings(model="medium"),
                    output=OutputSettings(format="json"),
                )
                settings.save()

                assert config_file.exists()
                saved = json.loads(config_file.read_text())
                assert saved["transcription"]["model"] == "medium"
                assert saved["output"]["format"] == "json"


class TestGetSettings:
    """Tests for get_settings."""

    def test_returns_app_settings(self):
        """Test that get_settings returns AppSettings."""
        with patch.object(AppSettings, "load", return_value=AppSettings()):
            settings = get_settings()
            assert isinstance(settings, AppSettings)


class TestShowSettings:
    """Tests for show_settings."""

    def test_masks_password(self):
        """Test that password is masked."""
        settings = AppSettings(
            redis=RedisSettings(host="h", port=1, db=0,
                                username="user", password="secret", cache_ttl=100),
        )
        display = show_settings(settings)
        assert display["redis"]["password"] == "****"
        assert display["redis"]["username"] == "****"

    def test_no_masking_when_empty(self):
        """Test no masking when credentials are empty."""
        settings = AppSettings(
            redis=RedisSettings(host="h", port=1, db=0,
                                username="", password="", cache_ttl=100),
        )
        display = show_settings(settings)
        assert display["redis"]["password"] == ""
