"""Formatter module — format output transkripsi ke berbagai format: SRT, VTT, TXT, JSON, CSV, MD."""

import csv
import io
import json
from typing import Any, Dict, List, Optional

from vidscript.core.diarizer import format_speaker_label
from vidscript.core.transcriber import TranscriptResult, TranscriptSegment

# Supported output formats
SUPPORTED_FORMATS = ["srt", "vtt", "txt", "json", "csv", "md"]


class FormatterError(Exception):
    """Base exception for formatter errors."""
    pass


def format_timestamp_srt(seconds: float) -> str:
    """Format seconds to SRT timestamp format (HH:MM:SS,mmm).

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted SRT timestamp string.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Format seconds to VTT timestamp format (HH:MM:SS.mmm).

    Args:
        seconds: Time in seconds.

    Returns:
        Formatted VTT timestamp string.
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _segment_text_with_speaker(segment: TranscriptSegment) -> str:
    """Get segment text prefixed with speaker label if available.

    Args:
        segment: Transcript segment.

    Returns:
        Text with optional speaker prefix.
    """
    if segment.speaker:
        return f"{format_speaker_label(segment.speaker)} {segment.text}"
    return segment.text


def format_srt(result: TranscriptResult) -> str:
    """Format transcript as SRT subtitle.

    Args:
        result: Transcription result.

    Returns:
        SRT formatted string.
    """
    lines = []
    for segment in result.segments:
        lines.append(str(segment.id))
        start = format_timestamp_srt(segment.start)
        end = format_timestamp_srt(segment.end)
        lines.append(f"{start} --> {end}")
        lines.append(_segment_text_with_speaker(segment))
        lines.append("")

    return "\n".join(lines)


def format_vtt(result: TranscriptResult) -> str:
    """Format transcript as WebVTT subtitle.

    Args:
        result: Transcription result.

    Returns:
        VTT formatted string.
    """
    lines = ["WEBVTT", ""]
    for segment in result.segments:
        start = format_timestamp_vtt(segment.start)
        end = format_timestamp_vtt(segment.end)
        lines.append(f"{start} --> {end}")
        lines.append(_segment_text_with_speaker(segment))
        lines.append("")

    return "\n".join(lines)


def format_txt(result: TranscriptResult) -> str:
    """Format transcript as plain text.

    Args:
        result: Transcription result.

    Returns:
        Plain text string.
    """
    lines = []
    for segment in result.segments:
        lines.append(_segment_text_with_speaker(segment))

    return "\n".join(lines)


def format_json(result: TranscriptResult) -> str:
    """Format transcript as JSON with full metadata.

    Args:
        result: Transcription result.

    Returns:
        JSON formatted string.
    """
    data = {
        "metadata": {
            "source_file": result.source_file,
            "language": result.language,
            "language_probability": result.language_probability,
            "duration": result.duration,
            "model": result.model,
            "total_segments": len(result.segments),
        },
        "segments": [
            {
                "id": seg.id,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "speaker": seg.speaker,
                "confidence": seg.confidence,
                "words": [
                    {
                        "word": w.word,
                        "start": w.start,
                        "end": w.end,
                        "probability": w.probability,
                    }
                    for w in seg.words
                ],
            }
            for seg in result.segments
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def format_csv(result: TranscriptResult) -> str:
    """Format transcript as CSV with columns: start, end, speaker, text, confidence.

    Args:
        result: Transcription result.

    Returns:
        CSV formatted string.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["start", "end", "speaker", "text", "confidence"])

    for segment in result.segments:
        writer.writerow([
            segment.start,
            segment.end,
            segment.speaker or "",
            segment.text,
            segment.confidence,
        ])

    return output.getvalue()


def format_md(result: TranscriptResult) -> str:
    """Format transcript as Markdown with heading and table.

    Args:
        result: Transcription result.

    Returns:
        Markdown formatted string.
    """
    lines = []
    lines.append(f"# Transkrip: {result.source_file}")
    lines.append("")
    lines.append(f"**Bahasa:** {result.language} (confidence: {result.language_probability})")
    lines.append(f"**Durasi:** {result.duration:.1f} detik")
    lines.append(f"**Model:** {result.model}")
    lines.append(f"**Total Segmen:** {len(result.segments)}")
    lines.append("")
    lines.append("## Hasil Transkripsi")
    lines.append("")
    lines.append("| # | Waktu Mulai | Waktu Selesai | Pembicara | Teks | Confidence |")
    lines.append("|---|------------|---------------|-----------|------|------------|")

    for segment in result.segments:
        start = format_timestamp_vtt(segment.start)
        end = format_timestamp_vtt(segment.end)
        speaker = segment.speaker or "-"
        text = segment.text.replace("|", "\\|")
        confidence = f"{segment.confidence:.2%}"
        lines.append(f"| {segment.id} | {start} | {end} | {speaker} | {text} | {confidence} |")

    lines.append("")
    return "\n".join(lines)


def format_output(result: TranscriptResult, output_format: str) -> str:
    """Format transcript result to the specified format.

    Args:
        result: Transcription result.
        output_format: Target format ('srt', 'vtt', 'txt', 'json', 'csv', 'md').

    Returns:
        Formatted output string.

    Raises:
        FormatterError: If format is not supported.
    """
    fmt = output_format.lower().strip()

    formatters = {
        "srt": format_srt,
        "vtt": format_vtt,
        "txt": format_txt,
        "json": format_json,
        "csv": format_csv,
        "md": format_md,
    }

    if fmt not in formatters:
        raise FormatterError(
            f"Format '{fmt}' tidak didukung. "
            f"Pilihan: {', '.join(SUPPORTED_FORMATS)}"
        )

    return formatters[fmt](result)


def get_file_extension(output_format: str) -> str:
    """Get file extension for the given output format.

    Args:
        output_format: Output format name.

    Returns:
        File extension with dot prefix.
    """
    extensions = {
        "srt": ".srt",
        "vtt": ".vtt",
        "txt": ".txt",
        "json": ".json",
        "csv": ".csv",
        "md": ".md",
    }
    return extensions.get(output_format.lower(), ".txt")
