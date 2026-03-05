"""Transcriber module — integrasi faster-whisper untuk speech-to-text."""

from dataclasses import dataclass, field
from typing import List, Optional


# Available Whisper models
AVAILABLE_MODELS = ["tiny", "base", "small", "medium", "large-v3"]

# Default model
DEFAULT_MODEL = "base"

# Default compute type
DEFAULT_COMPUTE_TYPE = "int8"


@dataclass
class WordSegment:
    """A single word with timing information."""
    word: str
    start: float
    end: float
    probability: float


@dataclass
class TranscriptSegment:
    """A single transcript segment with timing and metadata."""
    id: int
    start: float
    end: float
    text: str
    confidence: float = 0.0
    speaker: Optional[str] = None
    words: List[WordSegment] = field(default_factory=list)


@dataclass
class TranscriptResult:
    """Complete transcription result."""
    segments: List[TranscriptSegment]
    language: str
    language_probability: float
    duration: float
    model: str
    source_file: str


class TranscriberError(Exception):
    """Base exception for transcriber errors."""
    pass


class ModelLoadError(TranscriberError):
    """Raised when the Whisper model fails to load."""
    pass


class TranscriptionError(TranscriberError):
    """Raised when transcription fails."""
    pass


class Transcriber:
    """Whisper-based audio transcriber using faster-whisper.

    Args:
        model_size: Size of the Whisper model to use.
        device: Device to run inference on ('cpu', 'cuda', 'auto').
        compute_type: Compute type for inference ('int8', 'float16', 'float32').
    """

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL,
        device: str = "auto",
        compute_type: str = DEFAULT_COMPUTE_TYPE,
    ):
        if model_size not in AVAILABLE_MODELS:
            raise ValueError(
                f"Model '{model_size}' tidak tersedia. "
                f"Pilihan: {', '.join(AVAILABLE_MODELS)}"
            )

        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _load_model(self):
        """Load the faster-whisper model lazily."""
        if self._model is None:
            try:
                from faster_whisper import WhisperModel

                self._model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                )
            except Exception as e:
                raise ModelLoadError(
                    f"Gagal memuat model Whisper '{self.model_size}': {e}"
                )

    def transcribe(
        self,
        audio_path: str,
        language: Optional[str] = None,
        word_timestamps: bool = True,
        source_file: str = "",
    ) -> TranscriptResult:
        """Transcribe an audio file.

        Args:
            audio_path: Path to the audio file (WAV format preferred).
            language: Language code (e.g., 'en', 'id') or None for auto-detect.
            word_timestamps: Whether to include word-level timestamps.
            source_file: Original source file path for metadata.

        Returns:
            TranscriptResult with all segments and metadata.

        Raises:
            TranscriptionError: If transcription fails.
        """
        self._load_model()

        try:
            segments_gen, info = self._model.transcribe(
                audio_path,
                language=language,
                word_timestamps=word_timestamps,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                ),
            )

            segments = []
            for idx, segment in enumerate(segments_gen):
                words = []
                if segment.words:
                    for w in segment.words:
                        words.append(WordSegment(
                            word=w.word.strip(),
                            start=round(w.start, 3),
                            end=round(w.end, 3),
                            probability=round(w.probability, 4),
                        ))

                avg_confidence = 0.0
                if words:
                    avg_confidence = sum(w.probability for w in words) / len(words)
                elif hasattr(segment, "avg_logprob"):
                    # Convert log probability to probability
                    import math
                    avg_confidence = math.exp(segment.avg_logprob)

                segments.append(TranscriptSegment(
                    id=idx + 1,
                    start=round(segment.start, 3),
                    end=round(segment.end, 3),
                    text=segment.text.strip(),
                    confidence=round(avg_confidence, 4),
                    words=words,
                ))

            return TranscriptResult(
                segments=segments,
                language=info.language,
                language_probability=round(info.language_probability, 4),
                duration=round(info.duration, 3),
                model=self.model_size,
                source_file=source_file,
            )

        except TranscriberError:
            raise
        except Exception as e:
            raise TranscriptionError(f"Gagal melakukan transkripsi: {e}")

    def close(self):
        """Release model resources."""
        self._model = None
