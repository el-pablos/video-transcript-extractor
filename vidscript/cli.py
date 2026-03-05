"""CLI module — entry point utama VidScript dengan banner, subcommands, dan rich output."""

import logging
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from vidscript.__version__ import __author__, __repo__, __version__

console = Console()
error_console = Console(stderr=True)

# ─── ASCII Art Banner ──────────────────────────────────────────────────────────


def print_banner():
    """Print the VidScript ASCII art banner with colors."""
    try:
        import pyfiglet
        from colorama import init as colorama_init

        colorama_init()
        ascii_art = pyfiglet.figlet_format("VidScript", font="slant")
    except ImportError:
        ascii_art = r"""
 _    ___     ______           _       __
| |  / (_)___/ / __/__________(_)___  / /_
| | / / / __  /\__ \/ ___/ __/ / __ \/ __/
| |/ / / /_/ /___/ / /__/ / / / /_/ / /_
|___/_/\__,_//____/\___/_/ /_/ .___/\__/
                            /_/
"""

    # Gradient color effect
    lines = ascii_art.strip().split("\n")
    colors = ["bright_cyan", "cyan", "bright_blue", "blue", "bright_magenta", "magenta"]

    styled_lines = []
    for i, line in enumerate(lines):
        color = colors[i % len(colors)]
        styled_lines.append(f"[{color}]{line}[/{color}]")

    banner_text = "\n".join(styled_lines)

    # Build info lines
    info = (
        f"\n[bold bright_white]Advanced MP4 Transcript Extractor[/bold bright_white]\n"
        f"[dim]Version: {__version__} | Author: {__author__}[/dim]\n"
        f"[dim]{__repo__}[/dim]"
    )

    # Footer gradient line
    footer = "[bright_cyan]━[/bright_cyan]" * 10
    footer += "[cyan]━[/cyan]" * 10
    footer += "[bright_blue]━[/bright_blue]" * 10
    footer += "[blue]━[/blue]" * 10
    footer += "[bright_magenta]━[/bright_magenta]" * 10
    footer += "[magenta]━[/magenta]" * 10

    console.print(banner_text)
    console.print(info)
    console.print(footer)
    console.print()


