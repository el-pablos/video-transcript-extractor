"""Tests for diarizer module."""

from unittest.mock import MagicMock, patch

import pytest

from vidscript.core.diarizer import (
    Diarizer,
    DiarizationError,
    DiarizationPipelineError,
    SpeakerSegment,
    _find_best_speaker,
    assign_speakers,
    format_speaker_label,
)
from vidscript.core.transcriber import TranscriptResult, TranscriptSegment


class TestSpeakerSegment:
    """Tests for SpeakerSegment dataclass."""

    def test_create_speaker_segment(self):
        """Test creating a SpeakerSegment."""
        seg = SpeakerSegment(speaker="SPEAKER_00", start=0.0, end=5.0)
        assert seg.speaker == "SPEAKER_00"
        assert seg.start == 0.0
        assert seg.end == 5.0


class TestDiarizer:
    """Tests for Diarizer class."""

    def test_init(self):
        """Test Diarizer initialization."""
        d = Diarizer(auth_token="test_token")
        assert d.auth_token == "test_token"
        assert d._pipeline is None

    def test_load_pipeline_import_error(self):
        """Test pipeline loading when pyannote is not available."""
        d = Diarizer()
        with patch.dict("sys.modules", {"pyannote.audio": None, "pyannote": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                with pytest.raises(DiarizationPipelineError):
                    d._load_pipeline()

    def test_diarize_success(self):
        """Test successful diarization with mocked pipeline."""
        d = Diarizer()

        # Create mock turn objects
        mock_turn1 = MagicMock()
        mock_turn1.start = 0.0
        mock_turn1.end = 3.0

        mock_turn2 = MagicMock()
        mock_turn2.start = 3.5
        mock_turn2.end = 7.0

        mock_pipeline = MagicMock()
        mock_result = MagicMock()
        mock_result.itertracks.return_value = [
            (mock_turn1, None, "SPEAKER_00"),
            (mock_turn2, None, "SPEAKER_01"),
        ]
        mock_pipeline.return_value = mock_result
        d._pipeline = mock_pipeline

        segments = d.diarize("test.wav")
        assert len(segments) == 2
        assert segments[0].speaker == "SPEAKER_00"
        assert segments[1].speaker == "SPEAKER_01"

    def test_diarize_error(self):
        """Test diarization error handling."""
        d = Diarizer()
        mock_pipeline = MagicMock()
        mock_pipeline.side_effect = RuntimeError("Pipeline failed")
        d._pipeline = mock_pipeline

        with pytest.raises(DiarizationError, match="Gagal melakukan diarization"):
            d.diarize("test.wav")

    def test_close(self):
        """Test closing the diarizer."""
        d = Diarizer()
        d._pipeline = MagicMock()
        d.close()
        assert d._pipeline is None


class TestAssignSpeakers:
    """Tests for assign_speakers."""

    def test_assign_speakers_basic(self, sample_transcript):
        """Test basic speaker assignment."""
        speaker_segments = [
            SpeakerSegment(speaker="SPEAKER_00", start=0.0, end=4.0),
            SpeakerSegment(speaker="SPEAKER_01", start=4.0, end=10.0),
        ]

        result = assign_speakers(sample_transcript, speaker_segments)
        assert result.segments[0].speaker == "SPEAKER_00"
        assert result.segments[1].speaker == "SPEAKER_01"

    def test_assign_speakers_empty_segments(self, sample_transcript):
        """Test with empty speaker segments."""
        result = assign_speakers(sample_transcript, [])
        # Should keep original speakers in the transcript
        assert result is sample_transcript

    def test_assign_speakers_no_overlap(self):
        """Test assignment when no overlap exists."""
        segments = [
            TranscriptSegment(id=1, start=100.0, end=105.0, text="Far away"),
        ]
        transcript = TranscriptResult(
            segments=segments, language="en", language_probability=0.9,
            duration=105.0, model="base", source_file="test.mp4",
        )
        speaker_segments = [
            SpeakerSegment(speaker="SPEAKER_00", start=0.0, end=5.0),
        ]

        result = assign_speakers(transcript, speaker_segments)
        assert result.segments[0].speaker == "SPEAKER_UNKNOWN"


class TestFindBestSpeaker:
    """Tests for _find_best_speaker."""

    def test_single_speaker_overlap(self):
        """Test finding speaker with single overlap."""
        speaker_segments = [
            SpeakerSegment(speaker="SPEAKER_00", start=0.0, end=5.0),
        ]
        result = _find_best_speaker(1.0, 3.0, speaker_segments)
        assert result == "SPEAKER_00"

    def test_multiple_speakers_best_overlap(self):
        """Test finding speaker with most overlap."""
        speaker_segments = [
            SpeakerSegment(speaker="SPEAKER_00", start=0.0, end=3.0),
            SpeakerSegment(speaker="SPEAKER_01", start=2.0, end=8.0),
        ]
        # Segment from 2.5 to 6.0: SPEAKER_00 overlap=0.5, SPEAKER_01 overlap=3.5
        result = _find_best_speaker(2.5, 6.0, speaker_segments)
        assert result == "SPEAKER_01"

    def test_no_overlap(self):
        """Test when no speaker overlaps."""
        speaker_segments = [
            SpeakerSegment(speaker="SPEAKER_00", start=10.0, end=15.0),
        ]
        result = _find_best_speaker(0.0, 5.0, speaker_segments)
        assert result == "SPEAKER_UNKNOWN"


class TestFormatSpeakerLabel:
    """Tests for format_speaker_label."""

    def test_format_regular_label(self):
        """Test formatting a regular speaker label."""
        assert format_speaker_label("SPEAKER_00") == "[SPEAKER_00]"

    def test_format_already_bracketed(self):
        """Test formatting an already bracketed label."""
        assert format_speaker_label("[SPEAKER_00]") == "[SPEAKER_00]"

    def test_format_empty_label(self):
        """Test formatting an empty label."""
        assert format_speaker_label("") == ""

    def test_format_none_label(self):
        """Test formatting None (via empty string)."""
        assert format_speaker_label("") == ""
