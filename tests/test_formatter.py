"""Tests for formatter module."""

import csv
import io
import json

import pytest

from vidscript.core.transcriber import TranscriptResult, TranscriptSegment, WordSegment
from vidscript.output.formatter import (
    SUPPORTED_FORMATS,
    FormatterError,
    format_csv,
    format_json,
    format_md,
    format_output,
    format_srt,
    format_timestamp_srt,
    format_timestamp_vtt,
    format_txt,
    format_vtt,
    get_file_extension,
)


class TestFormatTimestamp:
    """Tests for timestamp formatting functions."""

    def test_srt_timestamp_zero(self):
        """Test SRT format at zero seconds."""
        assert format_timestamp_srt(0.0) == "00:00:00,000"

    def test_srt_timestamp_with_millis(self):
        """Test SRT format with milliseconds."""
        assert format_timestamp_srt(3.5) == "00:00:03,500"

    def test_srt_timestamp_minutes(self):
        """Test SRT format with minutes."""
        assert format_timestamp_srt(125.75) == "00:02:05,750"

    def test_srt_timestamp_hours(self):
        """Test SRT format with hours."""
        assert format_timestamp_srt(3661.123) == "01:01:01,123"

    def test_vtt_timestamp_zero(self):
        """Test VTT format at zero seconds."""
        assert format_timestamp_vtt(0.0) == "00:00:00.000"

    def test_vtt_timestamp_with_millis(self):
        """Test VTT format with milliseconds."""
        assert format_timestamp_vtt(3.5) == "00:00:03.500"

    def test_vtt_uses_dot_separator(self):
        """Test VTT uses dot instead of comma."""
        result = format_timestamp_vtt(1.5)
        assert "." in result
        assert "," not in result


class TestFormatSrt:
    """Tests for SRT formatting."""

    def test_basic_srt(self, sample_transcript):
        """Test basic SRT output."""
        result = format_srt(sample_transcript)
        lines = result.strip().split("\n")

        assert lines[0] == "1"
        assert "-->" in lines[1]
        assert "Hello" in lines[2]

    def test_srt_with_speaker(self, sample_transcript):
        """Test SRT with speaker labels."""
        result = format_srt(sample_transcript)
        assert "[SPEAKER_00]" in result
        assert "[SPEAKER_01]" in result

    def test_srt_segment_count(self, sample_transcript):
        """Test that all segments are in SRT output."""
        result = format_srt(sample_transcript)
        assert "1\n" in result
        assert "2\n" in result
        assert "3\n" in result


class TestFormatVtt:
    """Tests for VTT formatting."""

    def test_vtt_header(self, sample_transcript):
        """Test VTT starts with WEBVTT header."""
        result = format_vtt(sample_transcript)
        assert result.startswith("WEBVTT")

    def test_vtt_timestamps(self, sample_transcript):
        """Test VTT uses correct timestamp format."""
        result = format_vtt(sample_transcript)
        assert "-->" in result
        # VTT uses dot, not comma
        assert "00:00:00.000" in result


class TestFormatTxt:
    """Tests for TXT formatting."""

    def test_plain_text(self, sample_transcript):
        """Test plain text output contains text."""
        result = format_txt(sample_transcript)
        assert "Hello, this is a test." in result
        assert "second segment" in result

    def test_no_timestamps_in_txt(self, sample_transcript):
        """Test that timestamps are not in plain text."""
        result = format_txt(sample_transcript)
        assert "-->" not in result

    def test_txt_with_speakers(self, sample_transcript):
        """Test plain text includes speaker labels."""
        result = format_txt(sample_transcript)
        assert "[SPEAKER_00]" in result


