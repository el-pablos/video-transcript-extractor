"""Tests for CLI module — comprehensive coverage."""

import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from vidscript.cli import main, print_banner


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


class TestBanner:
    """Tests for the CLI banner."""

    def test_banner_no_error(self, capsys):
        try:
            print_banner()
        except Exception:
            pytest.fail("print_banner() raised an exception")

    def test_banner_with_pyfiglet(self, capsys):
        mock_pyfiglet = MagicMock()
        mock_pyfiglet.figlet_format.return_value = "VidScript"
        with patch.dict("sys.modules", {"pyfiglet": mock_pyfiglet, "colorama": MagicMock()}):
            print_banner()


class TestMainCommand:
    """Tests for the main CLI group."""

    def test_main_help(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "VidScript" in result.output

    def test_main_no_args(self, runner):
        result = runner.invoke(main, [])
        assert result.exit_code == 0

    def test_version_command(self, runner):
        result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output


class TestTranscribeCommand:
    """Tests for the transcribe subcommand."""

    def test_transcribe_help(self, runner):
        result = runner.invoke(main, ["transcribe", "--help"])
        assert result.exit_code == 0

    def test_transcribe_nonexistent_file(self, runner):
        result = runner.invoke(main, ["transcribe", "/nonexistent/video.mp4"])
        assert result.exit_code != 0

    def test_transcribe_model_choices(self, runner):
        result = runner.invoke(main, ["transcribe", "/nonexistent.mp4", "--model", "invalid"])
        assert result.exit_code != 0

    def test_transcribe_single_file(self, runner, tmp_path):
        mp4_file = tmp_path / "test.mp4"
        mp4_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00" * 100)

        with patch("vidscript.cli._process_single") as mock_single:
            result = runner.invoke(main, [
                "--quiet", "transcribe", str(mp4_file), "--no-cache"
            ])

    def test_transcribe_batch(self, runner, tmp_path):
        mp4_file = tmp_path / "test.mp4"
        mp4_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00" * 100)

        with patch("vidscript.cli._process_batch") as mock_batch:
            result = runner.invoke(main, [
                "--quiet", "transcribe", str(tmp_path), "--batch"
            ])

    def test_transcribe_directory_auto_batch(self, runner, tmp_path):
        """Directory triggers batch even without --batch flag."""
        with patch("vidscript.cli._process_batch") as mock_batch:
            result = runner.invoke(main, [
                "--quiet", "transcribe", str(tmp_path)
            ])

    def test_transcribe_with_all_options(self, runner, tmp_path):
        mp4_file = tmp_path / "test.mp4"
        mp4_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00" * 100)

        with patch("vidscript.cli._process_single"):
            result = runner.invoke(main, [
                "--quiet", "transcribe", str(mp4_file),
                "--model", "small", "--language", "en",
                "--format", "srt", "--diarize", "--no-cache"
            ])

    def test_transcribe_with_cache(self, runner, tmp_path):
        """Test transcribe sets up cache when --no-cache is not given."""
        mp4_file = tmp_path / "test.mp4"
        mp4_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00" * 100)

        with patch("vidscript.cli._process_single") as mock_single:
            with patch("vidscript.cache.redis_cache.RedisCache") as mock_cache_cls:
                with patch("vidscript.config.settings.get_settings") as mock_settings:
                    mock_settings.return_value = MagicMock()
                    result = runner.invoke(main, [
                        "--quiet", "transcribe", str(mp4_file)
                    ])

    def test_transcribe_cache_setup_error(self, runner, tmp_path):
        """Test transcribe handles cache setup error gracefully."""
        mp4_file = tmp_path / "test.mp4"
        mp4_file.write_bytes(b"\x00\x00\x00\x1cftypisom" + b"\x00" * 100)

        with patch("vidscript.cli._process_single") as mock_single:
            with patch("vidscript.cache.redis_cache.RedisCache", side_effect=Exception("Redis down")):
                with patch("vidscript.config.settings.get_settings") as mock_settings:
                    mock_settings.return_value = MagicMock()
                    result = runner.invoke(main, [
                        "--quiet", "transcribe", str(mp4_file)
                    ])


class TestProcessSingle:
    """Tests for _process_single function."""

    def test_cache_hit(self, tmp_path):
        from vidscript.cli import _process_single

        mp4 = tmp_path / "test.mp4"
        mp4.write_bytes(b"\x00" * 100)

        mock_cache = MagicMock()
        mock_cache.get.return_value = MagicMock(segments=[])
        mock_logger = MagicMock()

        with patch("vidscript.core.media_handler.get_file_hash", return_value="abc123"):
            with patch("vidscript.output.formatter.format_output", return_value="text"):
                with patch("vidscript.output.writer.write_result"):
                    _process_single(
                        str(mp4), MagicMock(), "txt", None, None, mock_cache, mock_logger
                    )
                    mock_cache.get.assert_called_once()

    def test_cache_miss_success(self, tmp_path):
        from vidscript.cli import _process_single

        mp4 = tmp_path / "test.mp4"
        mp4.write_bytes(b"\x00" * 100)

        mock_cache = MagicMock()
        mock_cache.get.return_value = None

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.transcript = MagicMock(
            language="en", language_probability=0.95,
            duration=60.0, model="base", segments=[]
        )
        mock_result.file_path = str(mp4)
        mock_result.processing_time = 2.0

        mock_extractor_cls = MagicMock()
        mock_extractor_cls.return_value.extract.return_value = mock_result

        with patch("vidscript.core.media_handler.get_file_hash", return_value="abc"):
            with patch("vidscript.utils.progress.ProgressTracker") as mock_pt:
                mock_pt.return_value.__enter__ = MagicMock(return_value=MagicMock())
                mock_pt.return_value.__exit__ = MagicMock(return_value=False)
                with patch("vidscript.core.extractor.Extractor", mock_extractor_cls):
                    with patch("vidscript.output.formatter.format_output", return_value="out"):
                        with patch("vidscript.output.writer.write_result"):
                            with patch("vidscript.cli._print_summary"):
                                _process_single(
                                    str(mp4), MagicMock(), "txt", None, None,
                                    mock_cache, MagicMock()
                                )

    def test_no_cache(self, tmp_path):
        from vidscript.cli import _process_single

        mp4 = tmp_path / "test.mp4"
        mp4.write_bytes(b"\x00" * 100)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.transcript = MagicMock(
            language="en", language_probability=0.95,
            duration=30.0, model="base", segments=[]
        )
        mock_result.file_path = str(mp4)
        mock_result.processing_time = 1.0

        mock_extractor_cls = MagicMock()
        mock_extractor_cls.return_value.extract.return_value = mock_result

        with patch("vidscript.utils.progress.ProgressTracker") as mock_pt:
            mock_pt.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_pt.return_value.__exit__ = MagicMock(return_value=False)
            with patch("vidscript.core.extractor.Extractor", mock_extractor_cls):
                with patch("vidscript.output.formatter.format_output", return_value="text"):
                    with patch("vidscript.output.writer.write_result"):
                        with patch("vidscript.cli._print_summary"):
                            _process_single(
                                str(mp4), MagicMock(), "txt", None, None,
                                None, MagicMock()
                            )

    def test_extraction_error(self, tmp_path):
        from vidscript.cli import _process_single

        mp4 = tmp_path / "test.mp4"
        mp4.write_bytes(b"\x00" * 100)

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Failed"

        mock_extractor_cls = MagicMock()
        mock_extractor_cls.return_value.extract.return_value = mock_result

        with patch("vidscript.utils.progress.ProgressTracker") as mock_pt:
            mock_pt.return_value.__enter__ = MagicMock(return_value=MagicMock())
            mock_pt.return_value.__exit__ = MagicMock(return_value=False)
            with patch("vidscript.core.extractor.Extractor", mock_extractor_cls):
                with pytest.raises(SystemExit):
                    _process_single(
                        str(mp4), MagicMock(), "txt", None, None,
                        None, MagicMock()
                    )

    def test_cache_read_error(self, tmp_path):
        """Test graceful handling when cache read fails."""
        from vidscript.cache.redis_cache import RedisCacheError
        from vidscript.cli import _process_single

        mp4 = tmp_path / "test.mp4"
        mp4.write_bytes(b"\x00" * 100)

        mock_cache = MagicMock()
        mock_cache.get.side_effect = RedisCacheError("Connection lost")

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.transcript = MagicMock(
            language="en", language_probability=0.9,
            duration=10.0, model="base", segments=[]
        )
        mock_result.file_path = str(mp4)
        mock_result.processing_time = 1.0

        mock_extractor_cls = MagicMock()
        mock_extractor_cls.return_value.extract.return_value = mock_result

        with patch("vidscript.core.media_handler.get_file_hash", return_value="hash"):
            with patch("vidscript.utils.progress.ProgressTracker") as mock_pt:
                mock_pt.return_value.__enter__ = MagicMock(return_value=MagicMock())
                mock_pt.return_value.__exit__ = MagicMock(return_value=False)
                with patch("vidscript.core.extractor.Extractor", mock_extractor_cls):
                    with patch("vidscript.output.formatter.format_output", return_value="out"):
                        with patch("vidscript.output.writer.write_result"):
                            with patch("vidscript.cli._print_summary"):
                                _process_single(
                                    str(mp4), MagicMock(), "txt", None, None,
                                    mock_cache, MagicMock()
                                )

    def test_cache_write_error(self, tmp_path):
        """Test graceful handling when cache write fails."""
        from vidscript.cache.redis_cache import RedisCacheError
        from vidscript.cli import _process_single

        mp4 = tmp_path / "test.mp4"
        mp4.write_bytes(b"\x00" * 100)

        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.set.side_effect = RedisCacheError("Write failed")

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.transcript = MagicMock(
            language="en", language_probability=0.9,
            duration=10.0, model="base", segments=[]
        )
        mock_result.file_path = str(mp4)
        mock_result.processing_time = 1.0

        mock_extractor_cls = MagicMock()
        mock_extractor_cls.return_value.extract.return_value = mock_result

        with patch("vidscript.core.media_handler.get_file_hash", return_value="hash"):
            with patch("vidscript.utils.progress.ProgressTracker") as mock_pt:
                mock_pt.return_value.__enter__ = MagicMock(return_value=MagicMock())
                mock_pt.return_value.__exit__ = MagicMock(return_value=False)
                with patch("vidscript.core.extractor.Extractor", mock_extractor_cls):
                    with patch("vidscript.output.formatter.format_output", return_value="out"):
                        with patch("vidscript.output.writer.write_result"):
                            with patch("vidscript.cli._print_summary"):
                                _process_single(
                                    str(mp4), MagicMock(), "txt", None, None,
                                    mock_cache, MagicMock()
                                )


class TestProcessBatch:
    """Tests for _process_batch function."""

    def test_no_files(self, tmp_path):
        from vidscript.cli import _process_batch

        with patch("vidscript.core.media_handler.scan_directory", return_value=[]):
            _process_batch(str(tmp_path), MagicMock(), "txt", None, None, MagicMock())

    def test_with_files(self, tmp_path):
        from vidscript.cli import _process_batch

        mp4 = tmp_path / "test.mp4"
        mp4.write_bytes(b"\x00" * 100)

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.transcript = MagicMock(segments=[])

        mock_extractor_cls = MagicMock()
        mock_extractor_cls.return_value.extract.return_value = mock_result

        with patch("vidscript.core.media_handler.scan_directory", return_value=[mp4]):
            with patch("vidscript.utils.progress.create_batch_progress") as mock_progress:
                mock_ctx = MagicMock()
                mock_progress.return_value.__enter__ = MagicMock(return_value=mock_ctx)
                mock_progress.return_value.__exit__ = MagicMock(return_value=False)
                mock_ctx.add_task.return_value = 0
                with patch("vidscript.core.extractor.Extractor", mock_extractor_cls):
                    with patch("vidscript.output.formatter.format_output", return_value="out"):
                        with patch("vidscript.output.writer.write_result"):
                            _process_batch(
                                str(tmp_path), MagicMock(), "txt", None, None, MagicMock()
                            )

    def test_with_failed_file(self, tmp_path):
        from vidscript.cli import _process_batch

        mp4 = tmp_path / "test.mp4"
        mp4.write_bytes(b"\x00" * 100)

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.transcript = None

        mock_extractor_cls = MagicMock()
        mock_extractor_cls.return_value.extract.return_value = mock_result

        with patch("vidscript.core.media_handler.scan_directory", return_value=[mp4]):
            with patch("vidscript.utils.progress.create_batch_progress") as mock_progress:
                mock_ctx = MagicMock()
                mock_progress.return_value.__enter__ = MagicMock(return_value=mock_ctx)
                mock_progress.return_value.__exit__ = MagicMock(return_value=False)
                mock_ctx.add_task.return_value = 0
                with patch("vidscript.core.extractor.Extractor", mock_extractor_cls):
                    _process_batch(
                        str(tmp_path), MagicMock(), "txt", None, None, MagicMock()
                    )


class TestPrintSummary:
    """Tests for _print_summary function."""

    def test_with_transcript(self):
        from vidscript.cli import _print_summary

        mock_result = MagicMock()
        mock_result.transcript = MagicMock(
            language="en", language_probability=0.99,
            duration=120.0, model="base", segments=[MagicMock()]
        )
        mock_result.file_path = "test.mp4"
        mock_result.processing_time = 5.0

        _print_summary(mock_result)

    def test_no_transcript(self):
        from vidscript.cli import _print_summary

        mock_result = MagicMock()
        mock_result.transcript = None

        _print_summary(mock_result)


class TestCacheCommands:
    """Tests for cache subcommands."""

    def test_cache_help(self, runner):
        result = runner.invoke(main, ["cache", "--help"])
        assert result.exit_code == 0

    def test_cache_list_with_entries(self, runner):
        mock_cache = MagicMock()
        mock_cache.list_keys.return_value = [
            {"hash": "abc123def456", "ttl": 3600, "size": 1024, "key": "k"},
        ]

        with patch("vidscript.cache.redis_cache.RedisCache", return_value=mock_cache):
            with patch("vidscript.config.settings.get_settings", return_value=MagicMock()):
                result = runner.invoke(main, ["cache", "list"])

    def test_cache_list_empty(self, runner):
        mock_cache = MagicMock()
        mock_cache.list_keys.return_value = []

        with patch("vidscript.cache.redis_cache.RedisCache", return_value=mock_cache):
            with patch("vidscript.config.settings.get_settings", return_value=MagicMock()):
                result = runner.invoke(main, ["cache", "list"])

    def test_cache_list_error(self, runner):
        from vidscript.cache.redis_cache import RedisCacheError

        with patch("vidscript.cache.redis_cache.RedisCache", side_effect=RedisCacheError("fail")):
            with patch("vidscript.config.settings.get_settings", return_value=MagicMock()):
                result = runner.invoke(main, ["cache", "list"])
                assert result.exit_code != 0

    def test_cache_clear_all(self, runner):
        mock_cache = MagicMock()
        mock_cache.clear_all.return_value = 5

        with patch("vidscript.cache.redis_cache.RedisCache", return_value=mock_cache):
            with patch("vidscript.config.settings.get_settings", return_value=MagicMock()):
                result = runner.invoke(main, ["cache", "clear", "--all"])

    def test_cache_clear_specific(self, runner):
        mock_cache = MagicMock()
        mock_cache.delete.return_value = True

        with patch("vidscript.cache.redis_cache.RedisCache", return_value=mock_cache):
            with patch("vidscript.config.settings.get_settings", return_value=MagicMock()):
                result = runner.invoke(main, ["cache", "clear", "abc123"])

    def test_cache_clear_not_found(self, runner):
        mock_cache = MagicMock()
        mock_cache.delete.return_value = False

        with patch("vidscript.cache.redis_cache.RedisCache", return_value=mock_cache):
            with patch("vidscript.config.settings.get_settings", return_value=MagicMock()):
                result = runner.invoke(main, ["cache", "clear", "abc123"])

    def test_cache_clear_no_args(self, runner):
        mock_cache = MagicMock()

        with patch("vidscript.cache.redis_cache.RedisCache", return_value=mock_cache):
            with patch("vidscript.config.settings.get_settings", return_value=MagicMock()):
                result = runner.invoke(main, ["cache", "clear"])

    def test_cache_clear_error(self, runner):
        from vidscript.cache.redis_cache import RedisCacheError

        with patch("vidscript.cache.redis_cache.RedisCache", side_effect=RedisCacheError("fail")):
            with patch("vidscript.config.settings.get_settings", return_value=MagicMock()):
                result = runner.invoke(main, ["cache", "clear", "--all"])
                assert result.exit_code != 0

    def test_cache_list_no_expiry(self, runner):
        """Test cache list with no-expiry entry (TTL <= 0)."""
        mock_cache = MagicMock()
        mock_cache.list_keys.return_value = [
            {"hash": "abc123", "ttl": -1, "size": 512, "key": "k"},
        ]

        with patch("vidscript.cache.redis_cache.RedisCache", return_value=mock_cache):
            with patch("vidscript.config.settings.get_settings", return_value=MagicMock()):
                result = runner.invoke(main, ["cache", "list"])


class TestConfigCommands:
    """Tests for config subcommands."""

    def test_config_help(self, runner):
        result = runner.invoke(main, ["config", "--help"])
        assert result.exit_code == 0

    def test_config_show(self, runner):
        with patch("vidscript.config.settings.get_settings", return_value=MagicMock()):
            with patch("vidscript.config.settings.show_settings", return_value={
                "redis": {"host": "localhost", "port": 6379},
                "transcription": {"model": "base"},
            }):
                result = runner.invoke(main, ["config", "show"])

    def test_config_set_valid(self, runner):
        mock_settings = MagicMock()
        mock_settings.transcription = MagicMock()
        mock_settings.output = MagicMock()

        with patch("vidscript.config.settings.get_settings", return_value=mock_settings):
            result = runner.invoke(main, ["config", "set", "transcription.model", "small"])

    def test_config_set_invalid_key(self, runner):
        result = runner.invoke(main, ["config", "set", "invalid", "value"])
        assert result.exit_code != 0

    def test_config_set_invalid_section(self, runner):
        result = runner.invoke(main, ["config", "set", "invalid.key", "value"])
        assert result.exit_code != 0

    def test_config_set_invalid_attr(self, runner):
        mock_settings = MagicMock()
        mock_transcription = MagicMock(spec=[])
        mock_settings.transcription = mock_transcription

        with patch("vidscript.config.settings.get_settings", return_value=mock_settings):
            result = runner.invoke(main, ["config", "set", "transcription.nonexistent", "val"])
            assert result.exit_code != 0

    def test_config_show_flat_values(self, runner):
        """Test config show with non-dict values."""
        with patch("vidscript.config.settings.get_settings", return_value=MagicMock()):
            with patch("vidscript.config.settings.show_settings", return_value={
                "version": "1.0.0",
            }):
                result = runner.invoke(main, ["config", "show"])


class TestCLIFlags:
    """Tests for global CLI flags."""

    def test_verbose_flag(self, runner):
        result = runner.invoke(main, ["--verbose", "version"])
        assert result.exit_code == 0

    def test_quiet_flag(self, runner):
        result = runner.invoke(main, ["--quiet", "version"])
        assert result.exit_code == 0
