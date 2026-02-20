"""Integration tests for persistent memory tool pack.

Uses real SQLite database with mocked OpenAI embeddings.
Tests full CRUD lifecycle, dedup, search, and export/import.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mem_db(tmp_path):
    """Provide a temporary memory database with mocked config and embeddings.

    Patches config to use tmp_path database and mocks embedding generation
    to return deterministic vectors.
    """
    import ottools.mem as mem_module

    db_path = tmp_path / "test_mem.sqlite"

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
    """Test full create-read-update-delete lifecycle with real SQLite."""

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

    def test_list(self, mem_db):
        mem_db.write(topic="list/a", content="alpha", category="rule")
        mem_db.write(topic="list/b", content="beta", category="note")

        result = mem_db.list()
        assert "Found 2 memories" in result

        result = mem_db.list(category="rule")
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

        # Verify subtopics preserve directory structure (including extension)
        listing = mem_db.list(topic="cmds/")
        assert "cmds/proj/review.md" in listing
        assert "cmds/proj/stage.md" in listing
        assert "cmds/top.md" in listing

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
    """Test search with real SQLite (mocked embeddings)."""

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
    """Test redaction and tag validation with real SQLite."""

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
    """Test lifecycle features with real SQLite."""

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


# ---------------------------------------------------------------------------
# Navigation: toc, slice, read modes
# ---------------------------------------------------------------------------

SAMPLE_NAV_MD = """\
# Introduction

Some intro text here.

## Requirements

### Requirement: Search

Search must support pattern matching.

## Configuration

