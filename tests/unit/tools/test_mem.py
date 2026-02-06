"""Tests for persistent memory tool pack.

Tests helpers, CRUD operations, safety features, and lifecycle functions
with mocked DuckDB and OpenAI.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ot_tools.mem import (
    Config,
    VALID_CATEGORIES,
    _cache_get,
    _cache_invalidate,
    _cache_put,
    _content_hash,
    _read_cache,
    _read_cache_lock,
    _redact,
    _topic_filter,
    _validate_category,
    _validate_tags,
)


@pytest.fixture()
def _mock_cwd(tmp_path: Path):
    """Mock CWD for path validation to use tmp_path."""
    with patch("ot.utils.pathsec.resolve_cwd_path") as mock_resolve:

        def _resolve(path: str) -> Path:
            p = Path(path).expanduser()
            if p.is_absolute():
                return p.resolve()
            return (tmp_path / p).resolve()

        mock_resolve.side_effect = _resolve
        yield


# ---------------------------------------------------------------------------
# Pure function tests (no mocking needed)
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestContentHash:
    """Test _content_hash SHA-256 helper."""

    def test_returns_hex_string(self):
        result = _content_hash("hello world")
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_input_same_hash(self):
        assert _content_hash("test") == _content_hash("test")

    def test_different_input_different_hash(self):
        assert _content_hash("hello") != _content_hash("world")


@pytest.mark.unit
@pytest.mark.tools
class TestTopicFilter:
    """Test _topic_filter SQL builder."""

    def test_none_returns_empty(self):
        sql, params = _topic_filter(None)
        assert sql == ""
        assert params == []

    def test_exact_match(self):
        sql, params = _topic_filter("projects/onetool")
        assert "topic = ?" in sql
        assert params == ["projects/onetool"]

    def test_prefix_match_with_trailing_slash(self):
        sql, params = _topic_filter("projects/")
        assert "topic = ?" in sql
        assert "topic LIKE ?" in sql
        assert "projects" in params
        assert "projects/%" in params

    def test_wildcard_match(self):
        sql, params = _topic_filter("projects/*/rules")
        assert "topic LIKE ?" in sql
        assert "projects/%/rules" in params


@pytest.mark.unit
@pytest.mark.tools
@patch("ot_tools.mem._get_config", return_value=Config())
class TestRedact:
    """Test _redact secret/PII redaction."""

    def test_redacts_api_keys(self, _mock_config):
        result = _redact("key: sk-abc123def456ghi789jkl0123")
        assert "sk-" not in result
        assert "[REDACTED:api_key]" in result

    def test_redacts_github_tokens(self, _mock_config):
        result = _redact("token: ghp_aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789")
        assert "ghp_" not in result
        assert "[REDACTED:github_token]" in result

    def test_redacts_passwords(self, _mock_config):
        result = _redact("password = mysecretpass123")
        assert "mysecretpass123" not in result
        assert "[REDACTED:password]" in result

    def test_redacts_connection_strings(self, _mock_config):
        result = _redact("url: postgres://user:pass@host/db")
        assert "user:pass" not in result
        assert "[REDACTED:connection_string]" in result

    def test_skips_redaction_when_disabled(self, mock_config):
        mock_config.return_value = Config(redaction_enabled=False)
        content = "key: sk-abc123def456ghi789jkl0123"
        assert _redact(content) == content


@pytest.mark.unit
@pytest.mark.tools
class TestValidateTags:
    """Test _validate_tags whitelist validation."""

    @patch("ot_tools.mem._get_config", return_value=Config(tags_whitelist=[]))
    def test_empty_whitelist_allows_all(self, _mock_config):
        assert _validate_tags(["any", "tag"]) == ["any", "tag"]

    @patch("ot_tools.mem._get_config", return_value=Config(tags_whitelist=["allowed"]))
    def test_whitelist_rejects_unknown(self, _mock_config):
        with pytest.raises(ValueError, match="not in whitelist"):
            _validate_tags(["forbidden"])

    @patch("ot_tools.mem._get_config", return_value=Config(tags_whitelist=["project/*"]))
    def test_whitelist_wildcard_prefix(self, _mock_config):
        assert _validate_tags(["project/onetool"]) == ["project/onetool"]

    def test_none_returns_empty(self):
        assert _validate_tags(None) == []


@pytest.mark.unit
@pytest.mark.tools
class TestValidateCategory:
    """Test _validate_category helper."""

    def test_valid_categories(self):
        for cat in VALID_CATEGORIES:
            assert _validate_category(cat) == cat

    def test_invalid_category_raises(self):
        with pytest.raises(ValueError, match="Invalid category"):
            _validate_category("invalid")


# ---------------------------------------------------------------------------
# Read cache tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestReadCache:
    """Test read cache get/put/invalidate."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        """Clear the read cache before and after each test."""
        with _read_cache_lock:
            _read_cache.clear()
        yield
        with _read_cache_lock:
            _read_cache.clear()

    @patch("ot_tools.mem._get_config", return_value=Config(read_cache_max_size=128, read_cache_ttl_seconds=300))
    def test_put_and_get(self, _mock_config):
        row = ("id-1", "topic/a", "content", "note", [], 5, 0)
        _cache_put("topic:topic/a", row)
        assert _cache_get("topic:topic/a") == row

    @patch("ot_tools.mem._get_config", return_value=Config(read_cache_max_size=128, read_cache_ttl_seconds=300))
    def test_miss_returns_none(self, _mock_config):
        assert _cache_get("topic:nonexistent") is None

    @patch("ot_tools.mem._get_config", return_value=Config(read_cache_max_size=0))
    def test_disabled_cache_never_stores(self, _mock_config):
        _cache_put("topic:a", ("row",))
        assert _cache_get("topic:a") is None

    @patch("ot_tools.mem._get_config", return_value=Config(read_cache_max_size=2, read_cache_ttl_seconds=300))
    def test_evicts_oldest_at_capacity(self, _mock_config):
        _cache_put("topic:a", ("row-a",))
        _cache_put("topic:b", ("row-b",))
        _cache_put("topic:c", ("row-c",))  # Should evict "a"
        assert _cache_get("topic:a") is None
        assert _cache_get("topic:b") is not None
        assert _cache_get("topic:c") is not None

    @patch("ot_tools.mem._get_config", return_value=Config(read_cache_max_size=128, read_cache_ttl_seconds=0))
    def test_ttl_zero_means_no_expiry(self, _mock_config):
        _cache_put("topic:a", ("row",))
        assert _cache_get("topic:a") is not None

    @patch("ot_tools.mem._get_config", return_value=Config(read_cache_max_size=128, read_cache_ttl_seconds=300))
    def test_invalidate_by_topic(self, _mock_config):
        _cache_put("topic:proj/a", ("row-a",))
        _cache_put("topic:proj/b", ("row-b",))
        _cache_put("topic:other/c", ("row-c",))
        _cache_invalidate(topic="proj/a")
        assert _cache_get("topic:proj/a") is None
        assert _cache_get("topic:proj/b") is not None
        assert _cache_get("topic:other/c") is not None

    @patch("ot_tools.mem._get_config", return_value=Config(read_cache_max_size=128, read_cache_ttl_seconds=300))
    def test_invalidate_by_topic_prefix(self, _mock_config):
        _cache_put("topic:proj/a", ("row-a",))
        _cache_put("topic:proj/b", ("row-b",))
        _cache_put("topic:other/c", ("row-c",))
        _cache_invalidate(topic="proj")
        # "proj" prefix invalidation removes proj/a and proj/b
        assert _cache_get("topic:proj/a") is None
        assert _cache_get("topic:proj/b") is None
        assert _cache_get("topic:other/c") is not None

    @patch("ot_tools.mem._get_config", return_value=Config(read_cache_max_size=128, read_cache_ttl_seconds=300))
    def test_invalidate_by_id_clears_all(self, _mock_config):
        _cache_put("topic:a", ("row-a",))
        _cache_put("id:123", ("row-123",))
        _cache_invalidate(id="123")
        # id invalidation clears entire cache (can't map id back to topic)
        assert _cache_get("topic:a") is None
        assert _cache_get("id:123") is None

    @patch("ot_tools.mem._get_config", return_value=Config(read_cache_max_size=128, read_cache_ttl_seconds=300))
    def test_invalidate_no_args_clears_all(self, _mock_config):
        _cache_put("topic:a", ("row-a",))
        _cache_put("topic:b", ("row-b",))
        _cache_invalidate()
        assert _cache_get("topic:a") is None
        assert _cache_get("topic:b") is None


@pytest.mark.unit
@pytest.mark.tools
class TestReadCacheIntegration:
    """Test that read() uses the cache."""

    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        with _read_cache_lock:
            _read_cache.clear()
        yield
        with _read_cache_lock:
            _read_cache.clear()

    @patch("ot_tools.mem._get_connection")
    def test_second_read_hits_cache(self, mock_conn):
        from ot_tools.mem import read

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-123", "test/topic", "cached content", "note",
            [], 5, 0, datetime.now(), datetime.now(),
        )

        # First read: cache miss
        result1 = read(topic="test/topic")
        assert result1 == "cached content"
        # SELECT was called
        select_calls_1 = len(conn.execute.call_args_list)

        # Second read: cache hit — should not add another SELECT
        result2 = read(topic="test/topic")
        assert result2 == "cached content"
        # Only the UPDATE (access_count) should have been added, no new SELECT
        select_calls_2 = len(conn.execute.call_args_list)
        # First read: 1 SELECT + 1 UPDATE = 2 calls. Second read: 1 UPDATE = 1 more call.
        assert select_calls_2 == select_calls_1 + 1


# ---------------------------------------------------------------------------
# CRUD operation tests with mocked DuckDB
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestWrite:
    """Test mem.write() with mocked database and embeddings."""

    @patch("ot_tools.mem._maybe_embed")
    @patch("ot_tools.mem._get_connection")
    def test_stores_new_memory(self, mock_conn, mock_embed):
        from ot_tools.mem import write

        mock_embed.return_value = None

        conn = MagicMock()
        mock_conn.return_value = conn
        # No duplicate found
        conn.execute.return_value.fetchone.return_value = None

        result = write(topic="test/topic", content="test content")

        assert "Stored memory" in result
        assert "test/topic" in result
        # Verify INSERT was called
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) == 1

    @patch("ot_tools.mem._get_connection")
    def test_rejects_duplicate(self, mock_conn):
        from ot_tools.mem import write

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = ("existing-id",)

        result = write(topic="test/topic", content="test content")

        assert "Duplicate" in result

    def test_rejects_invalid_category(self):
        from ot_tools.mem import write

        result = write(topic="test", content="test", category="invalid")
        assert "Error" in result
        assert "Invalid category" in result

    def test_rejects_both_content_and_file(self, tmp_path):
        from ot_tools.mem import write

        test_file = tmp_path / "test.txt"
        test_file.write_text("file content")

        result = write(topic="test", content="inline", file=str(test_file))
        assert result == "Error: Provide content or file, not both"

    def test_rejects_neither_content_nor_file(self):
        from ot_tools.mem import write

        result = write(topic="test")
        assert result == "Error: Provide content or file"

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._maybe_embed")
    @patch("ot_tools.mem._get_connection")
    def test_reads_from_file(self, mock_conn, mock_embed, tmp_path):
        from ot_tools.mem import write

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        test_file = tmp_path / "test.txt"
        test_file.write_text("file content")

        result = write(topic="test", file=str(test_file))

        assert "Stored memory" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._get_connection")
    def test_file_not_found(self, mock_conn, tmp_path):
        from ot_tools.mem import write

        conn = MagicMock()
        mock_conn.return_value = conn

        result = write(topic="test", file=str(tmp_path / "nonexistent.txt"))

        assert "Error" in result
        assert "not found" in result.lower()


@pytest.mark.unit
@pytest.mark.tools
class TestRead:
    """Test mem.read() with mocked database."""

    @patch("ot_tools.mem._get_connection")
    def test_reads_by_topic(self, mock_conn):
        from ot_tools.mem import read

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-123", "test/topic", "memory content", "note",
            ["tag1"], 5, 3, datetime.now(), datetime.now(),
        )

        result = read(topic="test/topic")

        assert result == "memory content"

    @patch("ot_tools.mem._get_connection")
    def test_reads_by_topic_with_meta(self, mock_conn):
        from ot_tools.mem import read

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-123", "test/topic", "memory content", "note",
            ["tag1"], 5, 3, datetime.now(), datetime.now(),
        )

        result = read(topic="test/topic", meta=True)

        assert "Topic: test/topic" in result
        assert "Category: note" in result
        assert "Tags: tag1" in result
        assert "memory content" in result
        assert "id-123" in result

    @patch("ot_tools.mem._get_connection")
    def test_reads_by_id(self, mock_conn):
        from ot_tools.mem import read

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (
            "id-123", "test/topic", "content", "rule",
            [], 7, 1, datetime.now(), datetime.now(),
        )

        result = read(topic="ignored", id="id-123")

        assert result == "content"

    @patch("ot_tools.mem._get_connection")
    def test_not_found(self, mock_conn):
        from ot_tools.mem import read

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        result = read(topic="nonexistent")

        assert "No memory found" in result


@pytest.mark.unit
@pytest.mark.tools
class TestReadBatch:
    """Test mem.read_batch() with mocked database."""

    @patch("ot_tools.mem._get_connection")
    def test_reads_by_topic_prefix(self, mock_conn):
        from ot_tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/a", "content a", "note", ["tag1"], 5, 2, datetime.now(), datetime.now()),
            ("id-2", "proj/b", "content b", "rule", [], 8, 0, datetime.now(), datetime.now()),
        ]

        result = read_batch(topic="proj/")

        assert "Read 2 memories" in result
        assert "content a" in result
        assert "content b" in result

    @patch("ot_tools.mem._get_connection")
    def test_reads_by_ids(self, mock_conn):
        from ot_tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/a", "content a", "note", [], 5, 1, datetime.now(), datetime.now()),
        ]

        result = read_batch(ids=["id-1"])

        assert "Read 1 memory" in result
        assert "content a" in result

    @patch("ot_tools.mem._get_connection")
    def test_reads_with_meta(self, mock_conn):
        from ot_tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/a", "content a", "note", ["tag1"], 5, 3, datetime.now(), datetime.now()),
        ]

        result = read_batch(topic="proj/", meta=True)

        assert "Topic: proj/a" in result
        assert "Category: note" in result
        assert "Tags: tag1" in result
        assert "content a" in result

    @patch("ot_tools.mem._get_connection")
    def test_empty_result(self, mock_conn):
        from ot_tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = read_batch(topic="nonexistent/")

        assert "No memories found" in result

    def test_requires_filter(self):
        from ot_tools.mem import read_batch

        result = read_batch()

        assert "Error" in result
        assert "At least one filter" in result

    def test_ids_rejects_combined_with_topic(self):
        from ot_tools.mem import read_batch

        result = read_batch(ids=["id-1"], topic="proj/")

        assert "Error" in result
        assert "ids cannot be combined" in result

    def test_ids_rejects_combined_with_category(self):
        from ot_tools.mem import read_batch

        result = read_batch(ids=["id-1"], category="rule")

        assert "Error" in result
        assert "ids cannot be combined" in result

    def test_ids_rejects_combined_with_tags(self):
        from ot_tools.mem import read_batch

        result = read_batch(ids=["id-1"], tags=["tag1"])

        assert "Error" in result
        assert "ids cannot be combined" in result

    @patch("ot_tools.mem._get_connection")
    def test_filters_by_category(self, mock_conn):
        from ot_tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/a", "rule content", "rule", [], 5, 1, datetime.now(), datetime.now()),
        ]

        result = read_batch(category="rule")

        assert "Read 1 memory" in result
        assert "rule content" in result
        # Verify SQL includes category filter
        sql_arg = conn.execute.call_args_list[0][0][0]
        assert "category = ?" in sql_arg

    @patch("ot_tools.mem._get_connection")
    def test_filters_by_tags(self, mock_conn):
        from ot_tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/a", "tagged content", "note", ["tag1"], 5, 1, datetime.now(), datetime.now()),
        ]

        result = read_batch(tags=["tag1"])

        assert "Read 1 memory" in result
        assert "tagged content" in result
        sql_arg = conn.execute.call_args_list[0][0][0]
        assert "list_has_any(tags, ?)" in sql_arg

    @patch("ot_tools.mem._get_connection")
    def test_combined_topic_and_category(self, mock_conn):
        from ot_tools.mem import read_batch

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "proj/a", "combined content", "rule", [], 5, 1, datetime.now(), datetime.now()),
        ]

        result = read_batch(topic="proj/", category="rule")

        assert "Read 1 memory" in result
        sql_arg = conn.execute.call_args_list[0][0][0]
        assert "category = ?" in sql_arg
        assert "topic" in sql_arg


@pytest.mark.unit
@pytest.mark.tools
class TestSearch:
    """Test mem.search() with mocked database and embeddings."""

    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=True))
    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_semantic_search(self, mock_conn, mock_embed, _mock_config):
        from ot_tools.mem import search

        mock_embed.return_value = [0.1] * 1536

        conn = MagicMock()
        mock_conn.return_value = conn
        # First execute: has_embeddings check; second: actual search
        conn.execute.return_value.fetchone.return_value = (1,)
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "content one", "note", ["tag"], 5, 2, 0.95),
        ]

        result = search(query="test query")

        assert "Found 1 memories" in result
        assert "topic/one" in result
        assert "0.95" in result

    @patch("ot_tools.mem._get_connection")
    def test_pattern_search(self, mock_conn):
        from ot_tools.mem import search

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "matching content", "note", [], 5, 1),
        ]

        result = search(query="matching", mode="pattern")

        assert "Found 1 memories" in result

    def test_invalid_mode(self):
        from ot_tools.mem import search

        result = search(query="test", mode="invalid")
        assert "Error" in result
        assert "Invalid mode" in result

    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=True))
    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_no_results(self, mock_conn, mock_embed, _mock_config):
        from ot_tools.mem import search

        mock_embed.return_value = [0.1] * 1536
        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (1,)
        conn.execute.return_value.fetchall.return_value = []

        result = search(query="nothing")

        assert "No memories found" in result

    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=True))
    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_search_custom_extract(self, mock_conn, mock_embed, _mock_config):
        from ot_tools.mem import search

        mock_embed.return_value = [0.1] * 1536
        long_content = "a" * 500

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (1,)
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", long_content, "note", [], 5, 1, 0.9),
        ]

        result = search(query="test", extract=50)

        # Should truncate to 50 chars + "..."
        assert "a" * 50 in result
        assert "a" * 51 not in result
        assert "..." in result

    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=True))
    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_search_extract_zero_returns_full(self, mock_conn, mock_embed, _mock_config):
        from ot_tools.mem import search

        mock_embed.return_value = [0.1] * 1536
        long_content = "a" * 500

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (1,)
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", long_content, "note", [], 5, 1, 0.9),
        ]

        result = search(query="test", extract=0)

        assert "a" * 500 in result
        assert "..." not in result


# ---------------------------------------------------------------------------
# Optional embeddings tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestMaybeEmbed:
    """Test _maybe_embed helper with different config states."""

    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=False))
    def test_disabled_returns_none(self, _mock_config):
        from ot_tools.mem import _maybe_embed

        result = _maybe_embed("mem-id", "some content")
        assert result is None

    @patch("ot_tools.mem._generate_embedding", return_value=[0.1, 0.2, 0.3])
    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=True, embeddings_async=False))
    def test_sync_returns_vector(self, _mock_config, _mock_embed):
        from ot_tools.mem import _maybe_embed

        result = _maybe_embed("mem-id", "some content")
        assert result == [0.1, 0.2, 0.3]

    @patch("ot_tools.mem._enqueue_embedding")
    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=True, embeddings_async=True))
    def test_async_enqueues_and_returns_none(self, _mock_config, mock_enqueue):
        from ot_tools.mem import _maybe_embed

        result = _maybe_embed("mem-id", "some content")
        assert result is None
        mock_enqueue.assert_called_once_with("mem-id")


@pytest.mark.unit
@pytest.mark.tools
class TestSearchEmbeddingsDisabled:
    """Test search returns helpful messages when embeddings disabled."""

    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=False))
    def test_semantic_search_returns_message(self, _mock_config):
        from ot_tools.mem import search

        result = search(query="test query")
        assert "embeddings_enabled" in result

    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=False))
    def test_hybrid_search_returns_message(self, _mock_config):
        from ot_tools.mem import search

        result = search(query="test query", mode="hybrid")
        assert "embeddings_enabled" in result

    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=False))
    @patch("ot_tools.mem._get_connection")
    def test_pattern_search_works_when_disabled(self, mock_conn, _mock_config):
        from ot_tools.mem import search

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "matching content", "note", [], 5, 1),
        ]

        result = search(query="matching", mode="pattern")
        assert "Found 1 memories" in result


@pytest.mark.unit
@pytest.mark.tools
class TestSearchNoEmbeddings:
    """Test search returns guidance when enabled but no embeddings exist."""

    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=True))
    @patch("ot_tools.mem._get_connection")
    def test_semantic_no_embeddings_returns_guidance(self, mock_conn, _mock_config):
        from ot_tools.mem import search

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = None  # No embeddings exist

        result = search(query="test query")
        assert "mem.embed" in result


@pytest.mark.unit
@pytest.mark.tools
class TestWriteWithoutEmbeddings:
    """Test that write stores NULL embedding when disabled."""

    @patch("ot_tools.mem._maybe_embed", return_value=None)
    @patch("ot_tools.mem._get_connection")
    def test_write_stores_null_embedding(self, mock_conn, _mock_embed):
        from ot_tools.mem import write

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = None  # No duplicate

        result = write(topic="test/topic", content="test content")

        assert "Stored memory" in result
        # Verify embedding parameter is None in INSERT
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) == 1
        insert_params = insert_calls[0][0][1]
        assert insert_params[7] is None  # embedding is 8th parameter


@pytest.mark.unit
@pytest.mark.tools
class TestEmbedFunction:
    """Test mem.embed() backfill function."""

    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=False))
    def test_disabled_returns_message(self, _mock_config):
        from ot_tools.mem import embed

        result = embed()
        assert "disabled" in result.lower()

    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=True))
    @patch("ot_tools.mem._get_connection")
    def test_dry_run_shows_count(self, mock_conn, _mock_config):
        from ot_tools.mem import embed

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "content one"),
            ("id-2", "content two"),
        ]

        result = embed(dry_run=True)
        assert "2 memories" in result

    @patch("ot_tools.mem._generate_embedding", return_value=[0.1] * 1536)
    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=True))
    @patch("ot_tools.mem._get_connection")
    def test_generates_embeddings(self, mock_conn, _mock_config, _mock_embed):
        from ot_tools.mem import embed

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "content one"),
        ]

        result = embed(dry_run=False)
        assert "Generated embeddings for 1 memories" in result

    @patch("ot_tools.mem._get_config", return_value=Config(embeddings_enabled=True))
    @patch("ot_tools.mem._get_connection")
    def test_all_embedded_returns_message(self, mock_conn, _mock_config):
        from ot_tools.mem import embed

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = embed()
        assert "already have embeddings" in result


@pytest.mark.unit
@pytest.mark.tools
class TestFlush:
    """Test mem.flush() queue drain."""

    def test_no_worker_returns_immediately(self):
        from ot_tools.mem import flush

        result = flush()
        assert "No background embeddings pending" in result


@pytest.mark.unit
@pytest.mark.tools
class TestListMemories:
    """Test mem.list_memories() with mocked database."""

    @patch("ot_tools.mem._get_connection")
    def test_lists_memories(self, mock_conn):
        from ot_tools.mem import list_memories

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "note", ["tag1"], 5, 2, datetime.now(), 100),
            ("id-2", "topic/two", "rule", [], 8, 0, datetime.now(), 200),
        ]

        result = list_memories()

        assert "Found 2 memories" in result
        assert "topic/one" in result
        assert "topic/two" in result

    @patch("ot_tools.mem._get_connection")
    def test_empty_list(self, mock_conn):
        from ot_tools.mem import list_memories

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = list_memories()

        assert "No memories found" in result


@pytest.mark.unit
@pytest.mark.tools
class TestCount:
    """Test mem.count() with mocked database."""

    @patch("ot_tools.mem._get_connection")
    def test_counts_all(self, mock_conn):
        from ot_tools.mem import count

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (42,)

        result = count()

        assert result == "42"


@pytest.mark.unit
@pytest.mark.tools
class TestDelete:
    """Test mem.delete() with mocked database."""

    @patch("ot_tools.mem._get_connection")
    def test_deletes_by_id(self, mock_conn):
        from ot_tools.mem import delete

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = ("id-123",)

        result = delete(id="id-123")

        assert "Deleted memory id-123" in result

    @patch("ot_tools.mem._get_connection")
    def test_requires_confirm_for_multi_delete(self, mock_conn):
        from ot_tools.mem import delete

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (5,)

        result = delete(topic="projects/")

        assert "confirm=True" in result

    def test_requires_topic_or_id(self):
        from ot_tools.mem import delete

        result = delete()
        assert "Error" in result
        assert "Must specify" in result


@pytest.mark.unit
@pytest.mark.tools
class TestUpdate:
    """Test mem.update() with mocked database and embeddings."""

    @patch("ot_tools.mem._maybe_embed")
    @patch("ot_tools.mem._get_connection")
    def test_updates_single_match(self, mock_conn, mock_embed):
        from ot_tools.mem import update

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-123", "old content"),
        ]

        result = update(topic="test/topic", content="new content")

        assert "Updated memory" in result

    @patch("ot_tools.mem._get_connection")
    def test_rejects_multiple_matches(self, mock_conn):
        from ot_tools.mem import update

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "content 1"),
            ("id-2", "content 2"),
        ]

        result = update(topic="ambiguous/topic", content="new")

        assert "Multiple memories" in result

    @patch("ot_tools.mem._get_connection")
    def test_not_found(self, mock_conn):
        from ot_tools.mem import update

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = update(topic="nonexistent", content="new")

        assert "No memory found" in result


@pytest.mark.unit
@pytest.mark.tools
class TestAppend:
    """Test mem.append() with mocked database and embeddings."""

    @patch("ot_tools.mem._maybe_embed")
    @patch("ot_tools.mem._get_connection")
    def test_appends_content(self, mock_conn, mock_embed):
        from ot_tools.mem import append

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value = conn

        # Mock for single match via fetchall
        conn.execute.return_value.fetchall.return_value = [
            ("id-123", "original content"),
        ]

        result = append(topic="test/topic", content="appended text")

        assert "Appended to memory" in result


# ---------------------------------------------------------------------------
# Phase 2 tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestContext:
    """Test mem.context() hot cache loading."""

    @patch("ot_tools.mem._get_connection")
    def test_loads_top_accessed(self, mock_conn):
        from ot_tools.mem import context

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "hot/topic", "frequently accessed content", "rule", ["tag"], 8, 100),
        ]

        result = context()

        assert "1 memories loaded" in result
        assert "hot/topic" in result
        assert "frequently accessed content" in result

    @patch("ot_tools.mem._get_connection")
    def test_empty_context(self, mock_conn):
        from ot_tools.mem import context

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = context()

        assert "No memories found" in result


# ---------------------------------------------------------------------------
# Phase 3 tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestUpdateBatch:
    """Test mem.update_batch() search-and-replace."""

    @patch("ot_tools.mem._get_connection")
    def test_dry_run_preview(self, mock_conn):
        from ot_tools.mem import update_batch

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "old_name is used here"),
            ("id-2", "topic/two", "old_name appears twice: old_name"),
        ]

        result = update_batch(search_text="old_name", replace_text="new_name")

        assert "Dry run" in result
        assert "2 memories" in result

    @patch("ot_tools.mem._get_connection")
    def test_no_matches(self, mock_conn):
        from ot_tools.mem import update_batch

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = update_batch(search_text="nonexistent", replace_text="new")

        assert "No memories contain" in result


@pytest.mark.unit
@pytest.mark.tools
class TestDecay:
    """Test mem.decay() importance decay."""

    @patch("ot_tools.mem._get_connection")
    def test_decay_dry_run(self, mock_conn):
        from ot_tools.mem import decay

        conn = MagicMock()
        mock_conn.return_value = conn
        # Memory created 60 days ago, accessed 0 times, relevance 10
        old_time = datetime(2025, 12, 1, tzinfo=timezone.utc)
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "old/topic", 10, 0, old_time),
        ]

        result = decay(dry_run=True)

        assert "Decay preview" in result

    @patch("ot_tools.mem._get_connection")
    def test_empty_decay(self, mock_conn):
        from ot_tools.mem import decay

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = decay()

        assert "No memories to decay" in result


@pytest.mark.unit
@pytest.mark.tools
class TestStats:
    """Test mem.stats() statistics."""

    @patch("ot_tools.mem._get_connection")
    def test_shows_statistics(self, mock_conn):
        from ot_tools.mem import stats

        conn = MagicMock()
        mock_conn.return_value = conn

        # Mock different queries in sequence
        conn.execute.return_value.fetchone.side_effect = [
            (10,),           # total count
            (5000, 500, 2000),  # size stats
            (3,),            # history count
            (2,),            # without embeddings count
        ]
        conn.execute.return_value.fetchall.side_effect = [
            [("note", 5), ("rule", 3), ("decision", 2)],  # categories
            [("projects", 7), ("learnings", 3)],           # topics
        ]

        result = stats()

        assert "10" in result
        assert "Memory Statistics" in result
        assert "Embeddings:" in result

    @patch("ot_tools.mem._get_connection")
    def test_empty_stats(self, mock_conn):
        from ot_tools.mem import stats

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = (0,)

        result = stats()

        assert "No memories stored" in result


@pytest.mark.unit
@pytest.mark.tools
class TestExport:
    """Test mem.export() YAML output."""

    @patch("ot_tools.mem._get_connection")
    def test_export_yaml(self, mock_conn):
        from ot_tools.mem import export

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "content one", "note", ["tag1"], 5, 2, datetime.now(), datetime.now()),
        ]

        result = export()

        assert "memories:" in result
        assert "topic/one" in result
        assert "content one" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._get_connection")
    def test_export_to_file(self, mock_conn, tmp_path):
        from ot_tools.mem import export

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "content", "note", [], 5, 0, datetime.now(), datetime.now()),
        ]

        out_file = tmp_path / "export.yaml"
        result = export(output=str(out_file))

        assert "Exported 1 memories" in result
        assert out_file.exists()

    @patch("ot_tools.mem._get_connection")
    def test_empty_export(self, mock_conn):
        from ot_tools.mem import export

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = export()

        assert "No memories to export" in result


@pytest.mark.unit
@pytest.mark.tools
class TestLoad:
    """Test mem.load() YAML import."""

    @pytest.mark.usefixtures("_mock_cwd")
    def test_file_not_found(self, tmp_path):
        from ot_tools.mem import load

        result = load(file=str(tmp_path / "nonexistent.yaml"))
        assert "Error" in result
        assert "not found" in result.lower()

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._maybe_embed")
    @patch("ot_tools.mem._get_connection")
    def test_imports_from_yaml(self, mock_conn, mock_embed, tmp_path):
        from ot_tools.mem import load

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = None  # No existing

        yaml_file = tmp_path / "memories.yaml"
        yaml_file.write_text(
            'memories:\n'
            '  - topic: "test/topic"\n'
            '    content: "imported content"\n'
            '    category: "note"\n'
            '    tags: ["imported"]\n'
            '    relevance: 7\n'
        )

        result = load(file=str(yaml_file))

        assert "Imported 1 memories" in result


@pytest.mark.unit
@pytest.mark.tools
class TestSnap:
    """Test mem.snap() file-based export."""

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._get_connection")
    def test_snapshot_creates_files_and_index(self, mock_conn, tmp_path):
        from ot_tools.mem import snap

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "docs/readme", "# README content", "note", ["tag1"], 5, 2,
             datetime.now(), datetime.now()),
        ]

        out_dir = tmp_path / "backup"
        result = snap(output=str(out_dir))

        assert "Snap 1 memories" in result
        assert (out_dir / "docs/readme.md").exists()
        assert (out_dir / "docs/readme.md").read_text() == "# README content"
        assert (out_dir / "index.yaml").exists()
        index_text = (out_dir / "index.yaml").read_text()
        assert "docs/readme" in index_text
        assert "docs/readme.md" in index_text

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._get_connection")
    def test_snapshot_with_topic_filter(self, mock_conn, tmp_path):
        from ot_tools.mem import snap

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "consult/ask", "ask content", "note", [], 5, 0,
             datetime.now(), datetime.now()),
            ("id-2", "consult/mem-tool", "mem content", "discovery", [], 7, 1,
             datetime.now(), datetime.now()),
        ]

        out_dir = tmp_path / "snap"
        result = snap(output=str(out_dir), topic="consult/")

        assert "Snap 2 memories" in result
        # Topic prefix stripped: "consult/ask" -> "ask.md"
        assert (out_dir / "ask.md").exists()
        assert (out_dir / "mem-tool.md").exists()

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._get_connection")
    def test_snapshot_skip_existing(self, mock_conn, tmp_path):
        from ot_tools.mem import snap

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "notes/a", "content a", "note", [], 5, 0,
             datetime.now(), datetime.now()),
        ]

        out_dir = tmp_path / "snap"
        out_dir.mkdir()
        (out_dir / "notes").mkdir()
        (out_dir / "notes/a.md").write_text("existing")

        result = snap(output=str(out_dir), on_conflict="skip")

        assert "1 skipped" in result
        assert (out_dir / "notes/a.md").read_text() == "existing"

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._get_connection")
    def test_snapshot_overwrite_existing(self, mock_conn, tmp_path):
        from ot_tools.mem import snap

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "notes/a", "new content", "note", [], 5, 0,
             datetime.now(), datetime.now()),
        ]

        out_dir = tmp_path / "snap"
        out_dir.mkdir()
        (out_dir / "notes").mkdir()
        (out_dir / "notes/a.md").write_text("old content")

        result = snap(output=str(out_dir), on_conflict="overwrite")

        assert "1 written" in result
        assert (out_dir / "notes/a.md").read_text() == "new content"

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._get_connection")
    def test_snapshot_nested_topics(self, mock_conn, tmp_path):
        from ot_tools.mem import snap

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "consult/sub/deep", "deep content", "rule", ["important"], 9, 0,
             datetime.now(), datetime.now()),
        ]

        out_dir = tmp_path / "snap"
        result = snap(output=str(out_dir), topic="consult/")

        assert "Snap 1 memories" in result
        assert (out_dir / "sub/deep.md").exists()
        assert (out_dir / "sub/deep.md").read_text() == "deep content"


@pytest.mark.unit
@pytest.mark.tools
class TestRestore:
    """Test mem.restore() from snapshot directory."""

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._maybe_embed")
    @patch("ot_tools.mem._get_connection")
    def test_restore_from_snapshot(self, mock_conn, mock_embed, tmp_path):
        from ot_tools.mem import restore

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = None  # No existing

        # Create snapshot directory
        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()
        (snap_dir / "ask.md").write_text("ask content")
        (snap_dir / "index.yaml").write_text(
            'snapshot:\n'
            '  topic_filter: "consult/"\n'
            '  count: 1\n'
            'memories:\n'
            '  - topic: "consult/ask"\n'
            '    file: "ask.md"\n'
            '    category: "note"\n'
            '    tags: ["research"]\n'
            '    relevance: 7\n'
        )

        result = restore(input=str(snap_dir))

        assert "Restored 1 memories" in result
        # Verify INSERT was called with correct topic and metadata
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        assert len(insert_calls) == 1
        insert_params = insert_calls[0][0][1]
        assert insert_params[1] == "consult/ask"  # topic
        assert insert_params[4] == "note"  # category
        assert insert_params[5] == ["research"]  # tags
        assert insert_params[6] == 7  # relevance

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._maybe_embed")
    @patch("ot_tools.mem._get_connection")
    def test_restore_skips_duplicates(self, mock_conn, mock_embed, tmp_path):
        from ot_tools.mem import restore

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = ("existing-id",)  # Already exists

        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()
        (snap_dir / "a.md").write_text("content")
        (snap_dir / "index.yaml").write_text(
            'memories:\n'
            '  - topic: "test/a"\n'
            '    file: "a.md"\n'
            '    category: "note"\n'
            '    tags: []\n'
            '    relevance: 5\n'
        )

        result = restore(input=str(snap_dir))

        assert "skipped 1" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._maybe_embed")
    @patch("ot_tools.mem._get_connection")
    def test_restore_overwrite(self, mock_conn, mock_embed, tmp_path):
        from ot_tools.mem import restore

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = ("existing-id",)

        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()
        (snap_dir / "a.md").write_text("new content")
        (snap_dir / "index.yaml").write_text(
            'memories:\n'
            '  - topic: "test/a"\n'
            '    file: "a.md"\n'
            '    category: "note"\n'
            '    tags: []\n'
            '    relevance: 5\n'
        )

        result = restore(input=str(snap_dir), overwrite=True)

        assert "Restored 1 memories" in result
        # Should have DELETE + INSERT
        delete_calls = [c for c in conn.execute.call_args_list if "DELETE" in str(c)]
        assert len(delete_calls) >= 1

    @pytest.mark.usefixtures("_mock_cwd")
    def test_restore_missing_index(self, tmp_path):
        from ot_tools.mem import restore

        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()

        result = restore(input=str(snap_dir))

        assert "Error" in result
        assert "index.yaml" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._get_connection")
    def test_restore_missing_file(self, mock_conn, tmp_path):
        from ot_tools.mem import restore

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()
        (snap_dir / "index.yaml").write_text(
            'memories:\n'
            '  - topic: "test/a"\n'
            '    file: "missing.md"\n'
            '    category: "note"\n'
            '    tags: []\n'
            '    relevance: 5\n'
        )

        result = restore(input=str(snap_dir))

        assert "1 errors" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._maybe_embed")
    @patch("ot_tools.mem._get_connection")
    def test_restore_topic_override(self, mock_conn, mock_embed, tmp_path):
        from ot_tools.mem import restore

        mock_embed.return_value = None
        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchone.return_value = None

        snap_dir = tmp_path / "snap"
        snap_dir.mkdir()
        (snap_dir / "ask.md").write_text("content")
        (snap_dir / "index.yaml").write_text(
            'snapshot:\n'
            '  topic_filter: "consult/"\n'
            'memories:\n'
            '  - topic: "consult/ask"\n'
            '    file: "ask.md"\n'
            '    category: "note"\n'
            '    tags: []\n'
            '    relevance: 5\n'
        )

        result = restore(input=str(snap_dir), topic="new-base")

        assert "Restored 1 memories" in result
        insert_calls = [c for c in conn.execute.call_args_list if "INSERT" in str(c)]
        insert_params = insert_calls[0][0][1]
        assert insert_params[1] == "new-base/ask"  # remapped topic


# ---------------------------------------------------------------------------
# OpenAI client tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestGetOpenAIClient:
    """Test _get_openai_client function."""

    @patch("ot_tools.mem.get_secret")
    def test_raises_without_api_key(self, mock_secret):
        from ot_tools.mem import _get_openai_client

        mock_secret.return_value = ""

        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            _get_openai_client()

    @patch("openai.OpenAI")
    @patch("ot_tools.mem.get_secret")
    def test_creates_client_with_key(self, mock_secret, mock_openai):
        from ot_tools.mem import _get_openai_client

        mock_secret.return_value = "sk-test"

        _get_openai_client()

        mock_openai.assert_called_once()


@pytest.mark.unit
@pytest.mark.tools
class TestChunkTextByTokens:
    """Test _chunk_text_by_tokens token-aware splitting."""

    def test_short_text_single_chunk(self):
        from ot_tools.mem import _chunk_text_by_tokens

        chunks = _chunk_text_by_tokens("hello world", 8191, "text-embedding-3-small")
        assert chunks == ["hello world"]

    def test_long_text_splits_into_chunks(self):
        from ot_tools.mem import _chunk_text_by_tokens

        text = "word " * 20000  # ~20000 tokens
        chunks = _chunk_text_by_tokens(text, 100, "text-embedding-3-small")
        assert len(chunks) > 1
        # Each chunk should decode back to valid text
        for chunk in chunks:
            assert isinstance(chunk, str)
            assert len(chunk) > 0

    def test_exact_limit_single_chunk(self):
        from ot_tools.mem import _chunk_text_by_tokens

        import tiktoken

        encoding = tiktoken.encoding_for_model("text-embedding-3-small")
        text = "hello world this is a test"
        token_count = len(encoding.encode(text))
        chunks = _chunk_text_by_tokens(text, token_count, "text-embedding-3-small")
        assert chunks == [text]

    def test_unknown_model_falls_back(self):
        from ot_tools.mem import _chunk_text_by_tokens

        chunks = _chunk_text_by_tokens("hello world", 8191, "unknown-model-xyz")
        assert chunks == ["hello world"]

    def test_chunks_cover_all_content(self):
        from ot_tools.mem import _chunk_text_by_tokens

        import tiktoken

        encoding = tiktoken.encoding_for_model("text-embedding-3-small")
        text = "word " * 500  # moderate text
        chunks = _chunk_text_by_tokens(text, 100, "text-embedding-3-small")
        # Rejoin all chunk tokens — should equal original tokens
        original_tokens = encoding.encode(text)
        chunk_tokens = []
        for chunk in chunks:
            chunk_tokens.extend(encoding.encode(chunk))
        assert len(chunk_tokens) == len(original_tokens)


@pytest.mark.unit
@pytest.mark.tools
class TestGenerateEmbedding:
    """Test _generate_embedding function."""

    @patch("ot_tools.mem._get_openai_client")
    def test_generates_embedding_short_text(self, mock_client):
        from ot_tools.mem import _generate_embedding

        mock_openai = MagicMock()
        mock_client.return_value = mock_openai

        mock_response = MagicMock()
        mock_response.data = [MagicMock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        mock_openai.embeddings.create.return_value = mock_response

        result = _generate_embedding("test text")

        assert result == [0.1, 0.2, 0.3]
        mock_openai.embeddings.create.assert_called_once()

    @patch("ot_tools.mem._chunk_text_by_tokens")
    @patch("ot_tools.mem._get_openai_client")
    def test_averages_multi_chunk_embeddings(self, mock_client, mock_chunk):
        from ot_tools.mem import _generate_embedding

        # Simulate text splitting into 2 chunks
        mock_chunk.return_value = ["chunk one", "chunk two"]

        mock_openai = MagicMock()
        mock_client.return_value = mock_openai

        # API returns 2 embeddings (one per chunk)
        embed1 = MagicMock()
        embed1.embedding = [1.0, 0.0, 0.0]
        embed2 = MagicMock()
        embed2.embedding = [0.0, 1.0, 0.0]
        mock_response = MagicMock()
        mock_response.data = [embed1, embed2]
        mock_openai.embeddings.create.return_value = mock_response

        result = _generate_embedding("very long text")

        # Should average the two vectors
        assert result == [0.5, 0.5, 0.0]
        # Should pass both chunks as a batch
        call_kwargs = mock_openai.embeddings.create.call_args[1]
        assert call_kwargs["input"] == ["chunk one", "chunk two"]

    @patch("ot_tools.mem._chunk_text_by_tokens")
    @patch("ot_tools.mem._get_openai_client")
    def test_single_chunk_passes_string_not_list(self, mock_client, mock_chunk):
        from ot_tools.mem import _generate_embedding

        mock_chunk.return_value = ["short text"]

        mock_openai = MagicMock()
        mock_client.return_value = mock_openai
        mock_response = MagicMock()
        mock_response.data = [MagicMock()]
        mock_response.data[0].embedding = [0.1, 0.2, 0.3]
        mock_openai.embeddings.create.return_value = mock_response

        _generate_embedding("short text")

        # Single chunk: should pass string directly, not a list
        call_kwargs = mock_openai.embeddings.create.call_args[1]
        assert call_kwargs["input"] == "short text"

    def test_safety_margin_applied(self):
        from ot_tools.mem import _TOKEN_SAFETY_MARGIN

        assert _TOKEN_SAFETY_MARGIN == 100


# ---------------------------------------------------------------------------
# Path security tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
@pytest.mark.usefixtures("_mock_cwd")
class TestFilePathSecurity:
    """Test that file operations reject paths outside allowed directories."""

    def test_write_rejects_absolute_path_outside_cwd(self):
        from ot_tools.mem import write

        result = write(topic="test", file="/etc/passwd")

        assert "Error" in result
        assert "outside allowed directories" in result

    def test_write_rejects_path_traversal(self, tmp_path):
        from ot_tools.mem import write

        result = write(topic="test", file="../../../etc/passwd")

        assert "Error" in result
        # Rejected by path validation (either "not found" or "outside allowed")
        assert "not found" in result.lower() or "outside allowed" in result

    def test_write_rejects_home_dir_file(self):
        from ot_tools.mem import write

        result = write(topic="test", file="~/.ssh/id_rsa")

        assert "Error" in result
        assert "not found" in result.lower() or "outside allowed" in result

    @patch("ot_tools.mem._get_connection")
    def test_export_rejects_path_outside_cwd(self, mock_conn):
        from ot_tools.mem import export

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "content", "note", [], 5, 0, datetime.now(), datetime.now()),
        ]

        result = export(output="/tmp/evil_export.yaml")

        assert "Error" in result
        assert "outside allowed directories" in result

    def test_load_rejects_path_outside_cwd(self):
        from ot_tools.mem import load

        result = load(file="/etc/shadow")

        assert "Error" in result
        assert "not found" in result.lower() or "outside allowed" in result

    def test_write_rejects_excluded_pattern(self, tmp_path):
        from ot_tools.mem import write

        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        config = git_dir / "config"
        config.write_text("secret")

        result = write(topic="test", file=str(config))

        assert "Error" in result
        assert "exclude pattern" in result


# ---------------------------------------------------------------------------
# Validation and safety fix tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestWriteValidation:
    """Test write() input validation for relevance and file size."""

    def test_rejects_relevance_below_range(self):
        from ot_tools.mem import write

        result = write(topic="test", content="x", relevance=0)
        assert "Error" in result
        assert "relevance" in result

    def test_rejects_relevance_above_range(self):
        from ot_tools.mem import write

        result = write(topic="test", content="x", relevance=11)
        assert "Error" in result
        assert "relevance" in result

    @pytest.mark.usefixtures("_mock_cwd")
    @patch("ot_tools.mem._get_connection")
    def test_rejects_large_file(self, mock_conn, tmp_path):
        from ot_tools.mem import write

        conn = MagicMock()
        mock_conn.return_value = conn

        big_file = tmp_path / "big.txt"
        big_file.write_bytes(b"x" * 1_100_000)

        result = write(topic="test", file=str(big_file))

        assert "Error" in result
        assert "too large" in result.lower()

    def test_empty_string_content_accepted(self):
        """Empty string content is explicitly provided, should not be confused with None."""
        from ot_tools.mem import write

        # Empty content should hit category/relevance validation or DB, not "Provide content or file"
        result = write(topic="test", content="", relevance=0)
        assert "relevance" in result  # hits relevance check, not "Provide content"


@pytest.mark.unit
@pytest.mark.tools
class TestExportYaml:
    """Test _export_yaml handles multi-line content."""

    def test_multiline_content_uses_block_scalar(self):
        from ot_tools.mem import _export_yaml

        rows = [
            ("id-1", "topic/one", "line one\nline two\nline three", "note", ["tag"], 5, 2, datetime.now(), datetime.now()),
        ]

        result = _export_yaml(rows)

        assert "content: |-" in result
        assert "      line one" in result
        assert "      line two" in result
        # Should NOT have broken YAML double-quoted strings
        assert 'content: "' not in result
