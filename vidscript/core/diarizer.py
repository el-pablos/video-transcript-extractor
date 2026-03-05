"""Speaker diarization module — pemisahan pembicara menggunakan pyannote.audio."""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from vidscript.core.transcriber import TranscriptResult, TranscriptSegment


@dataclass
class SpeakerSegment:
    """A segment with speaker identification."""
    speaker: str
    start: float
    end: float


class DiarizationError(Exception):
    """Base exception for diarization errors."""
    pass


class DiarizationPipelineError(DiarizationError):
    """Raised when the diarization pipeline fails to load."""
    pass


class Diarizer:
    """Speaker diarization using pyannote.audio.

    Args:
        auth_token: HuggingFace token for pyannote model access.
        min_speakers: Minimum number of expected speakers.
        max_speakers: Maximum number of expected speakers.
    """

    def __init__(
        self,
        auth_token: Optional[str] = None,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
    ):
        self.auth_token = auth_token
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self._pipeline = None

    def _load_pipeline(self):
        """Load the pyannote diarization pipeline lazily."""
        if self._pipeline is None:
            try:
                from pyannote.audio import Pipeline

                self._pipeline = Pipeline.from_pretrained(
                    "pyannote/speaker-diarization-3.1",
                    use_auth_token=self.auth_token,
                )
            except ImportError:
                raise DiarizationPipelineError(
                    "Library 'pyannote.audio' belum terinstall. "
                    "Install dengan: pip install pyannote.audio"
                )
            except Exception as e:
                raise DiarizationPipelineError(
                    f"Gagal memuat pipeline diarization: {e}"
                )

    def diarize(self, audio_path: str) -> List[SpeakerSegment]:
        """Perform speaker diarization on an audio file.

        Args:
            audio_path: Path to the audio file.

        Returns:
            List of SpeakerSegment with speaker labels and timestamps.

        Raises:
            DiarizationError: If diarization fails.
        """
        self._load_pipeline()

        try:
            params = {}
            if self.min_speakers is not None:
                params["min_speakers"] = self.min_speakers
            if self.max_speakers is not None:
                params["max_speakers"] = self.max_speakers

            diarization = self._pipeline(audio_path, **params)

            segments = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                segments.append(SpeakerSegment(
                    speaker=speaker,
                    start=round(turn.start, 3),
                    end=round(turn.end, 3),
                ))

            return segments

        except DiarizationError:
            raise
        except Exception as e:
            raise DiarizationError(f"Gagal melakukan diarization: {e}")

    def close(self):
        """Release pipeline resources."""
        self._pipeline = None


def assign_speakers(
    transcript: TranscriptResult,
    speaker_segments: List[SpeakerSegment],
) -> TranscriptResult:
    """Assign speaker labels to transcript segments based on timestamp overlap.

    Each transcript segment is assigned the speaker with the most overlap.

    Args:
        transcript: The transcription result.
        speaker_segments: List of diarization speaker segments.

    Returns:
        Updated TranscriptResult with speaker labels assigned.
    """
    if not speaker_segments:
        return transcript

    for segment in transcript.segments:
        segment.speaker = _find_best_speaker(
            segment.start, segment.end, speaker_segments
        )

    return transcript


def _find_best_speaker(
    start: float,
    end: float,
    speaker_segments: List[SpeakerSegment],
) -> str:
    """Find the speaker with the most overlap for a given time range.

    Args:
        start: Start time of the segment.
        end: End time of the segment.
        speaker_segments: List of speaker segments from diarization.

    Returns:
        Speaker label (e.g., 'SPEAKER_00').
    """
    speaker_overlap: Dict[str, float] = {}

    for ss in speaker_segments:
        overlap_start = max(start, ss.start)
        overlap_end = min(end, ss.end)
        overlap = max(0.0, overlap_end - overlap_start)

        if overlap > 0:
            speaker_overlap[ss.speaker] = (
                speaker_overlap.get(ss.speaker, 0.0) + overlap
            )

    if not speaker_overlap:
        return "SPEAKER_UNKNOWN"

    best_speaker = max(speaker_overlap, key=speaker_overlap.get)
    return best_speaker


def format_speaker_label(speaker: str) -> str:
    """Format a speaker label for display.

    Converts pyannote labels like 'SPEAKER_00' to '[SPEAKER_00]' format.

    Args:
        speaker: Raw speaker label.

    Returns:
        Formatted speaker label with brackets.
    """
    if not speaker:
        return ""
    if not speaker.startswith("["):
        return f"[{speaker}]"
    return speaker