Set `embeddings_enabled: true` to enable.
"""


@pytest.mark.integration
@pytest.mark.tools
class TestMemNavigation:
    """Test section navigation: write with toc, toc(), slice(), read modes."""

    def test_write_with_toc_default(self, mem_db):
        """toc=True is the default; headings are parsed without explicit arg."""
        result = mem_db.write(topic="nav/spec-default", content=SAMPLE_NAV_MD)
        assert "Stored memory" in result
        assert "toc:" in result
        assert "4 sections" in result

    def test_write_with_toc(self, mem_db):
        result = mem_db.write(topic="nav/spec", content=SAMPLE_NAV_MD, toc=True)
        assert "Stored memory" in result
        assert "toc:" in result
        assert "4 sections" in result

    def test_toc_returns_sections(self, mem_db):
        mem_db.write(topic="nav/toc", content=SAMPLE_NAV_MD, toc=True)
        result = mem_db.toc(topic="nav/toc")
        assert "Introduction" in result
        assert "Requirements" in result
        assert "Configuration" in result
        assert "4 sections" in result

    def test_toc_no_sections(self, mem_db):
        """Content with no headings produces no section index regardless of toc default."""
        mem_db.write(topic="nav/plain", content="no headings here")
        result = mem_db.toc(topic="nav/plain")
        assert "No sections found" in result

    def test_slice_by_section_number(self, mem_db):
        mem_db.write(topic="nav/slice-num", content=SAMPLE_NAV_MD, toc=True)
        result = mem_db.slice(topic="nav/slice-num", select=1)
        assert "Introduction" in result
        assert "Some intro text" in result

    def test_slice_by_heading(self, mem_db):
        mem_db.write(topic="nav/slice-head", content=SAMPLE_NAV_MD, toc=True)
        result = mem_db.slice(topic="nav/slice-head", select="Configuration")
        assert "embeddings_enabled" in result

    def test_slice_by_heading_case_insensitive(self, mem_db):
        mem_db.write(topic="nav/slice-ci", content=SAMPLE_NAV_MD, toc=True)
        result = mem_db.slice(topic="nav/slice-ci", select="configuration")
        assert "embeddings_enabled" in result

    def test_slice_by_line_range(self, mem_db):
        mem_db.write(topic="nav/slice-lr", content=SAMPLE_NAV_MD, toc=True)
        result = mem_db.slice(topic="nav/slice-lr", select=":3")
        lines = result.split("\n")
        assert len(lines) == 3

    def test_slice_mixed_list(self, mem_db):
        mem_db.write(topic="nav/slice-mix", content=SAMPLE_NAV_MD, toc=True)
        result = mem_db.slice(topic="nav/slice-mix", select=[1, "Configuration"])
        assert "Introduction" in result
        assert "embeddings_enabled" in result

    def test_read_mode_toc(self, mem_db):
        mem_db.write(topic="nav/read-toc", content=SAMPLE_NAV_MD, toc=True)
        result = mem_db.read(topic="nav/read-toc", mode="toc")
        assert "Introduction" in result
        assert "4 sections" in result

    def test_read_mode_meta(self, mem_db):
        mem_db.write(topic="nav/read-meta", content=SAMPLE_NAV_MD, category="rule")
        result = mem_db.read(topic="nav/read-meta", mode="meta")
        assert "Topic: nav/read-meta" in result
        assert "Category: rule" in result
        # meta mode should not include the content body
        assert "Some intro text" not in result

    def test_read_mode_all(self, mem_db):
        mem_db.write(topic="nav/read-all", content=SAMPLE_NAV_MD, toc=True)
        result = mem_db.read(topic="nav/read-all", mode="all")
        assert "Topic: nav/read-all" in result
        assert "Some intro text" in result

    def test_update_recomputes_toc(self, mem_db):
        mem_db.write(topic="nav/upd-toc", content=SAMPLE_NAV_MD, toc=True)
        toc_before = mem_db.toc(topic="nav/upd-toc")
        assert "4 sections" in toc_before

        new_content = "# Only One Section\n\nSimple content."
        mem_db.update(topic="nav/upd-toc", content=new_content)
        toc_after = mem_db.toc(topic="nav/upd-toc")
        assert "1 sections" in toc_after
        assert "Only One Section" in toc_after

    def test_read_batch_mode_toc(self, mem_db):
        mem_db.write(topic="nav/batch/a", content=SAMPLE_NAV_MD, toc=True)
        mem_db.write(topic="nav/batch/b", content="# Single\n\nContent.", toc=True)
        result = mem_db.read_batch(topic="nav/batch/", mode="toc")
        assert "Introduction" in result
        assert "Single" in result

    def test_write_file_with_toc(self, mem_db, tmp_path):
        """Write from file with toc=True populates source metadata and sections."""
        spec_file = tmp_path / "spec.md"
        spec_file.write_text(SAMPLE_NAV_MD)
        result = mem_db.write(topic="nav/file-toc", file=str(spec_file), toc=True)
        assert "Stored memory" in result
        assert "4 sections" in result

        # Verify meta contains source info
        meta_result = mem_db.read(topic="nav/file-toc", mode="meta")
        assert "source:" in meta_result
        assert "source_mtime:" in meta_result
        assert "content_type:" in meta_result

    def test_staleness_detection(self, mem_db, tmp_path):
        """toc() warns when source file has changed since storage."""
        spec_file = tmp_path / "stale.md"
        spec_file.write_text("# Old\n\nContent")
        mem_db.write(topic="nav/stale", file=str(spec_file), toc=True)

        # Modify the source file (ensure mtime changes)
        time.sleep(0.1)
        spec_file.write_text("# New\n\nChanged content\n\n## Extra\n\nMore.")

        result = mem_db.toc(topic="nav/stale")
        assert "modified since" in result


# ---------------------------------------------------------------------------
# Defect regression tests (D1-D7)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.tools
class TestDefectRegressions:
    """Regression tests for defects D1-D7 found via code audit."""

    def test_update_batch_recomputes_toc(self, mem_db):
        """D1: update_batch must recompute TOC sections after content changes."""
        mem_db.write(
            topic="d1/toc-batch",
            content="# Title\n\nOld text\n\n## Section\n\nBody",
            toc=True,
        )
        toc_before = mem_db.toc(topic="d1/toc-batch")
        assert "Section" in toc_before

        mem_db.update_batch(
            search_text="Old text",
            replace_text="New line 1\nNew line 2\nNew line 3",
            dry_run=False,
        )
        toc_after = mem_db.toc(topic="d1/toc-batch")
        assert "Section" in toc_after

        # Slice should return correct content after recomputation
        sliced = mem_db.slice(topic="d1/toc-batch", select=2)
        assert "Body" in sliced

    def test_export_load_preserves_meta(self, mem_db, tmp_path):
        """D2: export/load must preserve meta column (sections, source info)."""
        mem_db.write(
            topic="d2/meta-roundtrip",
            content="# Title\n\n## Section\n\nBody",
            toc=True,
        )
        meta_before = mem_db.read(topic="d2/meta-roundtrip", mode="meta")
        assert "section_count" in meta_before

        export_path = str(tmp_path / "meta-test.yaml")
        mem_db.export(output=export_path)

        mem_db.delete(topic="d2/meta-roundtrip", confirm=True)
        mem_db.load(file=export_path)

        meta_after = mem_db.read(topic="d2/meta-roundtrip", mode="meta")
        assert "section_count" in meta_after

    def test_snap_restore_preserves_meta(self, mem_db, tmp_path):
        """D3: snap/restore must preserve meta column."""
        mem_db.write(
            topic="d3/snap-meta",
            content="# Doc\n\n## Part\n\nText",
            toc=True,
        )
        meta_before = mem_db.read(topic="d3/snap-meta", mode="meta")
        assert "section_count" in meta_before

        snap_dir = str(tmp_path / "snap-meta")
        mem_db.snap(output=snap_dir, topic="d3/")

        mem_db.delete(topic="d3/snap-meta", confirm=True)
        mem_db.restore(input=snap_dir, topic="d3")

        meta_after = mem_db.read(topic="d3/snap-meta", mode="meta")
        assert "section_count" in meta_after

    def test_write_batch_populates_file_meta(self, mem_db, tmp_path):
        """D4: write_batch must populate source/source_mtime/content_type in meta."""
        doc = tmp_path / "docs" / "test.md"
        doc.parent.mkdir()
        doc.write_text("# Title\n\nContent")

        with patch("ot.paths.get_effective_cwd", return_value=tmp_path):
            mem_db.write_batch(
                topic="d4/batch-meta",
                glob_pattern="docs/*.md",
                toc=True,
            )
        result = mem_db.read(topic="d4/batch-meta/test.md", mode="meta")
        assert "source" in result
        assert "source_mtime" in result
        assert "content_type" in result

    def test_decay_never_increases_relevance(self, mem_db):
        """D5: decay must never increase relevance beyond original value."""
        mem_db.write(topic="d5/decay", content="some content", relevance=5)
        # Simulate accesses to boost access_count
        for _ in range(10):
            mem_db.read(topic="d5/decay")

        result = mem_db.decay(dry_run=True)
        # Should never show an increase
        assert "5 -> 6" not in result
        assert "5 -> 7" not in result

    def test_access_count_display_increments(self, mem_db):
        """D7: access count display must increment correctly across reads."""
        mem_db.write(topic="d7/access-display", content="hello")

        r1 = mem_db.read(topic="d7/access-display", mode="meta")
        r2 = mem_db.read(topic="d7/access-display", mode="meta")
        r3 = mem_db.read(topic="d7/access-display", mode="meta")

        assert "Accessed: 1 times" in r1
        assert "Accessed: 2 times" in r2
        assert "Accessed: 3 times" in r3


# ---------------------------------------------------------------------------
# stale / list(format="tree") / refresh integration tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.tools
class TestStaleTreeRefresh:
    """Integration tests for stale(), list(format='tree'), and refresh() with real SQLite."""

    def test_stale_detects_modified_file(self, mem_db, tmp_path):
        """Write from file, modify file, stale() reports it."""
        f = tmp_path / "doc.md"
        f.write_text("original content")
        mem_db.write(topic="stale-test/doc.md", file=str(f))

        # Modify the file (touch with new content)
        time.sleep(0.05)
        f.write_text("modified content")

        result = mem_db.stale(topic="stale-test/")
        assert "1 stale" in result
        assert "stale-test/doc.md" in result

    def test_stale_fresh_file(self, mem_db, tmp_path):
        """Write from file, don't modify, stale() reports fresh."""
        f = tmp_path / "fresh.md"
        f.write_text("content")
        mem_db.write(topic="stale-fresh/fresh.md", file=str(f))

        result = mem_db.stale(topic="stale-fresh/")
        assert "1 fresh" in result

    def test_tree_shows_hierarchy(self, mem_db):
        """Tree shows nested topic hierarchy with counts and leaf metadata."""
        mem_db.write(topic="tree-test/arch/index.md", content="arch index")
        mem_db.write(topic="tree-test/arch/core.md", content="arch core")
        mem_db.write(topic="tree-test/code/testing.md", content="code testing")

        result = mem_db.list(format="tree", topic="tree-test/")
        assert "tree-test/  (mem_count=3)" in result
        assert "── arch/  (mem_count=2)" in result
        assert "── code/  (mem_count=1)" in result
        # Leaf nodes should show metadata
        assert "── index.md  (id=" in result
        assert "category=note" in result

    def test_tree_depth_limit(self, mem_db):
        """Tree with depth=1 collapses children."""
        mem_db.write(topic="tree-depth/a/b/c", content="deep")
        mem_db.write(topic="tree-depth/a/b/d", content="deep2")

        result = mem_db.list(format="tree", topic="tree-depth/", depth=1)
        assert "── a/  (mem_count=2)" in result
        # Children should not appear
        assert "b/" not in result or "── c  (id=" not in result

    def test_refresh_round_trip(self, mem_db, tmp_path):
        """Write from file, modify file, refresh, verify content updated."""
        f = tmp_path / "refresh.md"
        f.write_text("# Original\n\nOriginal content\n")
        mem_db.write(topic="refresh-test/refresh.md", file=str(f), toc=True)

        # Verify original stored
        result = mem_db.read(topic="refresh-test/refresh.md")
        assert "Original content" in result

        # Modify file
        time.sleep(0.05)
        f.write_text("# Updated\n\nUpdated content\n")

        # Dry run first
        result = mem_db.refresh(topic="refresh-test/")
        assert "dry run" in result
        assert "1 stale" in result

        # Original content still in DB
        result = mem_db.read(topic="refresh-test/refresh.md")
        assert "Original content" in result

        # Apply refresh
        result = mem_db.refresh(topic="refresh-test/", dry_run=False)
        assert "apply" in result
        assert "1 stale" in result
        assert "updated" in result

        # Content should now be updated
        result = mem_db.read(topic="refresh-test/refresh.md")
        assert "Updated content" in result

    def test_refresh_preserves_history(self, mem_db, tmp_path):
        """Refresh creates history record of old content."""
        f = tmp_path / "hist.md"
        f.write_text("version 1")
        mem_db.write(topic="refresh-hist/hist.md", file=str(f))

        time.sleep(0.05)
        f.write_text("version 2")

        mem_db.refresh(topic="refresh-hist/", dry_run=False)

        # Check history table
        conn = mem_db._get_connection()
        history = conn.execute(
            "SELECT content FROM memory_history"
        ).fetchall()
        assert any("version 1" in h[0] for h in history)

    def test_refresh_missing_source_not_deleted(self, mem_db, tmp_path):
        """Refresh skips memories with missing source files (doesn't delete them)."""
        f = tmp_path / "temp.md"
        f.write_text("temp content")
        mem_db.write(topic="refresh-missing/temp.md", file=str(f))

        # Delete the source file
        f.unlink()

        result = mem_db.refresh(topic="refresh-missing/", dry_run=False)
        assert "1 missing" in result

        # Memory should still exist
        result = mem_db.read(topic="refresh-missing/temp.md")
        assert "temp content" in result


