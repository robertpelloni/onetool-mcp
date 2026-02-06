"""Integration tests for persistent memory tool pack.

Uses real DuckDB database with mocked OpenAI embeddings.
Tests full CRUD lifecycle, dedup, search, and export/import.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Skip all tests if dependencies are not available
duckdb = pytest.importorskip("duckdb")


@pytest.fixture
def mem_db(tmp_path):
    """Provide a temporary memory database with mocked config and embeddings.

    Patches config to use tmp_path database and mocks embedding generation
    to return deterministic vectors.
    """
    import ot_tools.mem as mem_module

    db_path = tmp_path / "test_mem.duckdb"

    # Close any existing connection
    mem_module._close_connection()

    mock_config = mem_module.Config(
        db_path=str(db_path),
        redaction_enabled=True,
        tags_whitelist=[],
        allowed_file_dirs=[str(tmp_path)],
    )

    # Counter for generating distinct embeddings
    call_count = [0]

    def mock_embedding(text: str) -> list[float]:
        """Generate deterministic but distinct embeddings based on call order."""
        call_count[0] += 1
        base = [0.0] * 1536
        # Set a few dimensions based on call count for differentiation
        base[0] = float(call_count[0]) / 100.0
        base[1] = float(hash(text) % 1000) / 1000.0
        return base

    with (
        patch.object(mem_module, "_get_config", return_value=mock_config),
        patch.object(mem_module, "_generate_embedding", side_effect=mock_embedding),
    ):
        yield mem_module

    # Clean up connection after test
    mem_module._close_connection()


# ---------------------------------------------------------------------------
# Core CRUD lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.tools
class TestMemCRUDLifecycle:
    """Test full create-read-update-delete lifecycle with real DuckDB."""

    def test_write_and_read(self, mem_db):
        result = mem_db.write(topic="test/lifecycle", content="hello world", category="note")
        assert "Stored memory" in result

        result = mem_db.read(topic="test/lifecycle")
        assert "hello world" in result

    def test_write_dedup(self, mem_db):
        mem_db.write(topic="test/dedup", content="same content")
        result = mem_db.write(topic="test/dedup", content="same content")
        assert "Duplicate" in result

    def test_write_different_topics_same_content(self, mem_db):
        result1 = mem_db.write(topic="topic/a", content="shared content")
        result2 = mem_db.write(topic="topic/b", content="shared content")
        assert "Stored" in result1
        assert "Stored" in result2

    def test_update_single_match(self, mem_db):
        mem_db.write(topic="test/update", content="original")
        result = mem_db.update(topic="test/update", content="updated")
        assert "Updated memory" in result

        result = mem_db.read(topic="test/update")
        assert "updated" in result

    def test_update_preserves_history(self, mem_db):
        mem_db.write(topic="test/history", content="version 1")
        mem_db.update(topic="test/history", content="version 2")

        # Verify history exists in database
        conn = mem_db._get_connection()
        history = conn.execute(
            "SELECT content FROM memory_history ORDER BY updated_at"
        ).fetchall()
        assert len(history) == 1
        assert history[0][0] == "version 1"

    def test_append(self, mem_db):
        mem_db.write(topic="test/append", content="line one")
        result = mem_db.append(topic="test/append", content="line two")
        assert "Appended" in result

        result = mem_db.read(topic="test/append")
        assert "line one" in result
        assert "line two" in result

    def test_delete_by_id(self, mem_db):
        result = mem_db.write(topic="test/delete", content="to be deleted")
        # Extract ID from result
        memory_id = result.split("Stored memory ")[1].split(" ")[0]

        result = mem_db.delete(id=memory_id)
        assert "Deleted" in result

        result = mem_db.read(topic="test/delete")
        assert "No memory found" in result

    def test_delete_by_topic_requires_confirm(self, mem_db):
        mem_db.write(topic="bulk/one", content="first")
        mem_db.write(topic="bulk/two", content="second")

        result = mem_db.delete(topic="bulk/")
        assert "confirm=True" in result

        result = mem_db.delete(topic="bulk/", confirm=True)
        assert "Deleted 2" in result

    def test_count(self, mem_db):
        mem_db.write(topic="count/a", content="first")
        mem_db.write(topic="count/b", content="second")
        mem_db.write(topic="other/c", content="third")

        assert mem_db.count() == "3"
        assert mem_db.count(topic="count/") == "2"

    def test_list_memories(self, mem_db):
        mem_db.write(topic="list/a", content="alpha", category="rule")
        mem_db.write(topic="list/b", content="beta", category="note")

        result = mem_db.list_memories()
        assert "Found 2 memories" in result

        result = mem_db.list_memories(category="rule")
        assert "Found 1 memory" in result


# ---------------------------------------------------------------------------
# Batch write
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.tools
class TestMemWriteBatch:
    """Test write_batch with real files and directory structure."""

    def test_preserves_directory_structure(self, mem_db, tmp_path):
        """write_batch should use relative path as subtopic, not just filename."""
        # Create nested directory structure
        sub = tmp_path / "commands" / "proj"
        sub.mkdir(parents=True)
        (sub / "review.md").write_text("review content")
        (sub / "stage.md").write_text("stage content")
        (tmp_path / "commands" / "top.md").write_text("top content")

        with patch("ot.paths.get_effective_cwd", return_value=tmp_path):
            result = mem_db.write_batch(
                topic="cmds",
                glob_pattern="commands/**/*.md",
                category="context",
            )

        assert "3 stored" in result

        # Verify subtopics preserve directory structure
        listing = mem_db.list_memories(topic="cmds/")
        assert "cmds/proj/review" in listing
        assert "cmds/proj/stage" in listing
        assert "cmds/top" in listing

    def test_no_files_matched(self, mem_db, tmp_path):
        with patch("ot.paths.get_effective_cwd", return_value=tmp_path):
            result = mem_db.write_batch(topic="empty", glob_pattern="*.xyz")

        assert "No files matched" in result


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.tools
class TestMemSearch:
    """Test search with real DuckDB (mocked embeddings)."""

    def test_pattern_search(self, mem_db):
        mem_db.write(topic="search/py", content="Python is great for scripting")
        mem_db.write(topic="search/js", content="JavaScript runs in browsers")

        result = mem_db.search(query="Python", mode="pattern")
        assert "Found 1 memories" in result
        assert "search/py" in result

    def test_pattern_search_topic_filter(self, mem_db):
        mem_db.write(topic="project/a", content="matching text")
        mem_db.write(topic="other/b", content="matching text")

        result = mem_db.search(query="matching", mode="pattern", topic="project/")
        assert "Found 1 memories" in result

    def test_search_no_results(self, mem_db):
        result = mem_db.search(query="nonexistent", mode="pattern")
        assert "No memories found" in result


# ---------------------------------------------------------------------------
# Phase 2 - Safety
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.tools
class TestMemSafety:
    """Test redaction and tag validation with real DuckDB."""

    def test_redacts_api_key_on_write(self, mem_db):
        mem_db.write(
            topic="secrets/test",
            content="my key is sk-abc123def456ghi789jkl0123",
        )
        result = mem_db.read(topic="secrets/test")
        assert "sk-abc123def456ghi789jkl0123" not in result
        assert "[REDACTED:api_key]" in result

    def test_context_loading(self, mem_db):
        # Write some memories with varying access counts
        mem_db.write(topic="ctx/hot", content="frequently used")
        mem_db.write(topic="ctx/cold", content="rarely used")

        # Read the first one multiple times to boost access count
        for _ in range(5):
            mem_db.read(topic="ctx/hot")

        result = mem_db.context(limit=1)
        assert "ctx/hot" in result


# ---------------------------------------------------------------------------
# Phase 3 - Lifecycle and I/O
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.tools
class TestMemLifecycle:
    """Test lifecycle features with real DuckDB."""

    def test_update_batch_dry_run(self, mem_db):
        mem_db.write(topic="batch/a", content="uses old_name here")
        mem_db.write(topic="batch/b", content="also has old_name")

        result = mem_db.update_batch(
            search_text="old_name", replace_text="new_name", dry_run=True
        )
        assert "Dry run" in result
        assert "2 memories" in result

    def test_update_batch_apply(self, mem_db):
        mem_db.write(topic="batch/apply", content="uses old_name here")

        result = mem_db.update_batch(
            search_text="old_name", replace_text="new_name", dry_run=False
        )
        assert "Updated 1 memories" in result

        result = mem_db.read(topic="batch/apply")
        assert "new_name" in result
        assert "old_name" not in result

    def test_stats(self, mem_db):
        mem_db.write(topic="stats/a", content="first memory", category="rule")
        mem_db.write(topic="stats/b", content="second memory", category="note")

        result = mem_db.stats()
        assert "Total memories: 2" in result
        assert "rule" in result
        assert "note" in result

    def test_export_yaml(self, mem_db):
        mem_db.write(topic="export/test", content="exported content")

        result = mem_db.export()
        assert "memories:" in result
        assert "export/test" in result
        assert "exported content" in result

    def test_export_to_file(self, mem_db, tmp_path):
        mem_db.write(topic="export/file", content="file content")

        out_file = tmp_path / "output.yaml"
        result = mem_db.export(output=str(out_file))
        assert "Exported 1 memories" in result
        assert out_file.exists()
        assert "file content" in out_file.read_text()

    def test_load_from_yaml(self, mem_db, tmp_path):
        # Write and export
        mem_db.write(topic="roundtrip/test", content="roundtrip content")
        out_file = tmp_path / "backup.yaml"
        mem_db.export(output=str(out_file))

        # Delete and re-import
        conn = mem_db._get_connection()
        conn.execute("DELETE FROM memories")

        assert mem_db.count() == "0"

        result = mem_db.load(file=str(out_file))
        assert "Imported 1 memories" in result
        assert mem_db.count() == "1"

    def test_export_load_roundtrip_multiline(self, mem_db, tmp_path):
        """Verify export→load roundtrip preserves multi-line content."""
        multiline = "line one\nline two\nline three"
        mem_db.write(topic="roundtrip/multi", content=multiline)

        out_file = tmp_path / "multi.yaml"
        mem_db.export(output=str(out_file))

        # Clear and re-import
        conn = mem_db._get_connection()
        conn.execute("DELETE FROM memories")
        assert mem_db.count() == "0"

        result = mem_db.load(file=str(out_file))
        assert "Imported 1 memories" in result

        content = mem_db.read(topic="roundtrip/multi")
        assert "line one" in content
        assert "line two" in content
        assert "line three" in content

    def test_decay_dry_run(self, mem_db):
        mem_db.write(topic="decay/test", content="old memory")

        result = mem_db.decay(dry_run=True)
        assert "Decay preview" in result
