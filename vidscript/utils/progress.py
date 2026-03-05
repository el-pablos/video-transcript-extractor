"""Progress module — progress bar real-time menggunakan rich Progress."""

from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

console = Console()


def create_progress_bar(
    description: str = "Processing",
    transient: bool = False,
) -> Progress:
    """Create a rich Progress bar with standard columns.

    Args:
        description: Default task description.
        transient: If True, progress bar disappears when done.

    Returns:
        Configured rich Progress instance.
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=40),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=transient,
    )
    return progress


def create_batch_progress(transient: bool = False) -> Progress:
    """Create a progress bar for batch processing with file count.

    Args:
        transient: If True, progress bar disappears when done.

    Returns:
        Configured rich Progress instance for batch operations.
    """
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(bar_width=30),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=transient,
    )
    return progress


class ProgressTracker:
    """High-level progress tracker for the extraction pipeline.

    Args:
        total_steps: Total number of steps in the pipeline.
        description: Description for the progress bar.
    """

    def __init__(self, total_steps: int = 100, description: str = "Transkripsi"):
        self.total_steps = total_steps
        self.description = description
        self._progress: Optional[Progress] = None
        self._task_id = None

    def __enter__(self):
        self._progress = create_progress_bar(transient=True)
        self._progress.start()
        self._task_id = self._progress.add_task(
            self.description, total=self.total_steps
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._progress:
            self._progress.stop()
        return False

    def update(self, step: str, progress: float, message: str = ""):
        """Update progress bar.

        Args:
            step: Current step name.
            progress: Progress value between 0.0 and 1.0.
            message: Optional status message.
        """
        if self._progress and self._task_id is not None:
            completed = int(progress * self.total_steps)
            description = f"{self.description}: {message}" if message else self.description
            self._progress.update(
                self._task_id,
                completed=completed,
                description=description,
            )

    def callback(self, step: str, progress: float, message: str = ""):
        """Callback method compatible with Extractor's progress_callback.

        Args:
            step: Current step name.
            progress: Progress value between 0.0 and 1.0.
            message: Optional status message.
        """
        self.update(step, progress, message)
