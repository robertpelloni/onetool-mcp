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
    _content_hash,
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
# CRUD operation tests with mocked DuckDB
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestWrite:
    """Test mem.write() with mocked database and embeddings."""

    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_stores_new_memory(self, mock_conn, mock_embed):
        from ot_tools.mem import write

        mock_embed.return_value = [0.1] * 1536

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
    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_reads_from_file(self, mock_conn, mock_embed, tmp_path):
        from ot_tools.mem import write

        mock_embed.return_value = [0.1] * 1536
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

    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_semantic_search(self, mock_conn, mock_embed):
        from ot_tools.mem import search

        mock_embed.return_value = [0.1] * 1536

        conn = MagicMock()
        mock_conn.return_value = conn
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

    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_no_results(self, mock_conn, mock_embed):
        from ot_tools.mem import search

        mock_embed.return_value = [0.1] * 1536
        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = []

        result = search(query="nothing")

        assert "No memories found" in result

    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_search_custom_extract(self, mock_conn, mock_embed):
        from ot_tools.mem import search

        mock_embed.return_value = [0.1] * 1536
        long_content = "a" * 500

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", long_content, "note", [], 5, 1, 0.9),
        ]

        result = search(query="test", extract=50)

        # Should truncate to 50 chars + "..."
        assert "a" * 50 in result
        assert "a" * 51 not in result
        assert "..." in result

    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_search_extract_zero_returns_full(self, mock_conn, mock_embed):
        from ot_tools.mem import search

        mock_embed.return_value = [0.1] * 1536
        long_content = "a" * 500

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", long_content, "note", [], 5, 1, 0.9),
        ]

        result = search(query="test", extract=0)

        assert "a" * 500 in result
        assert "..." not in result


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

    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_updates_single_match(self, mock_conn, mock_embed):
        from ot_tools.mem import update

        mock_embed.return_value = [0.1] * 1536
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

    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_appends_content(self, mock_conn, mock_embed):
        from ot_tools.mem import append

        mock_embed.return_value = [0.1] * 1536
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
        ]
        conn.execute.return_value.fetchall.side_effect = [
            [("note", 5), ("rule", 3), ("decision", 2)],  # categories
            [("projects", 7), ("learnings", 3)],           # topics
        ]

        result = stats()

        assert "10" in result
        assert "Memory Statistics" in result

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
    """Test mem.export() format output."""

    @patch("ot_tools.mem._get_connection")
    def test_export_yaml(self, mock_conn):
        from ot_tools.mem import export

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "content one", "note", ["tag1"], 5, 2, datetime.now(), datetime.now()),
        ]

        result = export(format="yaml")

        assert "memories:" in result
        assert "topic/one" in result
        assert "content one" in result

    @patch("ot_tools.mem._get_connection")
    def test_export_markdown(self, mock_conn):
        from ot_tools.mem import export

        conn = MagicMock()
        mock_conn.return_value = conn
        conn.execute.return_value.fetchall.return_value = [
            ("id-1", "topic/one", "content one", "note", ["tag1"], 5, 2, datetime.now(), datetime.now()),
        ]

        result = export(format="markdown")

        assert "# Memory Export" in result
        assert "## topic/one" in result

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
        result = export(format="yaml", output=str(out_file))

        assert "Exported 1 memories" in result
        assert out_file.exists()

    def test_invalid_format(self):
        from ot_tools.mem import export

        result = export(format="csv")
        assert "Error" in result
        assert "Invalid format" in result

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
    @patch("ot_tools.mem._generate_embedding")
    @patch("ot_tools.mem._get_connection")
    def test_imports_from_yaml(self, mock_conn, mock_embed, tmp_path):
        from ot_tools.mem import load

        mock_embed.return_value = [0.1] * 1536
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
class TestGenerateEmbedding:
    """Test _generate_embedding function."""

    @patch("ot_tools.mem._get_openai_client")
    def test_generates_embedding(self, mock_client):
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

        result = export(format="yaml", output="/tmp/evil_export.yaml")

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
