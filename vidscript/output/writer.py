"""Writer module — tulis hasil transkripsi ke file atau stdout."""

import os
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console

from vidscript.output.formatter import format_output, get_file_extension

console = Console()


class WriterError(Exception):
    """Base exception for writer errors."""
    pass


def write_to_file(
    content: str,
    output_path: str,
    overwrite: bool = True,
) -> str:
    """Write content to a file.

    Args:
        content: Text content to write.
        output_path: Destination file path.
        overwrite: Whether to overwrite existing files.

    Returns:
        Absolute path of the written file.

    Raises:
        WriterError: If writing fails.
    """
    try:
        path = Path(output_path)

        # Create parent directories if needed
        path.parent.mkdir(parents=True, exist_ok=True)

        if path.exists() and not overwrite:
            raise WriterError(f"File sudah ada dan overwrite=False: {path}")

        path.write_text(content, encoding="utf-8")
        return str(path.resolve())

    except WriterError:
        raise
    except Exception as e:
        raise WriterError(f"Gagal menulis file {output_path}: {e}")


def write_to_stdout(content: str) -> None:
    """Write content to stdout.

    Args:
        content: Text content to print.
    """
    sys.stdout.write(content)
    if not content.endswith("\n"):
        sys.stdout.write("\n")
    sys.stdout.flush()


def generate_output_path(
    source_file: str,
    output_format: str,
    output_dir: Optional[str] = None,
) -> str:
    """Generate output file path based on source file and format.

    Args:
        source_file: Original source file path.
        output_format: Target output format.
        output_dir: Optional output directory. Defaults to source file directory.

    Returns:
        Generated output file path.
    """
    source = Path(source_file)
    extension = get_file_extension(output_format)

    if output_dir:
        dir_path = Path(output_dir)
        dir_path.mkdir(parents=True, exist_ok=True)
        return str(dir_path / f"{source.stem}{extension}")

    return str(source.parent / f"{source.stem}{extension}")


def write_result(
    content: str,
    output_path: Optional[str] = None,
    source_file: Optional[str] = None,
    output_format: str = "txt",
    output_dir: Optional[str] = None,
) -> Optional[str]:
    """Write formatted result to file or stdout.

    If output_path is provided, writes to that path.
    If source_file is provided without output_path, generates a path.
    If neither is provided, writes to stdout.

    Args:
        content: Formatted content string.
        output_path: Explicit output file path.
        source_file: Source file for auto-generating output path.
        output_format: Output format for extension detection.
        output_dir: Optional directory for output files.

    Returns:
        File path if written to file, None if written to stdout.
    """
    if output_path:
        return write_to_file(content, output_path)
    elif source_file:
        generated_path = generate_output_path(source_file, output_format, output_dir)
        return write_to_file(content, generated_path)
    else:
        write_to_stdout(content)
        return None
