"""Language detection module — deteksi bahasa otomatis dari audio dan teks."""

from typing import Dict, List, Optional, Tuple

# Language code mapping for common languages
LANGUAGE_MAP = {
    "id": "Indonesian",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "hi": "Hindi",
    "pt": "Portuguese",
    "ru": "Russian",
    "it": "Italian",
    "nl": "Dutch",
    "tr": "Turkish",
    "pl": "Polish",
    "th": "Thai",
    "vi": "Vietnamese",
    "ms": "Malay",
    "sv": "Swedish",
}

# Supported language codes for Whisper
WHISPER_LANGUAGES = list(LANGUAGE_MAP.keys())


class LanguageDetectError(Exception):
    """Base exception for language detection errors."""
    pass


def detect_language_from_text(text: str) -> Tuple[str, float]:
    """Detect language from text using langdetect library.

    Args:
        text: Input text to analyze.

    Returns:
        Tuple of (language_code, confidence_score).

    Raises:
        LanguageDetectError: If detection fails.
    """
    if not text or not text.strip():
        raise LanguageDetectError("Teks kosong, tidak bisa mendeteksi bahasa")

    try:
        from langdetect import detect_langs
        from langdetect.lang_detect_exception import LangDetectException

        results = detect_langs(text)
        if results:
            best = results[0]
            return str(best.lang), round(float(best.prob), 4)

        raise LanguageDetectError("Tidak ada hasil deteksi bahasa")

    except LangDetectException as e:
        raise LanguageDetectError(f"Gagal mendeteksi bahasa dari teks: {e}")
    except ImportError:
        raise LanguageDetectError("Library 'langdetect' belum terinstall")


def detect_language_from_audio(audio_path: str, model_size: str = "base") -> Tuple[str, float]:
    """Detect language from audio using faster-whisper.

    Uses the first 30 seconds of audio for fast detection.

    Args:
        audio_path: Path to the audio file.
        model_size: Whisper model size for detection.

    Returns:
        Tuple of (language_code, confidence_score).

    Raises:
        LanguageDetectError: If detection fails.
    """
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(model_size, device="auto", compute_type="int8")
        _, info = model.transcribe(audio_path, language=None)

        return info.language, round(info.language_probability, 4)

    except ImportError:
        raise LanguageDetectError("Library 'faster-whisper' belum terinstall")
    except Exception as e:
        raise LanguageDetectError(f"Gagal mendeteksi bahasa dari audio: {e}")


def get_language_name(code: str) -> str:
    """Get full language name from language code.

    Args:
        code: ISO 639-1 language code.

    Returns:
        Full language name, or code if not found.
    """
    return LANGUAGE_MAP.get(code, code)


def validate_language_code(code: str) -> bool:
    """Check if a language code is supported.

    Args:
        code: Language code to validate.

    Returns:
        True if the language code is supported.
    """
    if code == "auto":
        return True
    return code in LANGUAGE_MAP


def get_supported_languages() -> List[Dict[str, str]]:
    """Get list of all supported languages.

    Returns:
        List of dicts with 'code' and 'name' keys.
    """
    return [
        {"code": code, "name": name}
        for code, name in sorted(LANGUAGE_MAP.items(), key=lambda x: x[1])
    ]


def resolve_language(language: Optional[str]) -> Optional[str]:
    """Resolve language parameter for transcription.

    Args:
        language: Language code, 'auto', or None.

    Returns:
        Language code string or None for auto-detection.
    """
    if language is None or language == "auto":
        return None
    if validate_language_code(language):
        return language
    raise LanguageDetectError(
        f"Kode bahasa '{language}' tidak didukung. "
        f"Gunakan 'auto' atau salah satu dari: {', '.join(sorted(LANGUAGE_MAP.keys()))}"
    )
