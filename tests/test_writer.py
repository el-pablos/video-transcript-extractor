"""Tests for writer module."""

import os
from pathlib import Path

import pytest

from vidscript.output.writer import (
    WriterError,
    generate_output_path,
    write_result,
    write_to_file,
    write_to_stdout,
)


class TestWriteToFile:
    """Tests for write_to_file."""

    def test_write_basic(self, tmp_dir):
        """Test basic file writing."""
        output = tmp_dir / "output.txt"
        result = write_to_file("Hello World", str(output))
        assert Path(result).exists()
        assert Path(result).read_text(encoding="utf-8") == "Hello World"

    def test_write_creates_directory(self, tmp_dir):
        """Test that parent directories are created."""
        output = tmp_dir / "subdir" / "deep" / "output.txt"
        write_to_file("content", str(output))
        assert output.exists()

    def test_write_overwrite(self, tmp_dir):
        """Test overwriting existing file."""
        output = tmp_dir / "output.txt"
        output.write_text("old content")
        write_to_file("new content", str(output), overwrite=True)
        assert output.read_text() == "new content"

    def test_write_no_overwrite(self, tmp_dir):
        """Test refusing to overwrite existing file."""
        output = tmp_dir / "output.txt"
        output.write_text("old content")
        with pytest.raises(WriterError, match="overwrite=False"):
            write_to_file("new content", str(output), overwrite=False)

    def test_write_utf8(self, tmp_dir):
        """Test writing UTF-8 content."""
        output = tmp_dir / "output.txt"
        content = "Ini bahasa Indonesia: belajar itu menyenangkan 🎉"
        write_to_file(content, str(output))
        assert output.read_text(encoding="utf-8") == content


class TestWriteToStdout:
    """Tests for write_to_stdout."""

    def test_write_stdout(self, capsys):
        """Test writing to stdout."""
        write_to_stdout("Hello stdout")
        captured = capsys.readouterr()
        assert "Hello stdout" in captured.out

    def test_write_stdout_adds_newline(self, capsys):
        """Test that missing newline is added."""
        write_to_stdout("no newline")
        captured = capsys.readouterr()
        assert captured.out.endswith("\n")


class TestGenerateOutputPath:
    """Tests for generate_output_path."""

    def test_default_directory(self):
        """Test path generation in source directory."""
        result = generate_output_path("/path/to/video.mp4", "srt")
        assert result.endswith("video.srt")
        assert "/path/to/" in result.replace("\\", "/")

    def test_custom_output_dir(self, tmp_dir):
        """Test path generation with custom directory."""
        result = generate_output_path("/path/to/video.mp4", "json", str(tmp_dir))
        assert result.endswith("video.json")
        assert str(tmp_dir) in result

    def test_different_formats(self):
        """Test path generation with different formats."""
        for fmt, ext in [("srt", ".srt"), ("vtt", ".vtt"), ("json", ".json")]:
            result = generate_output_path("video.mp4", fmt)
            assert result.endswith(ext)


class TestWriteResult:
    """Tests for write_result."""

    def test_write_to_explicit_path(self, tmp_dir):
        """Test writing to explicit output path."""
        output = str(tmp_dir / "result.txt")
        result = write_result("content", output_path=output)
        assert result is not None
        assert Path(result).exists()

    def test_write_to_generated_path(self, tmp_dir):
        """Test writing with auto-generated path."""
        source = str(tmp_dir / "video.mp4")
        Path(source).write_bytes(b"fake mp4")

        result = write_result(
            "content",
            source_file=source,
            output_format="txt",
        )
        assert result is not None
        assert result.endswith(".txt")

    def test_write_to_stdout(self, capsys):
        """Test writing to stdout when no path given."""
        result = write_result("stdout content")
        assert result is None
        captured = capsys.readouterr()
        assert "stdout content" in captured.out
