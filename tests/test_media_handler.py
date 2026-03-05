"""Tests for media_handler module."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vidscript.core.media_handler import (
    AudioExtractionError,
    FileNotFoundError_,
    InvalidFileError,
    MediaHandlerError,
    cleanup_temp_audio,
    extract_audio,
    get_file_hash,
    get_media_info,
    scan_directory,
    validate_file,
)


class TestValidateFile:
    """Tests for validate_file."""

    def test_valid_mp4_file(self, sample_mp4):
        """Test validation of a valid MP4 file."""
        result = validate_file(str(sample_mp4))
        assert result == sample_mp4

    def test_file_not_found(self):
        """Test validation of non-existent file."""
        with pytest.raises(FileNotFoundError_):
            validate_file("/nonexistent/path/video.mp4")

    def test_empty_file(self, empty_file):
        """Test validation of empty file."""
        with pytest.raises(InvalidFileError, match="File kosong"):
            validate_file(str(empty_file))

    def test_wrong_extension(self, non_mp4_file):
        """Test validation of non-MP4 file."""
        with pytest.raises(InvalidFileError, match="Ekstensi tidak didukung"):
            validate_file(str(non_mp4_file))

    def test_directory_instead_of_file(self, tmp_dir):
        """Test validation with directory path."""
        # Create a directory with .mp4 extension (edge case)
        dir_path = tmp_dir / "fake.mp4"
        dir_path.mkdir()
        with pytest.raises(InvalidFileError, match="Bukan sebuah file"):
            validate_file(str(dir_path))


class TestGetFileHash:
    """Tests for get_file_hash."""

    def test_sha256_hash(self, sample_mp4):
        """Test SHA256 hash generation."""
        hash_result = get_file_hash(str(sample_mp4), algorithm="sha256")
        assert isinstance(hash_result, str)
        assert len(hash_result) == 64  # SHA256 hex digest length

    def test_md5_hash(self, sample_mp4):
        """Test MD5 hash generation."""
        hash_result = get_file_hash(str(sample_mp4), algorithm="md5")
        assert isinstance(hash_result, str)
        assert len(hash_result) == 32  # MD5 hex digest length

    def test_same_file_same_hash(self, sample_mp4):
        """Test that same file produces same hash."""
        hash1 = get_file_hash(str(sample_mp4))
        hash2 = get_file_hash(str(sample_mp4))
        assert hash1 == hash2

    def test_different_files_different_hash(self, tmp_dir):
        """Test that different files produce different hashes."""
        file1 = tmp_dir / "file1.mp4"
        file2 = tmp_dir / "file2.mp4"
        file1.write_bytes(b"content1")
        file2.write_bytes(b"content2")
        hash1 = get_file_hash(str(file1))
        hash2 = get_file_hash(str(file2))
        assert hash1 != hash2


class TestGetMediaInfo:
    """Tests for get_media_info."""

    @patch("vidscript.core.media_handler.ffmpeg.probe")
    def test_successful_probe(self, mock_probe, sample_mp4):
        """Test successful media info retrieval."""
        mock_probe.return_value = {
            "format": {"format_name": "mov,mp4", "duration": "10.5", "size": "1024000"},
            "streams": [
                {"codec_type": "video", "codec_name": "h264"},
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "sample_rate": "44100",
                },
            ],
        }
        info = get_media_info(str(sample_mp4))
        assert info["has_video"] is True
        assert info["has_audio"] is True
        assert info["audio_channels"] == 2
        assert info["duration"] == 10.5

    @patch("vidscript.core.media_handler.ffmpeg.probe")
    def test_audio_only(self, mock_probe, sample_mp4):
        """Test media without video stream."""
        mock_probe.return_value = {
            "format": {"format_name": "mp3", "duration": "5.0", "size": "512000"},
            "streams": [
                {"codec_type": "audio", "codec_name": "mp3", "channels": 1, "sample_rate": "16000"},
            ],
        }
        info = get_media_info(str(sample_mp4))
        assert info["has_video"] is False
        assert info["has_audio"] is True

    @patch("vidscript.core.media_handler.ffmpeg.probe")
    def test_probe_error(self, mock_probe, sample_mp4):
        """Test handling of ffprobe errors."""
        mock_probe.side_effect = Exception("ffprobe failed")
        with pytest.raises(MediaHandlerError, match="Error saat probe media"):
            get_media_info(str(sample_mp4))


class TestExtractAudio:
    """Tests for extract_audio."""

    @patch("vidscript.core.media_handler.ffmpeg")
    def test_successful_extraction(self, mock_ffmpeg, sample_mp4, tmp_dir):
        """Test successful audio extraction."""
        output_path = str(tmp_dir / "output.wav")

        # Create the output file to simulate ffmpeg creating it
        Path(output_path).write_bytes(b"RIFF" + b"\x00" * 100)

        mock_stream = MagicMock()
        mock_ffmpeg.input.return_value = mock_stream
        mock_stream.output.return_value = mock_stream
        mock_stream.overwrite_output.return_value = mock_stream

        result = extract_audio(str(sample_mp4), output_path=output_path)
        assert result == output_path

    def test_invalid_file(self):
        """Test extraction from non-existent file."""
        with pytest.raises(FileNotFoundError_):
            extract_audio("/nonexistent/video.mp4")

    @patch("vidscript.core.media_handler.ffmpeg")
    def test_extraction_creates_empty_file(self, mock_ffmpeg, sample_mp4, tmp_dir):
        """Test handling when extraction creates empty file."""
        output_path = str(tmp_dir / "empty_output.wav")
        Path(output_path).write_bytes(b"")  # Empty file

        mock_stream = MagicMock()
        mock_ffmpeg.input.return_value = mock_stream
        mock_stream.output.return_value = mock_stream
        mock_stream.overwrite_output.return_value = mock_stream

        with pytest.raises(AudioExtractionError, match="kosong"):
            extract_audio(str(sample_mp4), output_path=output_path)


class TestScanDirectory:
    """Tests for scan_directory."""

    def test_scan_with_mp4_files(self, tmp_dir):
        """Test scanning directory with MP4 files."""
        (tmp_dir / "video1.mp4").write_bytes(b"data1")
        (tmp_dir / "video2.mp4").write_bytes(b"data2")
        (tmp_dir / "readme.txt").write_text("not a video")

        files = scan_directory(str(tmp_dir))
        assert len(files) == 2
        assert all(f.suffix == ".mp4" for f in files)

    def test_scan_empty_directory(self, tmp_dir):
        """Test scanning empty directory."""
        files = scan_directory(str(tmp_dir))
        assert len(files) == 0

    def test_scan_nonexistent_directory(self):
        """Test scanning non-existent directory."""
        with pytest.raises(FileNotFoundError_):
            scan_directory("/nonexistent/path")

    def test_scan_file_instead_of_directory(self, sample_mp4):
        """Test scanning a file path instead of directory."""
        with pytest.raises(InvalidFileError, match="Bukan sebuah direktori"):
            scan_directory(str(sample_mp4))

    def test_scan_recursive(self, tmp_dir):
        """Test recursive scanning."""
        sub_dir = tmp_dir / "subdir"
        sub_dir.mkdir()
        (tmp_dir / "root.mp4").write_bytes(b"data")
        (sub_dir / "child.mp4").write_bytes(b"data")

        files = scan_directory(str(tmp_dir), recursive=True)
        assert len(files) == 2

    def test_scan_ignores_empty_mp4(self, tmp_dir):
        """Test that empty MP4 files are ignored."""
        (tmp_dir / "empty.mp4").write_bytes(b"")
        (tmp_dir / "valid.mp4").write_bytes(b"data")

        files = scan_directory(str(tmp_dir))
        assert len(files) == 1


class TestCleanupTempAudio:
    """Tests for cleanup_temp_audio."""

    def test_cleanup_existing_file(self, tmp_dir):
        """Test cleanup of existing temp file."""
        temp_file = tmp_dir / "vidscript_test" / "audio.wav"
        temp_file.parent.mkdir(parents=True)
        temp_file.write_bytes(b"audio data")

        cleanup_temp_audio(str(temp_file))
        assert not temp_file.exists()

    def test_cleanup_nonexistent_file(self):
        """Test cleanup of non-existent file doesn't raise."""
        cleanup_temp_audio("/nonexistent/audio.wav")  # Should not raise