# ---------------------------------------------------------------------------
# slice_batch integration tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.tools
class TestSliceBatch:
    """Integration tests for mem.slice_batch() with real SQLite."""

    def test_slice_batch_round_trip(self, mem_db):
        """Write 3 memories with TOC, slice_batch all 3, verify content."""
        mem_db.write(topic="sb/a.md", content="# Intro\n\nHello world\n\n# Details\n\nMore info", toc=True)
        mem_db.write(topic="sb/b.md", content="# Setup\n\nStep one\n\n# Run\n\nStep two", toc=True)
        mem_db.write(topic="sb/c.md", content="# Config\n\nYAML stuff\n\n# Deploy\n\nShip it", toc=True)

        result = mem_db.slice_batch(items=[
            {"topic": "sb/a.md", "select": "Intro"},
            {"topic": "sb/b.md", "select": "Run"},
            {"topic": "sb/c.md", "select": "Deploy"},
        ])

        assert "Sliced 3 memories" in result
        assert "Hello world" in result
        assert "Step two" in result
        assert "Ship it" in result
        # Sections we didn't ask for should not appear
        assert "Step one" not in result
        assert "YAML stuff" not in result

    def test_slice_batch_increments_access_count(self, mem_db):
        """Verify access_count incremented for all sliced memories."""
        mem_db.write(topic="sb-ac/a", content="# H1\n\nContent", toc=True)
        mem_db.write(topic="sb-ac/b", content="# H1\n\nContent", toc=True)

        mem_db.slice_batch(items=[
            {"topic": "sb-ac/a", "select": "H1"},
            {"topic": "sb-ac/b", "select": "H1"},
        ])

        conn = mem_db._get_connection()
        counts = conn.execute(
            "SELECT topic, access_count FROM memories WHERE topic LIKE 'sb-ac/%' ORDER BY topic"
        ).fetchall()
        assert counts[0][1] >= 1  # sb-ac/a
        assert counts[1][1] >= 1  # sb-ac/b


