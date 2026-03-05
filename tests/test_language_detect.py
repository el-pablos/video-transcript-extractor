"""Tests for language_detect module."""

from unittest.mock import MagicMock, patch

import pytest

from vidscript.core.language_detect import (
    LANGUAGE_MAP,
    LanguageDetectError,
    detect_language_from_audio,
    detect_language_from_text,
    get_language_name,
    get_supported_languages,
    resolve_language,
    validate_language_code,
)


class TestDetectLanguageFromText:
    """Tests for detect_language_from_text."""

    @patch("vidscript.core.language_detect.detect_langs")
    def test_detect_english(self, mock_detect):
        """Test detecting English text."""
        mock_result = MagicMock()
        mock_result.lang = "en"
        mock_result.prob = 0.99
        mock_detect.return_value = [mock_result]

        lang, conf = detect_language_from_text("This is an English sentence.")
        assert lang == "en"
        assert conf == 0.99

    @patch("vidscript.core.language_detect.detect_langs")
    def test_detect_indonesian(self, mock_detect):
        """Test detecting Indonesian text."""
        mock_result = MagicMock()
        mock_result.lang = "id"
        mock_result.prob = 0.95
        mock_detect.return_value = [mock_result]

        lang, conf = detect_language_from_text("Ini adalah kalimat bahasa Indonesia.")
        assert lang == "id"

    def test_empty_text(self):
        """Test detection with empty text."""
        with pytest.raises(LanguageDetectError, match="Teks kosong"):
            detect_language_from_text("")

    def test_whitespace_text(self):
        """Test detection with whitespace-only text."""
        with pytest.raises(LanguageDetectError, match="Teks kosong"):
            detect_language_from_text("   ")

    @patch("vidscript.core.language_detect.detect_langs")
    def test_detect_no_results(self, mock_detect):
        """Test when langdetect returns no results."""
        mock_detect.return_value = []

        with pytest.raises(LanguageDetectError, match="Tidak ada hasil"):
            detect_language_from_text("test")


class TestDetectLanguageFromAudio:
    """Tests for detect_language_from_audio."""

    def test_detect_audio_import_error(self):
        """Test when faster_whisper is not available."""
        with patch.dict("sys.modules", {"faster_whisper": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                with pytest.raises(LanguageDetectError):
                    detect_language_from_audio("test.wav")

    @patch("vidscript.core.language_detect.WhisperModel", create=True)
    def test_detect_audio_success(self, mock_model_cls):
        """Test successful audio language detection."""
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.95

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([], mock_info)
        mock_model_cls.return_value = mock_model

        with patch.dict("sys.modules", {"faster_whisper": MagicMock(WhisperModel=mock_model_cls)}):
            lang, conf = detect_language_from_audio("test.wav")
            assert lang == "en"
            assert conf == 0.95


class TestGetLanguageName:
    """Tests for get_language_name."""

    def test_known_language(self):
        """Test getting name for known language code."""
        assert get_language_name("en") == "English"
        assert get_language_name("id") == "Indonesian"

    def test_unknown_language(self):
        """Test getting name for unknown code returns the code."""
        assert get_language_name("xx") == "xx"


class TestValidateLanguageCode:
    """Tests for validate_language_code."""

    def test_valid_code(self):
        """Test validation of valid language code."""
        assert validate_language_code("en") is True
        assert validate_language_code("id") is True

    def test_auto_code(self):
        """Test validation of 'auto' code."""
        assert validate_language_code("auto") is True

    def test_invalid_code(self):
        """Test validation of invalid language code."""
        assert validate_language_code("xyz") is False


class TestGetSupportedLanguages:
    """Tests for get_supported_languages."""

    def test_returns_list(self):
        """Test that supported languages are returned as list."""
        langs = get_supported_languages()
        assert isinstance(langs, list)
        assert len(langs) > 0
        assert all("code" in l and "name" in l for l in langs)

    def test_sorted_by_name(self):
        """Test that languages are sorted by name."""
        langs = get_supported_languages()
        names = [l["name"] for l in langs]
        assert names == sorted(names)


class TestResolveLanguage:
    """Tests for resolve_language."""

    def test_auto_returns_none(self):
        """Test that 'auto' resolves to None."""
        assert resolve_language("auto") is None

    def test_none_returns_none(self):
        """Test that None resolves to None."""
        assert resolve_language(None) is None

    def test_valid_code(self):
        """Test that valid code is returned as-is."""
        assert resolve_language("en") == "en"
        assert resolve_language("id") == "id"

    def test_invalid_code(self):
        """Test that invalid code raises error."""
        with pytest.raises(LanguageDetectError, match="tidak didukung"):
            resolve_language("xyz123")
