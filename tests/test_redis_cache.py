"""Tests for redis_cache module."""

import json
from unittest.mock import MagicMock, patch

import pytest

from vidscript.cache.redis_cache import (
    CACHE_KEY_PREFIX,
    DEFAULT_CACHE_TTL,
    RedisCache,
    RedisCacheError,
    RedisConnectionError,
)
from vidscript.core.transcriber import TranscriptResult, TranscriptSegment, WordSegment


@pytest.fixture
def redis_cache(mock_redis):
    """Create a RedisCache with mocked client."""
    cache = RedisCache(host="localhost", port=6379, password="test")
    cache._client = mock_redis
    return cache


@pytest.fixture
def sample_result():
    """Create a minimal TranscriptResult for cache tests."""
    return TranscriptResult(
        segments=[
            TranscriptSegment(
                id=1, start=0.0, end=5.0, text="Hello world",
                confidence=0.95, speaker="SPEAKER_00",
                words=[WordSegment(word="Hello", start=0.0, end=0.3, probability=0.98)],
            ),
        ],
        language="en",
        language_probability=0.97,
        duration=5.0,
        model="base",
        source_file="test.mp4",
    )


class TestRedisCacheInit:
    """Tests for RedisCache initialization."""

    def test_default_values(self):
        """Test default initialization values."""
        with patch.dict("os.environ", {}, clear=True):
            cache = RedisCache()
            assert cache.host == "localhost"
            assert cache.port == 6379
            assert cache.db == 0

    def test_custom_values(self):
        """Test custom initialization values."""
        cache = RedisCache(host="redis.example.com", port=6380, password="secret")
        assert cache.host == "redis.example.com"
        assert cache.port == 6380

    def test_env_values(self):
        """Test initialization from environment variables."""
        env = {
            "REDIS_HOST": "env-host",
            "REDIS_PORT": "1234",
            "REDIS_DB": "5",
            "REDIS_USERNAME": "user",
            "REDIS_PASSWORD": "pass",
        }
        with patch.dict("os.environ", env):
            cache = RedisCache()
            assert cache.host == "env-host"
            assert cache.port == 1234
            assert cache.db == 5


class TestRedisCacheKey:
    """Tests for cache key generation."""

    def test_make_key(self, redis_cache):
        """Test cache key generation."""
        key = redis_cache._make_key("abc123")
        assert key == f"{CACHE_KEY_PREFIX}abc123"

    def test_make_key_different_hashes(self, redis_cache):
        """Test different hashes produce different keys."""
        key1 = redis_cache._make_key("hash1")
        key2 = redis_cache._make_key("hash2")
        assert key1 != key2


class TestRedisCacheCompression:
    """Tests for compression/decompression."""

    def test_compress_decompress(self, redis_cache):
        """Test that compression and decompression are inverse operations."""
        original = '{"test": "data", "number": 42}'
        compressed = redis_cache._compress(original)
        decompressed = redis_cache._decompress(compressed)
        assert decompressed == original

    def test_compressed_is_bytes(self, redis_cache):
        """Test that compressed data is bytes."""
        compressed = redis_cache._compress("test data")
        assert isinstance(compressed, bytes)

    def test_compress_empty_string(self, redis_cache):
        """Test compressing empty string."""
        compressed = redis_cache._compress("")
        decompressed = redis_cache._decompress(compressed)
        assert decompressed == ""


class TestRedisCacheSerialization:
    """Tests for serialization/deserialization."""

    def test_serialize_result(self, redis_cache, sample_result):
        """Test serializing TranscriptResult to JSON."""
        json_str = redis_cache._serialize_result(sample_result)
        data = json.loads(json_str)
        assert data["language"] == "en"
        assert len(data["segments"]) == 1
        assert data["segments"][0]["text"] == "Hello world"

    def test_deserialize_result(self, redis_cache, sample_result):
        """Test deserializing JSON back to TranscriptResult."""
        json_str = redis_cache._serialize_result(sample_result)
        restored = redis_cache._deserialize_result(json_str)
        assert restored.language == sample_result.language
        assert len(restored.segments) == len(sample_result.segments)
        assert restored.segments[0].text == "Hello world"

    def test_roundtrip(self, redis_cache, sample_result):
        """Test full serialize/deserialize roundtrip."""
        json_str = redis_cache._serialize_result(sample_result)
        restored = redis_cache._deserialize_result(json_str)
        assert restored.language == sample_result.language
        assert restored.duration == sample_result.duration
        assert restored.model == sample_result.model


