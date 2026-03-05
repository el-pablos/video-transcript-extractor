"""Helpers module — fungsi-fungsi bantu umum untuk VidScript."""

import os
import re
from datetime import timedelta
from pathlib import Path
from typing import Optional


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string like '1h 23m 45s' or '2m 30s'.
    """
    if seconds < 0:
        return "0s"

    td = timedelta(seconds=int(seconds))
    hours, remainder = divmod(int(td.total_seconds()), 3600)
    minutes, secs = divmod(remainder, 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")

    return " ".join(parts)


def format_file_size(size_bytes: int) -> str:
    """Format file size in bytes to human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted string like '1.23 MB' or '456 KB'.
    """
    if size_bytes < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} B"
    return f"{size:.2f} {units[unit_index]}"


def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing invalid characters.

    Args:
        filename: Original filename.

    Returns:
        Sanitized filename safe for all OS.
    """
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # Remove leading/trailing dots and spaces
    sanitized = sanitized.strip(". ")
    # Limit length
    if len(sanitized) > 200:
        sanitized = sanitized[:200]
    return sanitized or "unnamed"


def truncate_text(text: str, max_length: int = 80, suffix: str = "...") -> str:
    """Truncate text to a maximum length with suffix.

    Args:
        text: Text to truncate.
        max_length: Maximum length including suffix.
        suffix: Suffix to append when truncated.

    Returns:
        Truncated text string.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def ensure_directory(directory: str) -> Path:
    """Ensure a directory exists, creating it if needed.

    Args:
        directory: Path to the directory.

    Returns:
        Path object for the directory.
    """
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_project_root() -> Path:
    """Get the project root directory.

    Returns:
        Path to the project root.
    """
    return Path(__file__).parent.parent.parent


def get_config_dir() -> Path:
    """Get the VidScript config directory (~/.vidscript/).

    Returns:
        Path to the config directory.
    """
    config_dir = Path.home() / ".vidscript"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def is_valid_mp4(file_path: str) -> bool:
    """Quick check if a file appears to be a valid MP4.

    Args:
        file_path: Path to the file.

    Returns:
        True if the file exists and has .mp4 extension.
    """
    path = Path(file_path)
    return path.exists() and path.is_file() and path.suffix.lower() == ".mp4" and path.stat().st_size > 0
