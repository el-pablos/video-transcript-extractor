"""Redis caching layer — cache hasil transkripsi dengan kompresi lz4."""

import json
import os
from dataclasses import asdict
from typing import Any, Dict, List, Optional

import lz4.frame

from vidscript.core.transcriber import (
    TranscriptResult,
    TranscriptSegment,
    WordSegment,
)

# Default cache TTL: 7 days in seconds
DEFAULT_CACHE_TTL = 7 * 24 * 60 * 60  # 604800

# Cache key prefix
CACHE_KEY_PREFIX = "vidscript:transcript:"


class RedisCacheError(Exception):
    """Base exception for Redis cache errors."""
    pass


class RedisConnectionError(RedisCacheError):
    """Raised when Redis connection fails."""
    pass


class RedisCache:
    """Redis caching layer with lz4 compression.

    Args:
        host: Redis host.
        port: Redis port.
        db: Redis database number.
        username: Redis username.
        password: Redis password.
        ttl: Cache TTL in seconds.
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: int = 0,
        username: Optional[str] = None,
        password: Optional[str] = None,
        ttl: int = DEFAULT_CACHE_TTL,
    ):
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", "6379"))
        self.db = db if db is not None else int(os.getenv("REDIS_DB", "0"))
        self.username = username or os.getenv("REDIS_USERNAME")
        self.password = password or os.getenv("REDIS_PASSWORD")
        self.ttl = ttl
        self._client = None

    def _get_client(self):
        """Get or create Redis client connection."""
        if self._client is None:
            try:
                import redis

                self._client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    username=self.username,
                    password=self.password,
                    decode_responses=False,
                    socket_timeout=10,
                    socket_connect_timeout=10,
                    retry_on_timeout=True,
                )
                # Test connection
                self._client.ping()
            except ImportError:
                raise RedisCacheError("Library 'redis' belum terinstall")
            except Exception as e:
                self._client = None
                raise RedisConnectionError(f"Gagal konek ke Redis: {e}")

        return self._client

    def _make_key(self, file_hash: str) -> str:
        """Create a cache key from file hash.

        Args:
            file_hash: SHA256 hash of the source file.

        Returns:
            Full Redis cache key string.
        """
        return f"{CACHE_KEY_PREFIX}{file_hash}"

    def _compress(self, data: str) -> bytes:
        """Compress data using lz4.

        Args:
            data: JSON string to compress.

        Returns:
            Compressed bytes.
        """
        return lz4.frame.compress(data.encode("utf-8"))

    def _decompress(self, data: bytes) -> str:
        """Decompress lz4 data.

        Args:
            data: Compressed bytes.

        Returns:
            Decompressed JSON string.
        """
        return lz4.frame.decompress(data).decode("utf-8")

    def _serialize_result(self, result: TranscriptResult) -> str:
        """Serialize TranscriptResult to JSON string.

        Args:
            result: Transcription result to serialize.

        Returns:
            JSON string representation.
        """
        data = {
            "segments": [
                {
                    "id": seg.id,
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text,
                    "confidence": seg.confidence,
                    "speaker": seg.speaker,
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
            "language": result.language,
            "language_probability": result.language_probability,
            "duration": result.duration,
            "model": result.model,
            "source_file": result.source_file,
        }
        return json.dumps(data, ensure_ascii=False)

    def _deserialize_result(self, json_str: str) -> TranscriptResult:
        """Deserialize JSON string to TranscriptResult.

        Args:
            json_str: JSON string to deserialize.

        Returns:
            TranscriptResult object.
        """
        data = json.loads(json_str)

        segments = []
        for seg_data in data["segments"]:
            words = [
                WordSegment(
                    word=w["word"],
                    start=w["start"],
                    end=w["end"],
                    probability=w["probability"],
                )
                for w in seg_data.get("words", [])
            ]
            segments.append(TranscriptSegment(
                id=seg_data["id"],
                start=seg_data["start"],
                end=seg_data["end"],
                text=seg_data["text"],
                confidence=seg_data.get("confidence", 0.0),
                speaker=seg_data.get("speaker"),
                words=words,
            ))

        return TranscriptResult(
            segments=segments,
            language=data["language"],
            language_probability=data["language_probability"],
            duration=data["duration"],
            model=data["model"],
            source_file=data["source_file"],
        )

    def get(self, file_hash: str) -> Optional[TranscriptResult]:
        """Get cached transcription result.

        Args:
            file_hash: SHA256 hash of the source file.

        Returns:
            TranscriptResult if found in cache, None otherwise.
        """
        try:
            client = self._get_client()
            key = self._make_key(file_hash)
            data = client.get(key)

            if data is None:
                return None

            json_str = self._decompress(data)
            return self._deserialize_result(json_str)

        except RedisCacheError:
            raise
        except Exception as e:
            raise RedisCacheError(f"Gagal membaca cache: {e}")

    def set(self, file_hash: str, result: TranscriptResult, ttl: Optional[int] = None) -> bool:
        """Store transcription result in cache.

        Args:
            file_hash: SHA256 hash of the source file.
            result: Transcription result to cache.
            ttl: Optional TTL override in seconds.

        Returns:
            True if successfully cached.
        """
        try:
            client = self._get_client()
            key = self._make_key(file_hash)
            json_str = self._serialize_result(result)
            compressed = self._compress(json_str)

            cache_ttl = ttl if ttl is not None else self.ttl
            client.setex(key, cache_ttl, compressed)
            return True

        except RedisCacheError:
            raise
        except Exception as e:
            raise RedisCacheError(f"Gagal menyimpan cache: {e}")

    def delete(self, file_hash: str) -> bool:
        """Delete a specific cache entry.

        Args:
            file_hash: SHA256 hash of the source file.

        Returns:
            True if the key was deleted.
        """
        try:
            client = self._get_client()
            key = self._make_key(file_hash)
            return client.delete(key) > 0

        except RedisCacheError:
            raise
        except Exception as e:
            raise RedisCacheError(f"Gagal menghapus cache: {e}")

    def clear_all(self) -> int:
        """Clear all VidScript cache entries.

        Returns:
            Number of entries deleted.
        """
        try:
            client = self._get_client()
            pattern = f"{CACHE_KEY_PREFIX}*"
            keys = list(client.scan_iter(match=pattern))

            if not keys:
                return 0

            return client.delete(*keys)

        except RedisCacheError:
            raise
        except Exception as e:
            raise RedisCacheError(f"Gagal menghapus semua cache: {e}")

    def list_keys(self) -> List[Dict[str, Any]]:
        """List all cache entries with metadata.

        Returns:
            List of dicts with key info (hash, ttl, size).
        """
        try:
            client = self._get_client()
            pattern = f"{CACHE_KEY_PREFIX}*"
            entries = []

            for key in client.scan_iter(match=pattern):
                key_str = key.decode("utf-8") if isinstance(key, bytes) else key
                file_hash = key_str.replace(CACHE_KEY_PREFIX, "")
                ttl = client.ttl(key)
                size = client.strlen(key)

                entries.append({
                    "hash": file_hash,
                    "ttl": ttl,
                    "size": size,
                    "key": key_str,
                })

            return entries

        except RedisCacheError:
            raise
        except Exception as e:
            raise RedisCacheError(f"Gagal membaca daftar cache: {e}")

    def exists(self, file_hash: str) -> bool:
        """Check if a cache entry exists.

        Args:
            file_hash: SHA256 hash of the source file.

        Returns:
            True if the cache entry exists.
        """
        try:
            client = self._get_client()
            key = self._make_key(file_hash)
            return client.exists(key) > 0

        except Exception:
            return False

    def close(self):
        """Close Redis connection."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