class TestRedisCacheOperations:
    """Tests for cache get/set/delete operations."""

    def test_get_cache_miss(self, redis_cache):
        """Test getting non-existent cache entry."""
        redis_cache._client.get.return_value = None
        result = redis_cache.get("nonexistent_hash")
        assert result is None

    def test_get_cache_hit(self, redis_cache, sample_result):
        """Test getting existing cache entry."""
        json_str = redis_cache._serialize_result(sample_result)
        compressed = redis_cache._compress(json_str)
        redis_cache._client.get.return_value = compressed

        result = redis_cache.get("existing_hash")
        assert result is not None
        assert result.language == "en"
        assert result.segments[0].text == "Hello world"

    def test_set_cache(self, redis_cache, sample_result):
        """Test storing cache entry."""
        success = redis_cache.set("file_hash", sample_result)
        assert success is True
        redis_cache._client.setex.assert_called_once()

    def test_set_cache_custom_ttl(self, redis_cache, sample_result):
        """Test storing with custom TTL."""
        redis_cache.set("file_hash", sample_result, ttl=3600)
        call_args = redis_cache._client.setex.call_args
        assert call_args[0][1] == 3600  # TTL argument

    def test_delete_existing(self, redis_cache):
        """Test deleting existing cache entry."""
        redis_cache._client.delete.return_value = 1
        result = redis_cache.delete("some_hash")
        assert result is True

    def test_delete_nonexistent(self, redis_cache):
        """Test deleting non-existent cache entry."""
        redis_cache._client.delete.return_value = 0
        result = redis_cache.delete("nonexistent")
        assert result is False

    def test_clear_all(self, redis_cache):
        """Test clearing all cache entries."""
        redis_cache._client.scan_iter.return_value = [b"key1", b"key2"]
        redis_cache._client.delete.return_value = 2

        count = redis_cache.clear_all()
        assert count == 2

    def test_clear_all_empty(self, redis_cache):
        """Test clearing when cache is empty."""
        redis_cache._client.scan_iter.return_value = []
        count = redis_cache.clear_all()
        assert count == 0

    def test_exists_true(self, redis_cache):
        """Test exists returns True for existing key."""
        redis_cache._client.exists.return_value = 1
        assert redis_cache.exists("some_hash") is True

    def test_exists_false(self, redis_cache):
        """Test exists returns False for missing key."""
        redis_cache._client.exists.return_value = 0
        assert redis_cache.exists("missing") is False


class TestRedisCacheList:
    """Tests for list_keys."""

    def test_list_keys(self, redis_cache):
        """Test listing cache keys."""
        redis_cache._client.scan_iter.return_value = [
            f"{CACHE_KEY_PREFIX}hash1".encode(),
            f"{CACHE_KEY_PREFIX}hash2".encode(),
        ]
        redis_cache._client.ttl.return_value = 3600
        redis_cache._client.strlen.return_value = 1024

        entries = redis_cache.list_keys()
        assert len(entries) == 2
        assert entries[0]["hash"] == "hash1"
        assert entries[0]["ttl"] == 3600
        assert entries[0]["size"] == 1024

    def test_list_keys_empty(self, redis_cache):
        """Test listing when no keys exist."""
        redis_cache._client.scan_iter.return_value = []
        entries = redis_cache.list_keys()
        assert len(entries) == 0


class TestRedisCacheConnection:
    """Tests for connection handling."""

    def test_connection_error(self):
        """Test connection error handling."""
        cache = RedisCache(host="invalid-host", port=9999, password="wrong")

        with patch("vidscript.cache.redis_cache.redis") as mock_redis_module:
            mock_client = MagicMock()
            mock_client.ping.side_effect = Exception("Connection refused")
            mock_redis_module.Redis.return_value = mock_client

            with pytest.raises(RedisConnectionError, match="Gagal konek"):
                cache._get_client()

    def test_close(self, redis_cache):
        """Test closing connection."""
        redis_cache.close()
        assert redis_cache._client is None
