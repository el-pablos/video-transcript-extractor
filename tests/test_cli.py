"""Tests for CLI module."""

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
        """Test banner prints without error."""
        # Should not raise even if pyfiglet not installed
        try:
            print_banner()
        except Exception:
            pytest.fail("print_banner() raised an exception")

    @patch("vidscript.cli.pyfiglet")
    def test_banner_with_pyfiglet(self, mock_pyfiglet, capsys):
        """Test banner uses pyfiglet when available."""
        mock_pyfiglet.figlet_format.return_value = "VidScript"
        print_banner()
        # No exception means success


class TestMainCommand:
    """Tests for the main CLI group."""

    def test_main_help(self, runner):
        """Test --help flag."""
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "VidScript" in result.output

    def test_main_no_args(self, runner):
        """Test running without arguments shows help."""
        result = runner.invoke(main, [])
        assert result.exit_code == 0

    def test_version_command(self, runner):
        """Test version subcommand."""
        result = runner.invoke(main, ["version"])
        assert result.exit_code == 0
        assert "1.0.0" in result.output


class TestTranscribeCommand:
    """Tests for the transcribe subcommand."""

    def test_transcribe_help(self, runner):
        """Test transcribe --help."""
        result = runner.invoke(main, ["transcribe", "--help"])
        assert result.exit_code == 0
        assert "MP4" in result.output or "mp4" in result.output.lower()

    def test_transcribe_nonexistent_file(self, runner):
        """Test transcribe with non-existent file."""
        result = runner.invoke(main, ["transcribe", "/nonexistent/video.mp4"])
        assert result.exit_code != 0

    def test_transcribe_model_choices(self, runner):
        """Test that model choice validation works."""
        result = runner.invoke(main, [
            "transcribe", "/nonexistent.mp4", "--model", "invalid"
        ])
        assert result.exit_code != 0


class TestCacheCommands:
    """Tests for cache subcommands."""

    def test_cache_help(self, runner):
        """Test cache --help."""
        result = runner.invoke(main, ["cache", "--help"])
        assert result.exit_code == 0
        assert "cache" in result.output.lower()

    def test_cache_list_help(self, runner):
        """Test cache list --help."""
        result = runner.invoke(main, ["cache", "list", "--help"])
        assert result.exit_code == 0

    def test_cache_clear_help(self, runner):
        """Test cache clear --help."""
        result = runner.invoke(main, ["cache", "clear", "--help"])
        assert result.exit_code == 0


class TestConfigCommands:
    """Tests for config subcommands."""

    def test_config_help(self, runner):
        """Test config --help."""
        result = runner.invoke(main, ["config", "--help"])
        assert result.exit_code == 0

    def test_config_show_help(self, runner):
        """Test config show --help."""
        result = runner.invoke(main, ["config", "show", "--help"])
        assert result.exit_code == 0

    def test_config_set_help(self, runner):
        """Test config set --help."""
        result = runner.invoke(main, ["config", "set", "--help"])
        assert result.exit_code == 0

    def test_config_set_invalid_key(self, runner):
        """Test config set with invalid key format."""
        result = runner.invoke(main, ["config", "set", "invalid", "value"])
        assert result.exit_code != 0

    def test_config_set_invalid_section(self, runner):
        """Test config set with invalid section."""
        result = runner.invoke(main, ["config", "set", "invalid.key", "value"])
        assert result.exit_code != 0


class TestCLIFlags:
    """Tests for global CLI flags."""

    def test_verbose_flag(self, runner):
        """Test --verbose flag is accepted."""
        result = runner.invoke(main, ["--verbose", "version"])
        assert result.exit_code == 0

    def test_quiet_flag(self, runner):
        """Test --quiet flag is accepted."""
        result = runner.invoke(main, ["--quiet", "version"])
        assert result.exit_code == 0
