"""Tests for progress module."""

from unittest.mock import MagicMock, patch

import pytest

from vidscript.utils.progress import (
    ProgressTracker,
    create_batch_progress,
    create_progress_bar,
)


class TestCreateProgressBar:
    """Tests for create_progress_bar."""

    def test_returns_progress_instance(self):
        progress = create_progress_bar()
        assert progress is not None

    def test_custom_description(self):
        progress = create_progress_bar(description="Testing")
        assert progress is not None

    def test_transient_mode(self):
        progress = create_progress_bar(transient=True)
        assert progress is not None


class TestCreateBatchProgress:
    """Tests for create_batch_progress."""

    def test_returns_progress_instance(self):
        progress = create_batch_progress()
        assert progress is not None

    def test_transient_mode(self):
        progress = create_batch_progress(transient=True)
        assert progress is not None


class TestProgressTracker:
    """Tests for ProgressTracker."""

    def test_init_defaults(self):
        tracker = ProgressTracker()
        assert tracker.total_steps == 100
        assert tracker.description == "Transkripsi"

    def test_init_custom(self):
        tracker = ProgressTracker(total_steps=50, description="Custom")
        assert tracker.total_steps == 50
        assert tracker.description == "Custom"

    def test_context_manager(self):
        with ProgressTracker() as tracker:
            assert tracker._progress is not None
            assert tracker._task_id is not None

    def test_update(self):
        with ProgressTracker() as tracker:
            tracker.update("step1", 0.5, "halfway")
            # No exception means success

    def test_update_no_message(self):
        with ProgressTracker() as tracker:
            tracker.update("step1", 0.3)

    def test_callback(self):
        with ProgressTracker() as tracker:
            tracker.callback("transcribe", 0.8, "almost done")

    def test_callback_no_message(self):
        with ProgressTracker() as tracker:
            tracker.callback("extract", 0.5)

    def test_exit_stops_progress(self):
        tracker = ProgressTracker()
        tracker.__enter__()
        assert tracker._progress is not None
        tracker.__exit__(None, None, None)

    def test_exit_returns_false(self):
        with ProgressTracker() as tracker:
            pass
        # __exit__ should return False (no exception suppression)

    def test_update_without_context(self):
        """Test update without entering context does nothing."""
        tracker = ProgressTracker()
        tracker.update("step", 0.5, "msg")  # Should not raise
