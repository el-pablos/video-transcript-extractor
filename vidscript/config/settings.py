"""Settings module — konfigurasi global, env, dan argparse defaults."""

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Default config file location
CONFIG_DIR = Path.home() / ".vidscript"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class RedisSettings:
    """Redis connection settings."""
    host: str = ""
    port: int = 6379
    db: int = 0
    username: str = ""
    password: str = ""
    cache_ttl: int = 604800  # 7 days

    @classmethod
    def from_env(cls) -> "RedisSettings":
        """Create RedisSettings from environment variables."""
        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            username=os.getenv("REDIS_USERNAME", ""),
            password=os.getenv("REDIS_PASSWORD", ""),
            cache_ttl=int(os.getenv("REDIS_CACHE_TTL", "604800")),
        )


@dataclass
class TranscriptionSettings:
    """Transcription default settings."""
    model: str = "base"
    language: str = "auto"
    device: str = "auto"
    compute_type: str = "int8"
    word_timestamps: bool = True


@dataclass
class OutputSettings:
    """Output default settings."""
    format: str = "txt"
    output_dir: Optional[str] = None


@dataclass
class AppSettings:
    """Main application settings container."""
    redis: RedisSettings = field(default_factory=RedisSettings.from_env)
    transcription: TranscriptionSettings = field(default_factory=TranscriptionSettings)
    output: OutputSettings = field(default_factory=OutputSettings)
    verbose: bool = False
    quiet: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return asdict(self)

    @classmethod
    def load(cls) -> "AppSettings":
        """Load settings from config file and environment.

        Environment variables and config file are merged,
        with env vars taking precedence.

        Returns:
            AppSettings instance.
        """
        settings = cls()

        # Load from config file if exists
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config_data = json.load(f)

                # Apply config file values
                if "transcription" in config_data:
                    tc = config_data["transcription"]
                    for key in ["model", "language", "device", "compute_type"]:
                        if key in tc:
                            setattr(settings.transcription, key, tc[key])

                if "output" in config_data:
                    oc = config_data["output"]
                    if "format" in oc:
                        settings.output.format = oc["format"]
                    if "output_dir" in oc:
                        settings.output.output_dir = oc["output_dir"]

            except (json.JSONDecodeError, OSError):
                pass  # Ignore invalid config file

        return settings

    def save(self) -> None:
        """Save current settings to config file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Only save non-sensitive settings
        config_data = {
            "transcription": {
                "model": self.transcription.model,
                "language": self.transcription.language,
                "device": self.transcription.device,
                "compute_type": self.transcription.compute_type,
            },
            "output": {
                "format": self.output.format,
                "output_dir": self.output.output_dir,
            },
        }

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2, ensure_ascii=False)


def get_settings() -> AppSettings:
    """Get application settings.

    Returns:
        AppSettings instance loaded from env and config file.
    """
    return AppSettings.load()


def show_settings(settings: Optional[AppSettings] = None) -> Dict[str, Any]:
    """Get settings as displayable dictionary (with secrets masked).

    Args:
        settings: Optional settings instance.

    Returns:
        Dictionary with masked sensitive values.
    """
    if settings is None:
        settings = get_settings()

    data = settings.to_dict()

    # Mask sensitive values
    if data.get("redis", {}).get("password"):
        data["redis"]["password"] = "****"
    if data.get("redis", {}).get("username"):
        data["redis"]["username"] = "****"

    return data
