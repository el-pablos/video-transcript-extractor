"""Media handler module — validasi file MP4 dan ekstraksi audio menggunakan ffmpeg."""

import hashlib
import os
import tempfile
from pathlib import Path
from typing import List, Optional

import ffmpeg

# Supported video extensions
SUPPORTED_EXTENSIONS = {".mp4"}

# Audio extraction settings
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHANNELS = 1  # Mono for Whisper
AUDIO_FORMAT = "wav"


class MediaHandlerError(Exception):
    """Base exception for media handler errors."""
    pass


class FileNotFoundError_(MediaHandlerError):
    """Raised when the input file does not exist."""
    pass


class InvalidFileError(MediaHandlerError):
    """Raised when the input file is not a valid MP4."""
    pass


class AudioExtractionError(MediaHandlerError):
    """Raised when audio extraction fails."""
    pass


def validate_file(file_path: str) -> Path:
    """Validate that the file exists, is an MP4, and is not empty.

    Args:
        file_path: Path to the input file.

    Returns:
        Validated Path object.

    Raises:
        FileNotFoundError_: If file does not exist.
        InvalidFileError: If file is not a valid MP4 or is empty.
    """
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError_(f"File tidak ditemukan: {path}")

    if not path.is_file():
        raise InvalidFileError(f"Bukan sebuah file: {path}")

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise InvalidFileError(
            f"Ekstensi tidak didukung: {path.suffix}. "
            f"Hanya mendukung: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    if path.stat().st_size == 0:
        raise InvalidFileError(f"File kosong (0 bytes): {path}")

    return path


def get_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """Calculate hash of a file for cache key generation.

    Args:
        file_path: Path to the file.
        algorithm: Hash algorithm to use ('md5' or 'sha256').

    Returns:
        Hex digest string of the file hash.
    """
    hash_func = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def get_media_info(file_path: str) -> dict:
    """Get media file information using ffprobe.

    Args:
        file_path: Path to the media file.

    Returns:
        Dictionary with media information (duration, streams, codec, etc.).
    """
    try:
        probe = ffmpeg.probe(file_path)
        video_streams = [s for s in probe["streams"] if s["codec_type"] == "video"]
        audio_streams = [s for s in probe["streams"] if s["codec_type"] == "audio"]

        info = {
            "format": probe["format"].get("format_name", "unknown"),
            "duration": float(probe["format"].get("duration", 0)),
            "size": int(probe["format"].get("size", 0)),
            "has_video": len(video_streams) > 0,
            "has_audio": len(audio_streams) > 0,
            "audio_channels": int(audio_streams[0].get("channels", 0)) if audio_streams else 0,
            "audio_sample_rate": int(audio_streams[0].get("sample_rate", 0)) if audio_streams else 0,
            "audio_codec": audio_streams[0].get("codec_name", "unknown") if audio_streams else "none",
        }
        return info
    except ffmpeg.Error as e:
        raise MediaHandlerError(f"Gagal membaca info media: {e.stderr}")
    except Exception as e:
        raise MediaHandlerError(f"Error saat probe media: {e}")


def extract_audio(
    file_path: str,
    output_path: Optional[str] = None,
    sample_rate: int = AUDIO_SAMPLE_RATE,
    channels: int = AUDIO_CHANNELS,
) -> str:
    """Extract audio from MP4 file to WAV format.

    Args:
        file_path: Path to the input MP4 file.
        output_path: Optional output path for the WAV file.
            If None, a temp file is created.
        sample_rate: Audio sample rate (default: 16000 for Whisper).
        channels: Number of audio channels (default: 1 mono).

    Returns:
        Path to the extracted WAV audio file.

    Raises:
        AudioExtractionError: If audio extraction fails.
    """
    validated_path = validate_file(file_path)

    if output_path is None:
        temp_dir = tempfile.mkdtemp(prefix="vidscript_")
        output_path = os.path.join(temp_dir, f"{validated_path.stem}.wav")

    try:
        (
            ffmpeg
            .input(str(validated_path))
            .output(
                output_path,
                acodec="pcm_s16le",
                ac=channels,
                ar=sample_rate,
                format=AUDIO_FORMAT,
            )
            .overwrite_output()
            .run(quiet=True, capture_stderr=True)
        )
    except ffmpeg.Error as e:
        stderr_output = e.stderr.decode("utf-8") if e.stderr else "Unknown error"
        raise AudioExtractionError(
            f"Gagal ekstrak audio dari {validated_path}: {stderr_output}"
        )

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise AudioExtractionError(
            f"File audio hasil ekstraksi kosong atau tidak dibuat: {output_path}"
        )

    return output_path


def scan_directory(directory: str, recursive: bool = False) -> List[Path]:
    """Scan a directory for MP4 files.

    Args:
        directory: Path to the directory to scan.
        recursive: Whether to scan recursively.

    Returns:
        List of Path objects for found MP4 files.

    Raises:
        FileNotFoundError_: If directory does not exist.
    """
    dir_path = Path(directory)

    if not dir_path.exists():
        raise FileNotFoundError_(f"Direktori tidak ditemukan: {dir_path}")

    if not dir_path.is_dir():
        raise InvalidFileError(f"Bukan sebuah direktori: {dir_path}")

    pattern = "**/*.mp4" if recursive else "*.mp4"
    files = sorted(dir_path.glob(pattern))

    return [f for f in files if f.is_file() and f.stat().st_size > 0]


def cleanup_temp_audio(audio_path: str) -> None:
    """Clean up temporary audio files.

    Args:
        audio_path: Path to the temporary audio file to delete.
    """
    try:
        path = Path(audio_path)
        if path.exists():
            path.unlink()
            # Also try to remove the temp directory if empty
            parent = path.parent
            if parent.name.startswith("vidscript_") and not any(parent.iterdir()):
                parent.rmdir()
    except OSError:
        pass  # Best effort cleanup