class TestFormatJson:
    """Tests for JSON formatting."""

    def test_valid_json(self, sample_transcript):
        """Test that output is valid JSON."""
        result = format_json(sample_transcript)
        data = json.loads(result)
        assert "metadata" in data
        assert "segments" in data

    def test_json_metadata(self, sample_transcript):
        """Test JSON metadata fields."""
        result = format_json(sample_transcript)
        data = json.loads(result)
        metadata = data["metadata"]
        assert metadata["language"] == "en"
        assert metadata["model"] == "base"
        assert metadata["total_segments"] == 3

    def test_json_segments_structure(self, sample_transcript):
        """Test JSON segments have correct structure."""
        result = format_json(sample_transcript)
        data = json.loads(result)
        seg = data["segments"][0]
        assert "id" in seg
        assert "start" in seg
        assert "end" in seg
        assert "text" in seg
        assert "speaker" in seg
        assert "confidence" in seg
        assert "words" in seg

    def test_json_words(self, sample_transcript):
        """Test JSON words detail."""
        result = format_json(sample_transcript)
        data = json.loads(result)
        words = data["segments"][0]["words"]
        assert len(words) > 0
        assert "word" in words[0]
        assert "probability" in words[0]


class TestFormatCsv:
    """Tests for CSV formatting."""

    def test_csv_header(self, sample_transcript):
        """Test CSV has correct header."""
        result = format_csv(sample_transcript)
        reader = csv.reader(io.StringIO(result))
        header = next(reader)
        assert header == ["start", "end", "speaker", "text", "confidence"]

    def test_csv_row_count(self, sample_transcript):
        """Test CSV has correct number of rows."""
        result = format_csv(sample_transcript)
        reader = csv.reader(io.StringIO(result))
        rows = list(reader)
        assert len(rows) == 4  # 1 header + 3 data rows

    def test_csv_data_values(self, sample_transcript):
        """Test CSV data values."""
        result = format_csv(sample_transcript)
        reader = csv.reader(io.StringIO(result))
        next(reader)  # Skip header
        first_row = next(reader)
        assert first_row[0] == "0.0"  # start
        assert first_row[3] == "Hello, this is a test."  # text


class TestFormatMd:
    """Tests for Markdown formatting."""

    def test_md_heading(self, sample_transcript):
        """Test Markdown has main heading."""
        result = format_md(sample_transcript)
        assert "# Transkrip:" in result

    def test_md_metadata(self, sample_transcript):
        """Test Markdown contains metadata."""
        result = format_md(sample_transcript)
        assert "**Bahasa:**" in result
        assert "**Durasi:**" in result
        assert "**Model:**" in result

    def test_md_table(self, sample_transcript):
        """Test Markdown contains table."""
        result = format_md(sample_transcript)
        assert "| # |" in result
        assert "|---|" in result

    def test_md_segment_data(self, sample_transcript):
        """Test Markdown table has segment data."""
        result = format_md(sample_transcript)
        assert "Hello, this is a test." in result


class TestFormatOutput:
    """Tests for format_output dispatcher."""

    def test_all_supported_formats(self, sample_transcript):
        """Test that all supported formats work."""
        for fmt in SUPPORTED_FORMATS:
            result = format_output(sample_transcript, fmt)
            assert isinstance(result, str)
            assert len(result) > 0

    def test_unsupported_format(self, sample_transcript):
        """Test error for unsupported format."""
        with pytest.raises(FormatterError, match="tidak didukung"):
            format_output(sample_transcript, "xml")

    def test_case_insensitive(self, sample_transcript):
        """Test format names are case-insensitive."""
        result = format_output(sample_transcript, "JSON")
        assert isinstance(result, str)

    def test_format_with_whitespace(self, sample_transcript):
        """Test format names with whitespace are trimmed."""
        result = format_output(sample_transcript, " txt ")
        assert isinstance(result, str)


class TestGetFileExtension:
    """Tests for get_file_extension."""

    def test_known_formats(self):
        """Test extensions for known formats."""
        assert get_file_extension("srt") == ".srt"
        assert get_file_extension("vtt") == ".vtt"
        assert get_file_extension("txt") == ".txt"
        assert get_file_extension("json") == ".json"
        assert get_file_extension("csv") == ".csv"
        assert get_file_extension("md") == ".md"

    def test_unknown_format_defaults_to_txt(self):
        """Test unknown format defaults to .txt."""
        assert get_file_extension("unknown") == ".txt"

    def test_case_insensitive(self):
        """Test case insensitivity."""
        assert get_file_extension("JSON") == ".json"