# ---------------------------------------------------------------------------
# Grep (regex search)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.tools
class TestMemGrep:
    """Test mem.grep() regex search across memory content."""

    def test_basic_regex(self, mem_db):
        mem_db.write(
            topic="grep/basic",
            content="line one\ndef foo(bar):\n    return bar\nline four",
            category="note",
        )
        result = mem_db.grep(pattern=r"def \w+\(")
        assert "grep/basic" in result
        assert "1 match" in result
        assert "> " in result  # match marker

    def test_fixed_strings(self, mem_db):
        mem_db.write(
            topic="grep/fixed",
            content="call foo.bar() here\nother line",
            category="note",
        )
        result = mem_db.grep(pattern="foo.bar()", fixed_strings=True)
        assert "grep/fixed" in result
        assert "1 match" in result

    def test_case_insensitive(self, mem_db):
        mem_db.write(
            topic="grep/case",
            content="Some ERROR happened\nanother line",
            category="note",
        )
        result = mem_db.grep(pattern="error", case_sensitive=False)
        assert "grep/case" in result

    def test_case_sensitive_miss(self, mem_db):
        mem_db.write(
            topic="grep/case-miss",
            content="Some ERROR happened",
            category="note",
        )
        result = mem_db.grep(pattern="error", case_sensitive=True)
        assert "No matches" in result

    def test_context_lines(self, mem_db):
        lines = "\n".join(f"line {i}" for i in range(10))
        mem_db.write(topic="grep/ctx", content=lines, category="note")
        result = mem_db.grep(pattern="line 5", context=1)
        assert "line 4" in result
        assert "line 6" in result

    def test_context_merge(self, mem_db):
        lines = "\n".join(f"line {i}" for i in range(10))
        mem_db.write(topic="grep/merge", content=lines, category="note")
        # Matches on line 3 and line 5 with context=2 should merge
        result = mem_db.grep(pattern="line [35]", context=2)
        assert "grep/merge" in result
        # Should be one contiguous block (no "..." separator between them)
        blocks = result.split("  ...")
        # Both matches should be in the same block since they overlap
        assert "line 3" in result
        assert "line 5" in result

    def test_topic_filter(self, mem_db):
        mem_db.write(topic="grep/docs/a", content="auth token", category="note")
        mem_db.write(topic="grep/other/b", content="auth token", category="note")
        result = mem_db.grep(pattern="auth", topic="grep/docs/")
        assert "grep/docs/a" in result
        assert "grep/other/b" not in result

    def test_category_filter(self, mem_db):
        mem_db.write(topic="grep/cat/a", content="config value", category="rule")
        mem_db.write(topic="grep/cat/b", content="config value", category="note")
        result = mem_db.grep(pattern="config", category="rule")
        assert "grep/cat/a" in result
        assert "grep/cat/b" not in result

    def test_tag_filter(self, mem_db):
        mem_db.write(
            topic="grep/tag/a", content="tagged content", category="note", tags=["python"]
        )
        mem_db.write(
            topic="grep/tag/b", content="tagged content", category="note", tags=["rust"]
        )
        result = mem_db.grep(pattern="tagged", tags=["python"])
        assert "grep/tag/a" in result
        assert "grep/tag/b" not in result

    def test_no_matches(self, mem_db):
        mem_db.write(topic="grep/empty", content="nothing here", category="note")
        result = mem_db.grep(pattern="zzzznotfound")
        assert "No matches" in result

    def test_invalid_regex(self, mem_db):
        result = mem_db.grep(pattern="[invalid")
        assert "Error" in result
        assert "regex" in result.lower()

    def test_line_numbers_in_output(self, mem_db):
        mem_db.write(
            topic="grep/nums",
            content="aaa\nbbb\nccc\nddd",
            category="note",
        )
        result = mem_db.grep(pattern="ccc", context=0)
        assert "3" in result  # line number for "ccc"

    def test_slice_hint_in_output(self, mem_db):
        mem_db.write(
            topic="grep/slice",
            content="aaa\nbbb\nccc",
            category="note",
        )
        result = mem_db.grep(pattern="bbb", context=0)
        assert "[slice:" in result

    def test_limit(self, mem_db):
        for i in range(5):
            mem_db.write(
                topic=f"grep/lim/{i}", content=f"common word {i}", category="note"
            )
        result = mem_db.grep(pattern="common", limit=2)
        # Should only search 2 memories
        count = result.count("grep/lim/")
        assert count <= 2

    def test_max_per_memory(self, mem_db):
        # Create content with widely spaced matches so they form separate groups
        lines = []
        for i in range(50):
            if i % 10 == 0:
                lines.append(f"MATCH {i}")
            else:
                lines.append(f"filler line {i}")
        mem_db.write(topic="grep/maxpm", content="\n".join(lines), category="note")
        result = mem_db.grep(pattern="MATCH", context=0, max_per_memory=2)
        # Should only have 2 match groups (blocks separated by ...)
        match_lines = [l for l in result.split("\n") if l.startswith(">")]
        assert len(match_lines) == 2
