"""Tests for extractor module."""

from unittest.mock import MagicMock, patch

import pytest

from vidscript.core.extractor import (
    ExtractionOptions,
    ExtractionResult,
    Extractor,
)
from vidscript.core.transcriber import TranscriptResult, TranscriptSegment


class TestExtractionOptions:
    """Tests for ExtractionOptions dataclass."""

    def test_defaults(self):
        """Test default options."""
        opts = ExtractionOptions()
        assert opts.model == "base"
        assert opts.language is None
        assert opts.diarize is False
        assert opts.device == "auto"

    def test_custom_options(self):
        """Test custom options."""
        opts = ExtractionOptions(model="large-v3", language="id", diarize=True)
        assert opts.model == "large-v3"
        assert opts.language == "id"
        assert opts.diarize is True


class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_defaults(self):
        """Test default result values."""
        result = ExtractionResult(file_path="test.mp4", file_hash="abc123")
        assert result.success is True
        assert result.error is None
        assert result.cache_hit is False

    def test_error_result(self):
        """Test error result."""
        result = ExtractionResult(
            file_path="test.mp4", file_hash="",
            error="Something failed", success=False,
        )
        assert result.success is False
        assert result.error == "Something failed"


class TestExtractor:
    """Tests for Extractor class."""

    def test_init_default(self):
        """Test default initialization."""
        ext = Extractor()
        assert ext.options.model == "base"
        assert ext.progress_callback is None

    def test_init_with_options(self):
        """Test initialization with custom options."""
        opts = ExtractionOptions(model="small")
        ext = Extractor(options=opts)
        assert ext.options.model == "small"

    def test_progress_callback(self):
        """Test progress callback is called."""
        callback = MagicMock()
        ext = Extractor(progress_callback=callback)
        ext._report_progress("test", 0.5, "testing")
        callback.assert_called_once_with("test", 0.5, "testing")

    @patch("vidscript.core.extractor.validate_file")
    @patch("vidscript.core.extractor.get_file_hash")
    @patch("vidscript.core.extractor.get_media_info")
    @patch("vidscript.core.extractor.extract_audio")
    @patch("vidscript.core.extractor.cleanup_temp_audio")
    def test_extract_success(
        self, mock_cleanup, mock_extract, mock_info, mock_hash, mock_validate
    ):
        """Test successful extraction pipeline."""
        from pathlib import Path

        mock_validate.return_value = Path("test.mp4")
        mock_hash.return_value = "abc123hash"
        mock_info.return_value = {"duration": 10.0}
        mock_extract.return_value = "/tmp/audio.wav"

        # Mock the transcriber
        mock_transcript = TranscriptResult(
            segments=[TranscriptSegment(id=1, start=0.0, end=5.0, text="Hello")],
            language="en",
            language_probability=0.95,
            duration=10.0,
            model="base",
            source_file="test.mp4",
        )

        ext = Extractor()
        mock_transcriber = MagicMock()
        mock_transcriber.transcribe.return_value = mock_transcript
        ext._transcriber = mock_transcriber

        result = ext.extract("test.mp4")

        assert result.success is True
        assert result.file_hash == "abc123hash"
        assert result.transcript is not None
        assert result.transcript.language == "en"
        mock_cleanup.assert_called_once_with("/tmp/audio.wav")

    @patch("vidscript.core.extractor.validate_file")
    def test_extract_invalid_file(self, mock_validate):
        """Test extraction with invalid file."""
        from vidscript.core.media_handler import FileNotFoundError_
        mock_validate.side_effect = FileNotFoundError_("File not found")

        ext = Extractor()
        result = ext.extract("nonexistent.mp4")

        assert result.success is False
        assert "File not found" in result.error

    @patch("vidscript.core.extractor.scan_directory")
    def test_extract_batch_empty(self, mock_scan):
        """Test batch extraction with empty directory."""
        mock_scan.return_value = []
        ext = Extractor()
        results = ext.extract_batch("/empty/dir")
        assert len(results) == 0

    @patch("vidscript.core.extractor.scan_directory")
    @patch.object(Extractor, "extract")
    def test_extract_batch_multiple(self, mock_extract, mock_scan):
        """Test batch extraction with multiple files."""
        from pathlib import Path

        mock_scan.return_value = [Path("video1.mp4"), Path("video2.mp4")]
        mock_extract.return_value = ExtractionResult(
            file_path="video.mp4", file_hash="hash", success=True,
        )

        ext = Extractor()
        results = ext.extract_batch("/videos/")

        assert len(results) == 2
        assert mock_extract.call_count == 2

    def test_close(self):
        """Test closing extractor releases resources."""
        ext = Extractor()
        ext._transcriber = MagicMock()
        ext._diarizer = MagicMock()
        ext.close()
        assert ext._transcriber is None
        assert ext._diarizer is None
