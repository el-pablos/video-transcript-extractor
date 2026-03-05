"""Pytest fixtures global untuk VidScript tests."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vidscript.core.transcriber import (
    TranscriptResult,
    TranscriptSegment,
    WordSegment,
)


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory(prefix="vidscript_test_") as d:
        yield Path(d)


@pytest.fixture
def sample_mp4(tmp_dir):
    """Create a dummy MP4 file for testing."""
    mp4_path = tmp_dir / "test_video.mp4"
    # Write minimal MP4 header (ftyp box) so it's not empty
    mp4_path.write_bytes(b"\x00\x00\x00\x1c" + b"ftypisom" + b"\x00" * 16)
    return mp4_path


@pytest.fixture
def empty_file(tmp_dir):
    """Create an empty file."""
    empty_path = tmp_dir / "empty.mp4"
    empty_path.write_bytes(b"")
    return empty_path


@pytest.fixture
def non_mp4_file(tmp_dir):
    """Create a non-MP4 file."""
    txt_path = tmp_dir / "test.txt"
    txt_path.write_text("This is not a video file.")
    return txt_path


@pytest.fixture
def sample_transcript():
    """Create a sample TranscriptResult for testing."""
    segments = [
        TranscriptSegment(
            id=1,
            start=0.0,
            end=3.5,
            text="Hello, this is a test.",
            confidence=0.95,
            speaker="SPEAKER_00",
            words=[
                WordSegment(word="Hello,", start=0.0, end=0.5, probability=0.98),
                WordSegment(word="this", start=0.5, end=0.8, probability=0.97),
                WordSegment(word="is", start=0.8, end=1.0, probability=0.99),
                WordSegment(word="a", start=1.0, end=1.2, probability=0.96),
                WordSegment(word="test.", start=1.2, end=3.5, probability=0.94),
            ],
        ),
        TranscriptSegment(
            id=2,
            start=4.0,
            end=8.0,
            text="This is the second segment.",
            confidence=0.90,
            speaker="SPEAKER_01",
            words=[
                WordSegment(word="This", start=4.0, end=4.3, probability=0.92),
                WordSegment(word="is", start=4.3, end=4.5, probability=0.95),
                WordSegment(word="the", start=4.5, end=4.7, probability=0.93),
                WordSegment(word="second", start=4.7, end=5.2, probability=0.88),
                WordSegment(word="segment.", start=5.2, end=8.0, probability=0.91),
            ],
        ),
        TranscriptSegment(
            id=3,
            start=10.0,
            end=15.5,
            text="And this is the last one.",
            confidence=0.85,
            speaker=None,
            words=[],
        ),
    ]

    return TranscriptResult(
        segments=segments,
        language="en",
        language_probability=0.97,
        duration=15.5,
        model="base",
        source_file="/path/to/test_video.mp4",
    )


@pytest.fixture
def sample_transcript_no_speakers():
    """Create a transcript without speaker labels."""
    segments = [
        TranscriptSegment(
            id=1,
            start=0.0,
            end=5.0,
            text="Segment without speaker.",
            confidence=0.9,
        ),
    ]
    return TranscriptResult(
        segments=segments,
        language="en",
        language_probability=0.95,
        duration=5.0,
        model="base",
        source_file="/path/to/test.mp4",
    )


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_client.get.return_value = None
    mock_client.setex.return_value = True
    mock_client.delete.return_value = 1
    mock_client.scan_iter.return_value = []
    mock_client.exists.return_value = 0
    return mock_client