# ─── CLI Group ─────────────────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.option("--verbose", "-v", is_flag=True, help="Mode verbose (DEBUG level logging).")
@click.option("--quiet", "-q", is_flag=True, help="Mode quiet, hanya tampilkan hasil akhir.")
@click.pass_context
def main(ctx, verbose, quiet):
    """VidScript — Advanced MP4 Transcript Extractor CLI.

    Tool CLI untuk mengekstrak transkrip dari file video MP4 secara akurat
    menggunakan Whisper AI, dengan dukungan multi-format output dan Redis caching.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet

    # Setup logging
    from vidscript.utils.logger import setup_logger

    if verbose:
        log_level = logging.DEBUG
    elif quiet:
        log_level = logging.WARNING
    else:
        log_level = logging.INFO

    setup_logger(level=log_level, quiet=quiet)

    if ctx.invoked_subcommand is None:
        print_banner()
        click.echo(ctx.get_help())


# ─── Transcribe Command ───────────────────────────────────────────────────────


@main.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--model", "-m", default="base", type=click.Choice(["tiny", "base", "small", "medium", "large-v3"]), help="Model Whisper yang digunakan.")
@click.option("--language", "-l", default="auto", help="Kode bahasa (auto, en, id, dll).")
@click.option("--format", "-f", "output_format", default="txt", type=click.Choice(["srt", "vtt", "txt", "json", "csv", "md"]), help="Format output.")
@click.option("--output", "-o", "output_path", default=None, help="Path file output.")
@click.option("--output-dir", default=None, help="Direktori output untuk batch processing.")
@click.option("--diarize", is_flag=True, help="Aktifkan speaker diarization.")
@click.option("--batch", is_flag=True, help="Proses semua file MP4 dalam direktori.")
@click.option("--no-cache", is_flag=True, help="Bypass Redis cache.")
@click.option("--cache-ttl", default=None, type=int, help="TTL cache dalam detik.")
@click.pass_context
def transcribe(ctx, path, model, language, output_format, output_path, output_dir, diarize, batch, no_cache, cache_ttl):
    """Ekstrak transkrip dari file MP4 atau direktori.

    PATH bisa berupa file .mp4 tunggal atau direktori (dengan flag --batch).

    Contoh:
        vidscript transcribe video.mp4 --model base --format srt
        vidscript transcribe ./videos/ --batch --format json
    """
    if not ctx.obj.get("quiet"):
        print_banner()

    from vidscript.cache.redis_cache import RedisCache, RedisCacheError
    from vidscript.config.settings import get_settings
    from vidscript.core.extractor import ExtractionOptions, ExtractionResult, Extractor
    from vidscript.core.media_handler import get_file_hash
    from vidscript.output.formatter import format_output
    from vidscript.output.writer import write_result
    from vidscript.utils.helpers import format_duration, format_file_size
    from vidscript.utils.logger import get_logger
    from vidscript.utils.progress import ProgressTracker

    logger = get_logger()
    settings = get_settings()

    # Build extraction options
    lang = language if language != "auto" else None
    options = ExtractionOptions(
        model=model,
        language=lang,
        diarize=diarize,
    )

    # Setup cache
    cache = None
    if not no_cache:
        try:
            redis_settings = settings.redis
            cache = RedisCache(
                host=redis_settings.host,
                port=redis_settings.port,
                db=redis_settings.db,
                username=redis_settings.username,
                password=redis_settings.password,
                ttl=cache_ttl or redis_settings.cache_ttl,
            )
        except Exception as e:
            logger.warning(f"Redis cache tidak tersedia: {e}")
            cache = None

    path_obj = Path(path)

    if batch or path_obj.is_dir():
        _process_batch(path, options, output_format, output_dir, cache, logger)
    else:
        _process_single(
            path, options, output_format, output_path, output_dir, cache, logger
        )


def _process_single(path, options, output_format, output_path, output_dir, cache, logger):
    """Process a single MP4 file."""
    from vidscript.cache.redis_cache import RedisCacheError
    from vidscript.core.extractor import Extractor
    from vidscript.core.media_handler import get_file_hash
    from vidscript.output.formatter import format_output
    from vidscript.output.writer import write_result
    from vidscript.utils.helpers import format_duration
    from vidscript.utils.progress import ProgressTracker

    # Check cache first
    file_hash = None
    if cache:
        try:
            file_hash = get_file_hash(path)
            cached_result = cache.get(file_hash)
            if cached_result is not None:
                console.print("[bold green][CACHE HIT][/bold green] Hasil ditemukan di cache!")
                content = format_output(cached_result, output_format)
                result_path = write_result(
                    content, output_path, path, output_format, output_dir
                )
                if result_path:
                    console.print(f"[green]Output disimpan ke:[/green] {result_path}")
                return
        except RedisCacheError as e:
            logger.warning(f"Cache error: {e}")

    console.print("[bold yellow][CACHE MISS][/bold yellow] Memproses file...")

    # Process with progress
    with ProgressTracker(description="Transkripsi") as tracker:
        extractor = Extractor(
            options=options,
            progress_callback=tracker.callback,
        )
        result = extractor.extract(path)
        extractor.close()

    if not result.success:
        error_console.print(f"[bold red]Error:[/bold red] {result.error}")
        sys.exit(1)

    # Show summary
    _print_summary(result)

    # Format and write output
    content = format_output(result.transcript, output_format)
    result_path = write_result(content, output_path, path, output_format, output_dir)
    if result_path:
        console.print(f"[green]Output disimpan ke:[/green] {result_path}")

    # Store in cache
    if cache and file_hash and result.transcript:
        try:
            cache.set(file_hash, result.transcript)
            logger.info("Hasil disimpan ke cache")
        except RedisCacheError as e:
            logger.warning(f"Gagal menyimpan cache: {e}")


def _process_batch(directory, options, output_format, output_dir, cache, logger):
    """Process all MP4 files in a directory."""
    from vidscript.core.extractor import Extractor
    from vidscript.core.media_handler import scan_directory
    from vidscript.output.formatter import format_output
    from vidscript.output.writer import write_result
    from vidscript.utils.progress import create_batch_progress

    files = scan_directory(directory)
    if not files:
        console.print("[yellow]Tidak ada file MP4 ditemukan di direktori ini.[/yellow]")
        return

    console.print(f"[bold]Ditemukan {len(files)} file MP4[/bold]")

    results = []
    with create_batch_progress() as progress:
        task = progress.add_task("Batch Processing", total=len(files))

        for file_path in files:
            progress.update(task, description=f"→ {file_path.name}")

            extractor = Extractor(options=options)
            result = extractor.extract(str(file_path))
            extractor.close()
            results.append(result)

            if result.success and result.transcript:
                content = format_output(result.transcript, output_format)
                write_result(
                    content, source_file=str(file_path),
                    output_format=output_format, output_dir=output_dir,
                )

            progress.advance(task)

    # Print batch summary
    success_count = sum(1 for r in results if r.success)
    fail_count = sum(1 for r in results if not r.success)

    table = Table(title="Hasil Batch Processing")
    table.add_column("Status", style="bold")
    table.add_column("Jumlah")
    table.add_row("[green]Berhasil[/green]", str(success_count))
    table.add_row("[red]Gagal[/red]", str(fail_count))
    table.add_row("Total", str(len(results)))
    console.print(table)


def _print_summary(result):
    """Print extraction summary."""
    from vidscript.utils.helpers import format_duration

    if not result.transcript:
        return

    table = Table(title="Ringkasan Transkripsi", show_header=False)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")

    table.add_row("File", result.file_path)
    table.add_row("Bahasa", f"{result.transcript.language} ({result.transcript.language_probability:.1%})")
    table.add_row("Durasi", format_duration(result.transcript.duration))
    table.add_row("Model", result.transcript.model)
    table.add_row("Segmen", str(len(result.transcript.segments)))
    table.add_row("Waktu Proses", format_duration(result.processing_time))

    console.print(table)


# ─── Cache Commands ────────────────────────────────────────────────────────────


@main.group()
def cache():
    """Kelola Redis cache untuk hasil transkripsi."""
    pass


@cache.command("list")
def cache_list():
    """Tampilkan semua entri cache yang tersimpan."""
    from vidscript.cache.redis_cache import RedisCache, RedisCacheError
    from vidscript.config.settings import get_settings
    from vidscript.utils.helpers import format_file_size

    settings = get_settings()

    try:
        redis_cache = RedisCache(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            username=settings.redis.username,
            password=settings.redis.password,
        )

        entries = redis_cache.list_keys()

        if not entries:
            console.print("[yellow]Cache kosong — belum ada data tersimpan.[/yellow]")
            return

        table = Table(title=f"Cache Entries ({len(entries)} total)")
        table.add_column("#", style="dim")
        table.add_column("File Hash", style="cyan")
        table.add_column("Size", justify="right")
        table.add_column("TTL", justify="right")

        for idx, entry in enumerate(entries, 1):
            ttl_str = f"{entry['ttl']}s" if entry["ttl"] > 0 else "no expiry"
            table.add_row(
                str(idx),
                entry["hash"][:16] + "...",
                format_file_size(entry["size"]),
                ttl_str,
            )

        console.print(table)
        redis_cache.close()

    except RedisCacheError as e:
        error_console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


@cache.command("clear")
@click.option("--all", "clear_all", is_flag=True, help="Hapus semua cache.")
@click.argument("file_hash", required=False)
def cache_clear(clear_all, file_hash):
    """Hapus cache spesifik atau semua cache.

    Contoh:
        vidscript cache clear --all
        vidscript cache clear abc123def456
    """
    from vidscript.cache.redis_cache import RedisCache, RedisCacheError
    from vidscript.config.settings import get_settings

    settings = get_settings()

    try:
        redis_cache = RedisCache(
            host=settings.redis.host,
            port=settings.redis.port,
            db=settings.redis.db,
            username=settings.redis.username,
            password=settings.redis.password,
        )

        if clear_all:
            count = redis_cache.clear_all()
            console.print(f"[green]Berhasil menghapus {count} entri cache.[/green]")
        elif file_hash:
            deleted = redis_cache.delete(file_hash)
            if deleted:
                console.print(f"[green]Cache untuk hash {file_hash} berhasil dihapus.[/green]")
            else:
                console.print(f"[yellow]Cache untuk hash {file_hash} tidak ditemukan.[/yellow]")
        else:
            console.print("[yellow]Gunakan --all untuk hapus semua, atau berikan file hash.[/yellow]")

        redis_cache.close()

    except RedisCacheError as e:
        error_console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


# ─── Config Command ───────────────────────────────────────────────────────────


@main.group()
def config():
    """Kelola konfigurasi VidScript."""
    pass


@config.command("show")
def config_show():
    """Tampilkan konfigurasi aktif saat ini."""
    from vidscript.config.settings import get_settings, show_settings

    settings = get_settings()
    display_data = show_settings(settings)

    table = Table(title="Konfigurasi Aktif")
    table.add_column("Setting", style="bold cyan")
    table.add_column("Value")

    # Flatten nested settings for display
    for section, values in display_data.items():
        if isinstance(values, dict):
            for key, value in values.items():
                table.add_row(f"{section}.{key}", str(value))
        else:
            table.add_row(section, str(values))

    console.print(table)


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key, value):
    """Set nilai konfigurasi.

    Contoh:
        vidscript config set transcription.model small
        vidscript config set output.format json
    """
    from vidscript.config.settings import get_settings

    settings = get_settings()

    parts = key.split(".")
    if len(parts) != 2:
        error_console.print("[red]Format key harus: section.key (contoh: transcription.model)[/red]")
        sys.exit(1)

    section, attr = parts

    target_map = {
        "transcription": settings.transcription,
        "output": settings.output,
    }

    if section not in target_map:
        error_console.print(f"[red]Section '{section}' tidak valid. Pilihan: {', '.join(target_map.keys())}[/red]")
        sys.exit(1)

    target = target_map[section]
    if not hasattr(target, attr):
        error_console.print(f"[red]Key '{attr}' tidak ditemukan di section '{section}'[/red]")
        sys.exit(1)

    setattr(target, attr, value)
    settings.save()
    console.print(f"[green]Berhasil menyimpan {key} = {value}[/green]")


# ─── Version Command ──────────────────────────────────────────────────────────


@main.command()
def version():
    """Tampilkan versi VidScript."""
    console.print(f"[bold]VidScript[/bold] v{__version__}")


if __name__ == "__main__":
    main()
