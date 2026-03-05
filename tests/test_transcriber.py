"""Tests for transcriber module."""

from unittest.mock import MagicMock, patch

import pytest

from vidscript.core.transcriber import (
    AVAILABLE_MODELS,
    DEFAULT_MODEL,
    ModelLoadError,
    Transcriber,
    TranscriptionError,
    TranscriptResult,
    TranscriptSegment,
    WordSegment,
)


class TestWordSegment:
    """Tests for WordSegment dataclass."""

    def test_create_word_segment(self):
        """Test creating a WordSegment."""
        ws = WordSegment(word="hello", start=0.0, end=0.5, probability=0.95)
        assert ws.word == "hello"
        assert ws.start == 0.0
        assert ws.end == 0.5
        assert ws.probability == 0.95


class TestTranscriptSegment:
    """Tests for TranscriptSegment dataclass."""

    def test_create_segment(self):
        """Test creating a TranscriptSegment."""
        seg = TranscriptSegment(id=1, start=0.0, end=5.0, text="Hello world")
        assert seg.id == 1
        assert seg.text == "Hello world"
        assert seg.confidence == 0.0
        assert seg.speaker is None
        assert seg.words == []

    def test_create_segment_with_all_fields(self):
        """Test creating a segment with all fields populated."""
        words = [WordSegment(word="hi", start=0.0, end=0.3, probability=0.9)]
        seg = TranscriptSegment(
            id=1, start=0.0, end=1.0, text="hi",
            confidence=0.9, speaker="SPEAKER_00", words=words,
        )
        assert seg.speaker == "SPEAKER_00"
        assert len(seg.words) == 1


class TestTranscriptResult:
    """Tests for TranscriptResult dataclass."""

    def test_create_result(self, sample_transcript):
        """Test creating a TranscriptResult."""
        assert len(sample_transcript.segments) == 3
        assert sample_transcript.language == "en"
        assert sample_transcript.duration == 15.5
        assert sample_transcript.model == "base"


class TestTranscriber:
    """Tests for Transcriber class."""

    def test_init_valid_model(self):
        """Test initialization with valid model."""
        t = Transcriber(model_size="base")
        assert t.model_size == "base"
        assert t._model is None

    def test_init_invalid_model(self):
        """Test initialization with invalid model."""
        with pytest.raises(ValueError, match="tidak tersedia"):
            Transcriber(model_size="invalid_model")

    def test_available_models(self):
        """Test that expected models are available."""
        assert "tiny" in AVAILABLE_MODELS
        assert "base" in AVAILABLE_MODELS
        assert "small" in AVAILABLE_MODELS
        assert "medium" in AVAILABLE_MODELS
        assert "large-v3" in AVAILABLE_MODELS

    @patch("vidscript.core.transcriber.WhisperModel", create=True)
    def test_load_model(self, mock_whisper_cls):
        """Test lazy model loading."""
        mock_model = MagicMock()
        mock_whisper_cls.return_value = mock_model

        t = Transcriber(model_size="base")

        with patch("vidscript.core.transcriber.WhisperModel", mock_whisper_cls):
            # Simulate importing WhisperModel inside _load_model
            with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=mock_whisper_cls)}):
                t._load_model()

        assert t._model is not None

    def test_load_model_import_error(self):
        """Test model loading when faster_whisper is not installed."""
        t = Transcriber(model_size="base")

        with patch.dict("sys.modules", {"faster_whisper": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                with pytest.raises(ModelLoadError):
                    t._load_model()

    def test_transcribe_without_model(self):
        """Test transcription when model fails to load."""
        t = Transcriber(model_size="base")

        with patch.object(t, "_load_model", side_effect=ModelLoadError("Model error")):
            with pytest.raises(ModelLoadError):
                t.transcribe("test.wav")

    def test_transcribe_success(self):
        """Test successful transcription with mocked model."""
        t = Transcriber(model_size="base")

        # Create mock segment
        mock_word = MagicMock()
        mock_word.word = "hello"
        mock_word.start = 0.0
        mock_word.end = 0.5
        mock_word.probability = 0.95

        mock_segment = MagicMock()
        mock_segment.start = 0.0
        mock_segment.end = 2.0
        mock_segment.text = " hello world"
        mock_segment.words = [mock_word]
        mock_segment.avg_logprob = -0.3

        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.97
        mock_info.duration = 10.0

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        t._model = mock_model

        result = t.transcribe("test.wav", source_file="test.mp4")
        assert isinstance(result, TranscriptResult)
        assert result.language == "en"
        assert len(result.segments) == 1
        assert result.segments[0].text == "hello world"

    def test_transcribe_exception(self):
        """Test transcription error handling."""
        t = Transcriber(model_size="base")
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = RuntimeError("Transcription failed")
        t._model = mock_model

        with pytest.raises(TranscriptionError, match="Gagal melakukan transkripsi"):
            t.transcribe("test.wav")

    def test_close(self):
        """Test closing the transcriber."""
        t = Transcriber(model_size="base")
        t._model = MagicMock()
        t.close()
        assert t._model is None
