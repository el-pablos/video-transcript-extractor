"""Extractor module — orchestrator utama yang mengkoordinasi semua proses transkripsi."""

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

from vidscript.core.diarizer import Diarizer, SpeakerSegment, assign_speakers
from vidscript.core.language_detect import resolve_language
from vidscript.core.media_handler import (
    cleanup_temp_audio,
    extract_audio,
    get_file_hash,
    get_media_info,
    scan_directory,
    validate_file,
)
from vidscript.core.transcriber import Transcriber, TranscriptResult


@dataclass
class ExtractionOptions:
    """Options for the extraction process."""
    model: str = "base"
    language: Optional[str] = None
    diarize: bool = False
    diarize_token: Optional[str] = None
    min_speakers: Optional[int] = None
    max_speakers: Optional[int] = None
    word_timestamps: bool = True
    device: str = "auto"
    compute_type: str = "int8"


@dataclass
class ExtractionResult:
    """Result of a single file extraction."""
    file_path: str
    file_hash: str
    transcript: Optional[TranscriptResult] = None
    speaker_segments: Optional[List[SpeakerSegment]] = None
    media_info: Optional[Dict] = None
    processing_time: float = 0.0
    cache_hit: bool = False
    error: Optional[str] = None
    success: bool = True


class ExtractorError(Exception):
    """Base exception for extractor errors."""
    pass


class Extractor:
    """Main orchestrator for the extraction pipeline.

    Coordinates media handling, transcription, and diarization.

    Args:
        options: Extraction options configuration.
        progress_callback: Optional callback for progress updates.
            Receives (step_name: str, progress: float, message: str).
    """

    def __init__(
        self,
        options: Optional[ExtractionOptions] = None,
        progress_callback: Optional[Callable] = None,
    ):
        self.options = options or ExtractionOptions()
        self.progress_callback = progress_callback
        self._transcriber = None
        self._diarizer = None

    def _report_progress(self, step: str, progress: float, message: str = ""):
        """Report progress to the callback if set."""
        if self.progress_callback:
            self.progress_callback(step, progress, message)

    def _get_transcriber(self) -> Transcriber:
        """Get or create the transcriber instance."""
        if self._transcriber is None:
            self._transcriber = Transcriber(
                model_size=self.options.model,
                device=self.options.device,
                compute_type=self.options.compute_type,
            )
        return self._transcriber

    def _get_diarizer(self) -> Diarizer:
        """Get or create the diarizer instance."""
        if self._diarizer is None:
            self._diarizer = Diarizer(
                auth_token=self.options.diarize_token,
                min_speakers=self.options.min_speakers,
                max_speakers=self.options.max_speakers,
            )
        return self._diarizer

    def extract(self, file_path: str) -> ExtractionResult:
        """Extract transcript from a single MP4 file.

        Args:
            file_path: Path to the MP4 file.

        Returns:
            ExtractionResult with transcript and metadata.
        """
        start_time = time.time()
        audio_path = None

        try:
            # Step 1: Validate file
            self._report_progress("validate", 0.05, f"Validasi file: {file_path}")
            validated_path = validate_file(file_path)

            # Step 2: Get file hash for caching
            self._report_progress("hash", 0.10, "Menghitung hash file...")
            file_hash = get_file_hash(str(validated_path))

            # Step 3: Get media info
            self._report_progress("probe", 0.15, "Membaca info media...")
            try:
                media_info = get_media_info(str(validated_path))
            except Exception:
                media_info = None

            # Step 4: Extract audio from MP4
            self._report_progress("extract_audio", 0.25, "Mengekstrak audio dari MP4...")
            audio_path = extract_audio(str(validated_path))

            # Step 5: Resolve language
            language = resolve_language(self.options.language)

            # Step 6: Transcribe audio
            self._report_progress("transcribe", 0.40, "Mentranskripsi audio...")
            transcriber = self._get_transcriber()
            transcript = transcriber.transcribe(
                audio_path=audio_path,
                language=language,
                word_timestamps=self.options.word_timestamps,
                source_file=str(validated_path),
            )

            # Step 7: Speaker diarization (optional)
            speaker_segments = None
            if self.options.diarize:
                self._report_progress("diarize", 0.75, "Melakukan speaker diarization...")
                diarizer = self._get_diarizer()
                speaker_segments = diarizer.diarize(audio_path)
                transcript = assign_speakers(transcript, speaker_segments)

            self._report_progress("done", 1.0, "Selesai!")

            processing_time = time.time() - start_time

            return ExtractionResult(
                file_path=str(validated_path),
                file_hash=file_hash,
                transcript=transcript,
                speaker_segments=speaker_segments,
                media_info=media_info,
                processing_time=round(processing_time, 3),
            )

        except Exception as e:
            processing_time = time.time() - start_time
            return ExtractionResult(
                file_path=file_path,
                file_hash="",
                processing_time=round(processing_time, 3),
                error=str(e),
                success=False,
            )
        finally:
            # Cleanup temporary audio file
            if audio_path:
                cleanup_temp_audio(audio_path)

    def extract_batch(self, directory: str, recursive: bool = False) -> List[ExtractionResult]:
        """Extract transcripts from all MP4 files in a directory.

        Args:
            directory: Path to the directory containing MP4 files.
            recursive: Whether to scan recursively.

        Returns:
            List of ExtractionResult for each file processed.
        """
        files = scan_directory(directory, recursive=recursive)

        if not files:
            return []

        results = []
        total = len(files)

        for idx, file_path in enumerate(files):
            self._report_progress(
                "batch",
                (idx / total),
                f"Memproses file {idx + 1}/{total}: {file_path.name}",
            )
            result = self.extract(str(file_path))
            results.append(result)

        return results

    def close(self):
        """Release all resources."""
        if self._transcriber:
            self._transcriber.close()
            self._transcriber = None
        if self._diarizer:
            self._diarizer.close()
            self._diarizer = None
