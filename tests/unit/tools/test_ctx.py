"""Unit tests for the ctx pack.

Covers: db layer, chunking, indexing, write/append, read/toc, search/grep/slice,
ask, management, and maintenance tools.
"""
from __future__ import annotations

import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from ot.ctx.chunking import Chunk, _chunk_markdown, _chunk_plain, chunk_content
from ot.ctx.db import (
    _ensure_schema,
    _migration_guard,
    _open_connection,
    delete_fts_for_handle,
    expires_at,
    get_content,
    is_expired,
    now_ts,
    ttl_remaining,
)
from ot.ctx.indexing import (
    _extract_vocabulary,
    build_index,
    build_snippet,
    positions_from_highlight,
    _STX,
    _ETX,
)
from ot.ctx.maintenance import (
    ctx_delete,
    ctx_purge,
)
from ot.utils.duration import parse_duration
from ot.ctx.management import ctx_inspect, ctx_list, ctx_stats
from ot.ctx.read import ctx_read, ctx_toc
from ot.ctx.search import (
    _edit_distance,
    _escape_fts5,
    ctx_grep,
    ctx_search,
    ctx_slice,
)
from ot.ctx.ask import ctx_ask
from ot.ctx.write import ctx_append, ctx_write


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conn() -> sqlite3.Connection:
    """Create an in-memory SQLite connection with full ctx schema."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    _ensure_schema(conn)
    return conn


def _insert_handle(
    conn: sqlite3.Connection,
    handle: str = "abcd1234",
    content: str = "line one\nline two\nline three",
    source: str = "test",
    status: str = "ready",
    ttl: int = 3600,
    is_file: int = 0,
) -> None:
    """Insert a test handle into the db."""
    created = now_ts()
    exp = created + ttl if ttl > 0 else None
    size = len(content.encode())
    lines = len(content.splitlines())
    conn.execute(
        "INSERT INTO results(handle, source, size_bytes, total_lines, status, created_at, expires_at, is_file, meta)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, '{}')",
        (handle, source, size, lines, status, created, exp, is_file),
    )
    conn.execute("INSERT INTO content(handle, body) VALUES (?, ?)", (handle, content))
    conn.commit()


def _build_index_for_handle(conn: sqlite3.Connection, handle: str, content: str) -> None:
    """Run build_index synchronously for a test handle."""
    build_index(handle, content, conn)


# ===========================================================================
# 1. Database Layer
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestDbSchema:
    def test_schema_creation(self) -> None:
        conn = _make_conn()
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        vtables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='shadow' OR type='table'").fetchall()}
        all_names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master").fetchall()}
        assert "results" in all_names
        assert "content" in all_names
        assert "vocabulary" in all_names
        assert "chunk_embeddings" in all_names
        assert "chunks" in all_names
        assert "chunks_trigram" in all_names

    def test_fk_cascade_delete(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "hello world")
        # Add vocab entry
        conn.execute("INSERT INTO vocabulary(handle, term, score) VALUES ('h1', 'hello', 1.0)")
        conn.commit()

        # Delete results row — should cascade to content, vocabulary
        conn.execute("DELETE FROM results WHERE handle='h1'")
        conn.commit()

        assert conn.execute("SELECT COUNT(*) FROM content WHERE handle='h1'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM vocabulary WHERE handle='h1'").fetchone()[0] == 0

    def test_ttl_expiry_query(self) -> None:
        conn = _make_conn()
        past = now_ts() - 100
        conn.execute(
            "INSERT INTO results(handle, source, size_bytes, total_lines, status, created_at, expires_at)"
            " VALUES ('expired', '', 0, 0, 'ready', ?, ?)",
            (past - 3600, past),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM results WHERE handle='expired'").fetchone()
        assert is_expired(row)

    def test_migration_guard_marks_indexing_as_failed(self) -> None:
        conn = _make_conn()
        conn.execute(
            "INSERT INTO results(handle, source, size_bytes, total_lines, status, created_at)"
            " VALUES ('stuck', '', 0, 0, 'indexing', ?)",
            (now_ts(),),
        )
        conn.commit()
        _migration_guard(conn)
        row = conn.execute("SELECT status FROM results WHERE handle='stuck'").fetchone()
        assert row["status"] == "failed"

    def test_ttl_remaining(self) -> None:
        row = {"expires_at": now_ts() + 100}
        remaining = ttl_remaining(row)
        assert 99 < remaining <= 100

    def test_no_expiry_when_expires_at_none(self) -> None:
        row = {"expires_at": None}
        assert not is_expired(row)
        assert ttl_remaining(row) == 0.0

    def test_get_content_returns_none_on_unicode_decode_error(self) -> None:
        """get_content returns None if file-backed body contains invalid UTF-8."""
        import tempfile
        from ot.ctx.db import get_content

        conn = _make_conn()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"\xff\xfe invalid utf-8")
            bad_path = f.name

        conn.execute(
            "INSERT INTO results(handle, source, size_bytes, total_lines, status, created_at, is_file)"
            " VALUES ('bad1', '', 5, 1, 'ready', ?, 1)",
            (now_ts(),),
        )
        conn.execute("INSERT INTO content(handle, body) VALUES ('bad1', ?)", (bad_path,))
        conn.commit()

        result = get_content(conn, "bad1")
        assert result is None


# ===========================================================================
# 2. Chunking
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestChunking:
    def test_markdown_single_heading(self) -> None:
        content = "# Hello\n\nsome text here\n"
        chunks = _chunk_markdown(content.splitlines())
        assert len(chunks) >= 1
        assert any("Hello" in c.title for c in chunks)

    def test_markdown_nested_headings_breadcrumb(self) -> None:
        content = "# Top\n\n## Sub\n\ntext\n"
        chunks = _chunk_markdown(content.splitlines())
        sub_chunks = [c for c in chunks if "Sub" in c.title]
        assert sub_chunks
        assert "Top" in sub_chunks[0].title
        assert "Sub" in sub_chunks[0].title

    def test_markdown_code_fence_intact(self) -> None:
        content = "# Section\n\n```python\ndef foo():\n    pass\n```\n\nmore text\n"
        chunks = _chunk_markdown(content.splitlines())
        # The code fence content should not be split into a separate chunk
        full_body = " ".join(c.body for c in chunks)
        assert "def foo()" in full_body

    def test_markdown_horizontal_rule_flush(self) -> None:
        content = "first part\n\n---\n\nsecond part\n"
        chunks = _chunk_markdown(content.splitlines())
        assert len(chunks) >= 2

    def test_plain_blank_line_split(self) -> None:
        content = "para one line a\npara one line b\n\npara two line a\npara two line b\n"
        chunks = _chunk_plain(content.splitlines())
        assert len(chunks) == 2

    def test_plain_fixed_size_fallback(self) -> None:
        # 50 lines with no blank lines — should be split into 20-line groups
        lines = [f"line {i}" for i in range(50)]
        content = "\n".join(lines)
        chunks = _chunk_plain(content.splitlines())
        assert len(chunks) >= 3
        for c in chunks:
            assert len(c.body.splitlines()) <= 20

    def test_chunk_content_selects_markdown(self) -> None:
        content = "# Title\n\nsome content\n"
        chunks = chunk_content(content)
        assert any("Title" in c.title for c in chunks)

    def test_chunk_content_selects_plain(self) -> None:
        content = "just plain text\nno headings here\n"
        chunks = chunk_content(content)
        assert len(chunks) >= 1


# ===========================================================================
# 3. Indexing
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestIndexing:
    def test_fts5_insertion(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "# Intro\n\nHello world authentication\n", status="pending")
        build_index("h1", "# Intro\n\nHello world authentication\n", conn)
        count = conn.execute("SELECT COUNT(*) FROM chunks WHERE handle='h1'").fetchone()[0]
        assert count >= 1

    def test_vocabulary_scoring(self) -> None:
        terms = _extract_vocabulary("authentication middleware kubernetes deployment containerization")
        term_names = [t for t, _ in terms]
        # Long / identifier-like terms should score well
        assert any(len(t) >= 8 for t in term_names)

    def test_vocabulary_filters_stopwords(self) -> None:
        terms = _extract_vocabulary("the and is a to of for")
        assert terms == []

    def test_snippet_extraction_positions(self) -> None:
        highlighted = f"Before {_STX}match{_ETX} after"
        positions = positions_from_highlight(highlighted)
        assert len(positions) == 1

    def test_snippet_windows_merged(self) -> None:
        # Two close positions — windows should merge
        text = "a" * 100 + "match1" + "b" * 50 + "match2" + "c" * 100
        snippet = build_snippet(text, [100, 156], window=50)
        assert "match1" in snippet or "match2" in snippet

    def test_snippet_word_boundary_start(self) -> None:
        # start is mid-word — snippet should begin at the next whole word
        text = "first second third fourth fifth sixth seventh"
        # Position 10 is mid-word ("second" starts at 6, ends at 12)
        snippet = build_snippet(text, [10], window=5)
        # The snippet should not start with a partial word
        # After snapping, start advances past "second" to "third"
        assert not snippet.startswith("econd") and not snippet.startswith("cond")

    def test_snippet_word_boundary_end(self) -> None:
        # end is mid-word — snippet should not end with a partial word
        text = "alpha beta gamma delta epsilon zeta"
        # Position near the end of "gamma" (index ~16), window clips into "delta"
        snippet = build_snippet(text, [16], window=5)
        # Should not end with a partial word fragment
        words = snippet.split()
        assert all(w in text.split() for w in words if w != "…")

    def test_embedding_skipped_when_not_configured(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "test content", status="pending")
        # No embedding_model → no embeddings stored
        build_index("h1", "test content", conn, embedding_model="")
        count = conn.execute("SELECT COUNT(*) FROM chunk_embeddings WHERE handle='h1'").fetchone()[0]
        assert count == 0

    def test_build_index_sets_ready(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "# Hello\n\nworld\n", status="pending")
        build_index("h1", "# Hello\n\nworld\n", conn)
        row = conn.execute("SELECT status FROM results WHERE handle='h1'").fetchone()
        assert row["status"] == "ready"


# ===========================================================================
# 4. Write and Append
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestWrite:
    def test_write_returns_quickly(self) -> None:
        conn = _make_conn()
        with patch("ot.ctx.write.get_db_path") as mock_path, \
             patch("ot.ctx.write.threading.Thread") as mock_thread, \
             patch("ot.ctx.write._generate_abstract", return_value="fast abstract"):
            mock_path.return_value = Path("/tmp/results.db")
            mock_thread.return_value = MagicMock()
            from ot.ctx.config import Config
            start = time.time()
            result = ctx_write("some content", db=conn, config=Config())
            elapsed = time.time() - start
        assert elapsed < 0.1
        assert "handle" in result

    def test_write_status_is_pending(self) -> None:
        conn = _make_conn()
        with patch("ot.ctx.write.get_db_path") as mock_path, \
             patch("ot.ctx.write.threading.Thread") as mock_thread:
            mock_path.return_value = Path("/tmp/results.db")
            mock_thread.return_value = MagicMock()
            from ot.ctx.config import Config
            result = ctx_write("hello", db=conn, config=Config())
        assert result["status"] == "pending"
        row = conn.execute(
            "SELECT status FROM results WHERE handle=?", (result["handle"],)
        ).fetchone()
        assert row["status"] == "pending"

    def test_write_spawns_indexing_thread(self) -> None:
        conn = _make_conn()
        with patch("ot.ctx.write.get_db_path") as mock_path, \
             patch("ot.ctx.write.threading.Thread") as mock_thread:
            mock_path.return_value = Path("/tmp/results.db")
            spawned = MagicMock()
            mock_thread.return_value = spawned
            from ot.ctx.config import Config
            ctx_write("hello", db=conn, config=Config())
        mock_thread.assert_called_once()
        spawned.start.assert_called_once()

    def test_write_file_pointer_threshold(self) -> None:
        conn = _make_conn()
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "results.db"
            with patch("ot.ctx.write.get_db_path") as mock_path, \
                 patch("ot.ctx.write.threading.Thread") as mock_thread:
                mock_path.return_value = db_path
                mock_thread.return_value = MagicMock()
                from ot.ctx.config import Config
                cfg = Config(max_inline_bytes=10)
                result = ctx_write("a" * 100, db=conn, config=cfg)

        handle = result["handle"]
        meta = conn.execute("SELECT is_file FROM results WHERE handle=?", (handle,)).fetchone()
        assert meta["is_file"] == 1

    def test_write_preview_lines(self) -> None:
        conn = _make_conn()
        with patch("ot.ctx.write.get_db_path") as mock_path, \
             patch("ot.ctx.write.threading.Thread") as mock_thread:
            mock_path.return_value = Path("/tmp/results.db")
            mock_thread.return_value = MagicMock()
            from ot.ctx.config import Config
            content = "\n".join(f"line {i}" for i in range(20))
            result = ctx_write(content, verbose=True, db=conn, config=Config())
        assert len(result["preview"]) <= 5

    def test_write_verbose_false_omits_preview_and_usage(self) -> None:
        conn = _make_conn()
        with patch("ot.ctx.write.get_db_path") as mock_path, \
             patch("ot.ctx.write.threading.Thread") as mock_thread:
            mock_path.return_value = Path("/tmp/results.db")
            mock_thread.return_value = MagicMock()
            from ot.ctx.config import Config
            result = ctx_write("some content", db=conn, config=Config())
        assert "preview" not in result
        assert "usage" not in result

    def test_write_verbose_true_includes_preview(self) -> None:
        conn = _make_conn()
        with patch("ot.ctx.write.get_db_path") as mock_path, \
             patch("ot.ctx.write.threading.Thread") as mock_thread:
            mock_path.return_value = Path("/tmp/results.db")
            mock_thread.return_value = MagicMock()
            from ot.ctx.config import Config
            result = ctx_write("line one\nline two", verbose=True, db=conn, config=Config())
        assert "preview" in result
        assert "usage" not in result

    def test_write_content_type_markdown(self) -> None:
        conn = _make_conn()
        with patch("ot.ctx.write.get_db_path") as mock_path, \
             patch("ot.ctx.write.threading.Thread") as mock_thread:
            mock_path.return_value = Path("/tmp/results.db")
            mock_thread.return_value = MagicMock()
            from ot.ctx.config import Config
            content = "# Heading\n\nSome text under heading.\n\n## Sub\n\nMore."
            result = ctx_write(content, db=conn, config=Config())
        assert result["content_type"] == "markdown"

    def test_write_content_type_text(self) -> None:
        conn = _make_conn()
        with patch("ot.ctx.write.get_db_path") as mock_path, \
             patch("ot.ctx.write.threading.Thread") as mock_thread:
            mock_path.return_value = Path("/tmp/results.db")
            mock_thread.return_value = MagicMock()
            from ot.ctx.config import Config
            content = "line 1\nline 2\nline 3\nno headings here"
            result = ctx_write(content, db=conn, config=Config())
        assert result["content_type"] == "text"

    def test_write_with_intent_ot_llm_not_installed(self) -> None:
        conn = _make_conn()
        with patch("ot.ctx.write.get_db_path") as mock_path, \
             patch("ot.ctx.write.threading.Thread") as mock_thread, \
             patch("ot.ctx.write._run_intent") as mock_intent:
            mock_path.return_value = Path("/tmp/results.db")
            mock_thread.return_value = MagicMock()
            mock_intent.return_value = {"answer_error": "ot_llm not installed"}
            from ot.ctx.config import Config
            result = ctx_write("content", intent="summarize", db=conn, config=Config())
        assert "answer_error" in result

    def test_generate_abstract_uses_llm(self) -> None:
        from ot.ctx.write import _generate_abstract
        import sys
        fake_llm = MagicMock()
        fake_llm.transform.return_value = "A clear LLM-generated abstract."
        with patch.dict(sys.modules, {"ottools.ot_llm": fake_llm}):
            result = _generate_abstract("Some content about FastAPI routing.")
        assert result == "A clear LLM-generated abstract."

    def test_generate_abstract_fallback_first_500_chars(self) -> None:
        from ot.ctx.write import _generate_abstract
        import sys
        # Ensure ot_llm is not available
        with patch.dict(sys.modules, {"ottools.ot_llm": None}):
            short = _generate_abstract("Hello world")
        assert short == "Hello world"

    def test_generate_abstract_fallback_truncates_at_500(self) -> None:
        from ot.ctx.write import _generate_abstract
        long_content = "word " * 200  # 1000 chars
        with patch.dict({"ottools.ot_llm": None}, {}):
            with patch("ot.ctx.write._generate_abstract", wraps=lambda c: c[:500].strip() + "…"):
                result = _generate_abstract(long_content)
        # Should end with ellipsis and be under 502 chars
        assert len(result) <= 502

    def test_write_abstract_is_empty_immediately(self) -> None:
        conn = _make_conn()
        with patch("ot.ctx.write.get_db_path") as mock_path, \
             patch("ot.ctx.write.threading.Thread") as mock_thread:
            mock_path.return_value = Path("/tmp/results.db")
            mock_thread.return_value = MagicMock()
            from ot.ctx.config import Config
            result = ctx_write("some content", db=conn, config=Config())
        assert result["abstract"] == ""

    def test_append_rebuilds_index(self) -> None:
        conn = _make_conn()
        with patch("ot.ctx.write.get_db_path") as mock_path, \
             patch("ot.ctx.write.threading.Thread") as mock_thread:
            mock_path.return_value = Path("/tmp/results.db")
            mock_t = MagicMock()
            mock_thread.return_value = mock_t
            from ot.ctx.config import Config
            result = ctx_write("original content", db=conn, config=Config())
            handle = result["handle"]
            append_result = ctx_append(handle, " extra", db=conn, config=Config())
        assert append_result["status"] == "pending"
        assert append_result["abstract"] == ""
        # 1 indexing thread per write + 1 per append = 2 total
        assert mock_t.start.call_count == 2

    def test_append_unknown_handle(self) -> None:
        conn = _make_conn()
        from ot.ctx.config import Config
        result = ctx_append("nosuchhandle", "extra", db=conn, config=Config())
        assert "error" in result

    def test_write_accepts_handle_dict_and_dereferences(self) -> None:
        """ctx_write dereferences a runner auto-offload handle dict transparently."""
        conn = _make_conn()
        _insert_handle(conn, "src1", "deref content here", status="ready")
        with patch("ot.ctx.write.get_db_path") as mock_path, \
             patch("ot.ctx.write.threading.Thread") as mock_thread:
            mock_path.return_value = Path("/tmp/results.db")
            mock_thread.return_value = MagicMock()
            from ot.ctx.config import Config
            result = ctx_write(
                {"handle": "src1", "total_lines": 1},
                source="test",
                db=conn,
                config=Config(),
            )
        assert "handle" in result
        assert result["handle"] != "src1"  # new handle allocated

    def test_write_handle_dict_unknown_returns_error(self) -> None:
        conn = _make_conn()
        from ot.ctx.config import Config
        result = ctx_write({"handle": "nosuch"}, db=conn, config=Config())
        assert "error" in result


# ===========================================================================
# 5. Read and TOC
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestRead:
    def test_pagination_defaults(self) -> None:
        conn = _make_conn()
        content = "\n".join(f"line {i}" for i in range(200))
        _insert_handle(conn, "h1", content)
        result = ctx_read("h1", db=conn)
        assert result["returned"] == 100
        assert result["offset"] == 1
        assert result["has_more"] is True

    def test_pagination_with_offset(self) -> None:
        conn = _make_conn()
        content = "\n".join(f"line {i}" for i in range(200))
        _insert_handle(conn, "h1", content)
        result = ctx_read("h1", offset=101, limit=50, db=conn)
        assert result["offset"] == 101
        assert result["returned"] == 50

    def test_tail(self) -> None:
        conn = _make_conn()
        content = "\n".join(str(i) for i in range(100))
        _insert_handle(conn, "h1", content)
        result = ctx_read("h1", tail=20, db=conn)
        assert result["returned"] == 20
        assert result["lines"][-1] == "99"

    def test_tail_larger_than_total(self) -> None:
        conn = _make_conn()
        content = "a\nb\nc"
        _insert_handle(conn, "h1", content)
        result = ctx_read("h1", tail=100, db=conn)
        assert result["returned"] == 3

    def test_invalid_offset(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "content")
        result = ctx_read("h1", offset=0, db=conn)
        assert "error" in result
        assert "offset must be >= 1" in result["error"]

    def test_invalid_limit(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "content")
        result = ctx_read("h1", limit=0, db=conn)
        assert "error" in result
        assert "limit must be >= 1" in result["error"]

    def test_mode_toc(self) -> None:
        conn = _make_conn()
        content = "# Intro\n\ntext\n\n## Sub\n\nmore\n"
        _insert_handle(conn, "h1", content, status="indexing")
        result = ctx_read("h1", mode="toc", db=conn)
        assert "sections" in result

    def test_mode_meta(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "hello world", source="testpack")
        result = ctx_read("h1", mode="meta", db=conn)
        assert result["source"] == "testpack"
        assert "status" in result
        assert isinstance(result["ttl_remaining"], int)

    def test_mode_invalid(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "hello world")
        result = ctx_read("h1", mode="invalid", db=conn)
        assert "error" in result
        assert "invalid" in result["error"].lower()

    def test_empty_content_progress(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "")
        result = ctx_read("h1", db=conn)
        assert result["total_lines"] == 0
        assert result["progress"] == "empty (0 lines)"

    def test_expired_handle(self) -> None:
        conn = _make_conn()
        past = now_ts() - 100
        conn.execute(
            "INSERT INTO results(handle, source, size_bytes, total_lines, status, created_at, expires_at)"
            " VALUES ('exp', '', 5, 1, 'ready', ?, ?)",
            (past - 3700, past),
        )
        conn.execute("INSERT INTO content(handle, body) VALUES ('exp', 'hello')")
        conn.commit()
        result = ctx_read("exp", db=conn)
        assert "error" in result
        assert "expired" in result["error"].lower()

    def test_unknown_handle(self) -> None:
        conn = _make_conn()
        result = ctx_read("unknown", db=conn)
        assert "error" in result

    def test_toc_from_chunks(self) -> None:
        conn = _make_conn()
        content = "# Section A\n\nsome text\n\n# Section B\n\nmore text\n"
        _insert_handle(conn, "h1", content, status="pending")
        build_index("h1", content, conn)
        result = ctx_toc("h1", db=conn)
        assert "sections" in result
        assert result["total_sections"] >= 1


# ===========================================================================
# 6. Search, Grep, Slice
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestSearch:
    def _ready_handle(self, conn: sqlite3.Connection, handle: str, content: str) -> None:
        _insert_handle(conn, handle, content, status="pending")
        build_index(handle, content, conn)
        # build_index sets status='ready'; ctx_search skips the event wait for ready handles

    def test_porter_match(self) -> None:
        conn = _make_conn()
        content = "# Auth\n\nAuthentication requires a valid token\n"
        self._ready_handle(conn, "h1", content)
        result = ctx_search("h1", queries=["authenticate"], db=conn)
        assert "h1" in result.get("handle", "h1")
        assert result["results"]["authenticate"]["matchLayer"] == "porter"

    def test_no_results_includes_vocabulary(self) -> None:
        conn = _make_conn()
        content = "# Deploy\n\nKubernetes deployment configuration\n"
        self._ready_handle(conn, "h1", content)
        result = ctx_search("h1", queries=["zxqvbfoo"], db=conn)
        assert "vocabulary" in result["results"]["zxqvbfoo"]
        assert result["results"]["zxqvbfoo"]["sections"] == []

    def test_search_score_is_positive(self) -> None:
        conn = _make_conn()
        content = "# Auth\n\nAuthentication requires a valid token\n"
        self._ready_handle(conn, "h1", content)
        result = ctx_search("h1", queries=["authentication"], db=conn)
        sections = result["results"]["authentication"]["sections"]
        assert sections, "Expected at least one result"
        assert sections[0]["score"] > 0, "Score should be positive (negated BM25)"

    def test_search_on_failed_handle(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "content", status="failed")
        result = ctx_search("h1", queries=["foo"], db=conn)
        assert "error" in result

    def test_grep_basic(self) -> None:
        conn = _make_conn()
        content = "apple pie\nbanana split\napricot jam\n"
        _insert_handle(conn, "h1", content)
        result = ctx_grep("h1", pattern="ap", db=conn)
        assert result["returned"] == 2

    def test_grep_with_context(self) -> None:
        conn = _make_conn()
        content = "\n".join(["before", "before2", "TARGET", "after", "after2"])
        _insert_handle(conn, "h1", content)
        result = ctx_grep("h1", pattern="TARGET", context=1, db=conn)
        assert "---" not in result["lines"] or len(result["lines"]) > 1
        assert any("TARGET" in ln for ln in result["lines"])

    def test_grep_fuzzy(self) -> None:
        conn = _make_conn()
        content = "configuration settings\ndeployment manifest\nservice definition\n"
        _insert_handle(conn, "h1", content)
        result = ctx_grep("h1", pattern="config", fuzzy=True, db=conn)
        assert result["returned"] >= 1

    def test_grep_empty_pattern(self) -> None:
        conn = _make_conn()
        content = "line one\nline two\nline three\n"
        _insert_handle(conn, "h1", content)
        result = ctx_grep("h1", pattern="", db=conn)
        assert "error" in result
        assert "empty" in result["error"].lower()

    def test_grep_unknown_handle(self) -> None:
        conn = _make_conn()
        result = ctx_grep("nosuch", pattern="x", db=conn)
        assert "error" in result

    def test_slice_by_line_range(self) -> None:
        conn = _make_conn()
        content = "\n".join(f"line {i}" for i in range(1, 21))
        _insert_handle(conn, "h1", content)
        result = ctx_slice("h1", select="5:10", db=conn)
        assert "lines" in result
        assert len(result["lines"]) == 6

    def test_slice_by_section_number(self) -> None:
        conn = _make_conn()
        content = "# A\n\ntextA\n\n# B\n\ntextB\n"
        _insert_handle(conn, "h1", content, status="pending")
        build_index("h1", content, conn)
        result = ctx_slice("h1", select=1, db=conn)
        assert "lines" in result

    def test_slice_by_heading(self) -> None:
        conn = _make_conn()
        content = "# Installation\n\nRun npm install\n\n# Usage\n\nRun npm start\n"
        _insert_handle(conn, "h1", content, status="pending")
        build_index("h1", content, conn)
        result = ctx_slice("h1", select="Installation", db=conn)
        assert "lines" in result
        assert "error" not in result

    def test_slice_section_not_found(self) -> None:
        conn = _make_conn()
        content = "# Known\n\ntext\n"
        _insert_handle(conn, "h1", content, status="pending")
        build_index("h1", content, conn)
        result = ctx_slice("h1", select="NonExistentXYZ", db=conn)
        assert "error" in result

    def test_edit_distance(self) -> None:
        assert _edit_distance("kitten", "sitting") == 3
        assert _edit_distance("", "abc") == 3
        assert _edit_distance("abc", "abc") == 0

    def test_escape_fts5_simple_token(self) -> None:
        assert _escape_fts5("hello") == "hello"

    def test_escape_fts5_multi_word_strips_stopwords(self) -> None:
        """Multi-word natural language queries use implicit AND (space-separated tokens)."""
        # Both tokens are significant — neither is a stopword
        assert _escape_fts5("hello world") == "hello world"
        # Stopwords stripped, only significant term remains
        assert _escape_fts5("how to install") == "install"
        # Mixed: only significant terms kept
        assert _escape_fts5("the installation guide") == "installation guide"

    def test_escape_fts5_boolean_operators_pass_through(self) -> None:
        assert _escape_fts5("install AND config") == "install AND config"
        assert _escape_fts5("NOT install") == "NOT install"
        assert _escape_fts5("install OR deploy") == "install OR deploy"


# ===========================================================================
# 7. Ask
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestAsk:
    def test_single_question_returns_result_list(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "asyncio is great for IO-bound tasks")
        mock_llm = MagicMock()
        mock_llm.transform = MagicMock(return_value="asyncio is great for IO-bound work")
        with patch.dict("sys.modules", {"ottools.ot_llm": mock_llm}):
            result = ctx_ask("h1", q="What is asyncio good for?", db=conn)
        assert "result" in result
        assert result["handle"] == "h1"
        assert len(result["result"]) == 1
        assert result["result"][0]["question"] == "What is asyncio good for?"
        assert result["result"][0]["answer"] == "asyncio is great for IO-bound work"

    def test_batch_questions_single_llm_call(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "Python asyncio content")
        mock_llm = MagicMock()
        mock_llm.transform = MagicMock(return_value="1. Use gather\n2. Avoid blocking")
        with patch.dict("sys.modules", {"ottools.ot_llm": mock_llm}):
            result = ctx_ask("h1", q=["Best practice?", "Common mistake?"], db=conn)
        assert mock_llm.transform.call_count == 1
        assert len(result["result"]) == 2
        assert result["result"][0]["question"] == "Best practice?"
        assert result["result"][1]["question"] == "Common mistake?"

    def test_model_override_passed_to_llm(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "content")
        mock_llm = MagicMock()
        mock_llm.transform = MagicMock(return_value="answer")
        with patch.dict("sys.modules", {"ottools.ot_llm": mock_llm}):
            ctx_ask("h1", q="What?", model="haiku", db=conn)
        mock_llm.transform.assert_called_once()
        _, kwargs = mock_llm.transform.call_args
        assert kwargs.get("model") == "haiku"

    def test_ot_llm_not_configured_returns_error_dict(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "content")
        with patch.dict("sys.modules", {"ottools.ot_llm": None}):
            result = ctx_ask("h1", q="What?", db=conn)
        assert "error" in result
        assert result["handle"] == "h1"
        assert "ot_llm" in result["error"]

    def test_unknown_handle_returns_error_dict(self) -> None:
        conn = _make_conn()
        result = ctx_ask("nosuch", q="What?", db=conn)
        assert result == {"error": "Handle not found: nosuch", "handle": "nosuch"}

    def test_large_content_sets_truncated(self) -> None:
        conn = _make_conn()
        big_content = "x" * (1024 * 1024 + 1)  # just over 1MB default
        _insert_handle(conn, "h1", big_content)
        mock_llm = MagicMock()
        mock_llm.transform = MagicMock(return_value="answer")
        with patch.dict("sys.modules", {"ottools.ot_llm": mock_llm}):
            result = ctx_ask("h1", q="What?", db=conn)
        assert result.get("truncated") is True
        assert "hint" in result


# ===========================================================================
# 8. Management
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestManagement:
    def test_list_active_handles(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "content A", source="brave")
        _insert_handle(conn, "h2", "content B", source="webfetch")
        result = ctx_list(db=conn)
        assert isinstance(result, list)
        assert len(result) == 2
        # abstract is None until background worker runs
        assert result[0]["abstract"] is None
        # command shows how to read the handle
        assert result[0]["command"] == f"ctx.read('{result[0]['handle']}')"

    def test_list_includes_abstract_when_set(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h_abs", "FastAPI content", source="docs")
        conn.execute(
            "UPDATE results SET meta=json_set(meta, '$.abstract', 'FastAPI routing docs.') WHERE handle='h_abs'"
        )
        conn.commit()
        result = ctx_list(db=conn)
        assert result[0]["abstract"] == "FastAPI routing docs."

    def test_inspect_includes_abstract(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h_ins", "content", source="test")
        conn.execute(
            "UPDATE results SET meta=json_set(meta, '$.abstract', 'A test document.') WHERE handle='h_ins'"
        )
        conn.commit()
        result = ctx_inspect("h_ins", db=conn)
        assert result["abstract"] == "A test document."

    def test_list_empty(self) -> None:
        conn = _make_conn()
        result = ctx_list(db=conn)
        assert result == []

    def test_list_filter_by_source(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "A", source="brave")
        _insert_handle(conn, "h2", "B", source="webfetch")
        result = ctx_list(source="brave", db=conn)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["source"] == "brave"

    def test_list_filter_by_status(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "A", status="ready")
        _insert_handle(conn, "h2", "B", status="failed")
        result = ctx_list(status="failed", db=conn)
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["status"] == "failed"

    def test_list_invalid_status_raises(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "A", status="ready")
        with pytest.raises(ValueError, match="Invalid status 'bad_status'"):
            ctx_list(status="bad_status", db=conn)

    def test_inspect_known_handle(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "hello world", source="testpack")
        result = ctx_inspect("h1", db=conn)
        assert result["handle"] == "h1"
        assert result["source"] == "testpack"
        assert "chunk_count" in result
        assert "vocab_size" in result

    def test_inspect_unknown_handle(self) -> None:
        conn = _make_conn()
        result = ctx_inspect("nosuch", db=conn)
        assert "error" in result

    def test_stats_aggregation(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "content A", status="ready")
        _insert_handle(conn, "h2", "content B", status="failed")
        with patch("ot.ctx.management.get_db_path") as mock_path:
            p = MagicMock()
            p.exists.return_value = False
            mock_path.return_value = p
            result = ctx_stats(db=conn)
        assert result["total_handles"] == 2
        assert "ready" in result["handles_by_status"]
        assert "failed" in result["handles_by_status"]
        assert "estimated_tokens_saved" in result


# ===========================================================================
# 9. Maintenance
# ===========================================================================


@pytest.mark.unit
@pytest.mark.tools
class TestMaintenance:
    def _mock_db_path(self):
        """Return a mock db_path that reports not existing (so size=0)."""
        p = MagicMock()
        p.exists.return_value = False
        p.stat.return_value = MagicMock(st_size=0)
        return p

    def test_delete_cascades(self) -> None:
        conn = _make_conn()
        _insert_handle(conn, "h1", "content to delete")
        build_index("h1", "content to delete", conn)
        result = ctx_delete("h1", db=conn)
        assert result == {"deleted": "h1"}
        assert conn.execute("SELECT COUNT(*) FROM results WHERE handle='h1'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM content WHERE handle='h1'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM chunks WHERE handle='h1'").fetchone()[0] == 0

    def test_delete_unlinks_file(self) -> None:
        conn = _make_conn()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test content")
            fpath = f.name

        conn.execute(
            "INSERT INTO results(handle, source, size_bytes, total_lines, status, created_at, is_file)"
            " VALUES ('fh', '', 12, 1, 'ready', ?, 1)",
            (now_ts(),),
        )
        conn.execute("INSERT INTO content(handle, body) VALUES ('fh', ?)", (fpath,))
        conn.commit()

        ctx_delete("fh", db=conn)
        assert not Path(fpath).exists()

    def test_delete_unknown_handle(self) -> None:
        conn = _make_conn()
        result = ctx_delete("nosuch", db=conn)
        assert result == {"error": "Handle not found: nosuch"}

    def test_purge_by_age(self) -> None:
        conn = _make_conn()
        old = now_ts() - 7200  # 2 hours ago
        conn.execute(
            "INSERT INTO results(handle, source, size_bytes, total_lines, status, created_at)"
            " VALUES ('old', '', 0, 0, 'ready', ?)",
            (old,),
        )
        conn.execute("INSERT INTO content(handle, body) VALUES ('old', 'x')")
        conn.commit()
        result = ctx_purge(minutes=60, db=conn)
        assert result["deleted"] == 1

    def test_purge_by_source(self) -> None:
        conn = _make_conn()
        old = now_ts() - 3600  # 1 hour ago
        for h in ("h1", "h2"):
            conn.execute(
                "INSERT INTO results(handle, source, size_bytes, total_lines, status, created_at)"
                " VALUES (?, ?, 10, 1, 'ready', ?)",
                (h, "brave" if h == "h1" else "webfetch", old),
            )
            conn.execute("INSERT INTO content(handle, body) VALUES (?, 'x')", (h,))
        conn.commit()
        result = ctx_purge(source="brave", db=conn)
        assert result["deleted"] == 1
        assert conn.execute("SELECT COUNT(*) FROM results WHERE handle='h1'").fetchone()[0] == 0

    def test_purge_by_status(self) -> None:
        conn = _make_conn()
        old = now_ts() - 3600
        for h, st in (("h1", "failed"), ("h2", "ready")):
            conn.execute(
                "INSERT INTO results(handle, source, size_bytes, total_lines, status, created_at)"
                " VALUES (?, '', 10, 1, ?, ?)",
                (h, st, old),
            )
            conn.execute("INSERT INTO content(handle, body) VALUES (?, 'x')", (h,))
        conn.commit()
        result = ctx_purge(status="failed", db=conn)
        assert result["deleted"] == 1

    def test_purge_no_matches(self) -> None:
        """ctx_purge() with no old handles deletes nothing."""
        conn = _make_conn()
        # Insert fresh handles — they won't be older than 15 minutes
        _insert_handle(conn, "h1", "A", status="ready")
        result = ctx_purge(db=conn)
        assert result["deleted"] == 0

    def test_purge_skips_vacuum_when_nothing_deleted(self) -> None:
        """VACUUM is not run when no handles are deleted."""
        conn = _make_conn()
        _insert_handle(conn, "h1", "A", status="ready")

        vacuum_calls: list[str] = []

        class _TrackingConn:
            def __init__(self, real: sqlite3.Connection) -> None:
                self._real = real

            def execute(self, sql: str, *args: object, **kwargs: object):
                if sql.strip().upper() == "VACUUM":
                    vacuum_calls.append(sql)
                return self._real.execute(sql, *args, **kwargs)

            def __getattr__(self, name: str):
                return getattr(self._real, name)

        ctx_purge(db=_TrackingConn(conn))  # type: ignore[arg-type]
        assert vacuum_calls == [], "VACUUM should not run when deleted == 0"

    def test_purge_old_handles_default_minutes(self) -> None:
        """ctx_purge() with default minutes=15 deletes handles older than 15 min."""
        conn = _make_conn()
        old = now_ts() - 3700  # ~62 min ago
        conn.execute(
            "INSERT INTO results(handle, source, size_bytes, total_lines, status, created_at)"
            " VALUES ('exp', '', 100, 1, 'ready', ?)",
            (old,),
        )
        conn.execute("INSERT INTO content(handle, body) VALUES ('exp', 'x')")
        conn.commit()
        result = ctx_purge(db=conn)
        assert result["deleted"] == 1
        assert result["bytes_freed"] == 100

    def test_purge_bytes_freed_sums_size_bytes(self) -> None:
        """bytes_freed reflects content size, not filesystem diff."""
        conn = _make_conn()
        old = now_ts() - 3700
        for h, size in (("h1", 500), ("h2", 300)):
            conn.execute(
                "INSERT INTO results(handle, source, size_bytes, total_lines, status, created_at)"
                " VALUES (?, '', ?, 1, 'ready', ?)",
                (h, size, old),
            )
            conn.execute("INSERT INTO content(handle, body) VALUES (?, 'x')", (h,))
        conn.commit()
        result = ctx_purge(db=conn)
        assert result["deleted"] == 2
        assert result["bytes_freed"] == 800

    def test_purge_all_wipes_everything(self) -> None:
        """ctx_purge(delete_all=True) removes all handles and preserves schema."""
        conn = _make_conn()
        _insert_handle(conn, "h1", "A")
        _insert_handle(conn, "h2", "B")
        result = ctx_purge(delete_all=True, db=conn)
        assert result["deleted"] == 2
        assert conn.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 0
        # Schema preserved
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "results" in tables
        assert "content" in tables

    def test_purge_all_respects_source_filter(self) -> None:
        """ctx_purge(delete_all=True, source=...) deletes only matching handles."""
        conn = _make_conn()
        _insert_handle(conn, "h1", "A", source="brave")
        _insert_handle(conn, "h2", "B", source="webfetch")
        result = ctx_purge(delete_all=True, source="brave", db=conn)
        assert result["deleted"] == 1
        assert conn.execute("SELECT COUNT(*) FROM results WHERE handle='h1'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM results WHERE handle='h2'").fetchone()[0] == 1

    def test_purge_all_respects_status_filter(self) -> None:
        """ctx_purge(delete_all=True, status=...) deletes only matching handles."""
        conn = _make_conn()
        _insert_handle(conn, "h1", "A", status="failed")
        _insert_handle(conn, "h2", "B", status="ready")
        result = ctx_purge(delete_all=True, status="failed", db=conn)
        assert result["deleted"] == 1
        assert conn.execute("SELECT COUNT(*) FROM results WHERE handle='h1'").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM results WHERE handle='h2'").fetchone()[0] == 1

    def test_parse_duration(self) -> None:
        assert parse_duration("30m") == 1800.0
        assert parse_duration("2h") == 7200.0
        assert parse_duration("1d") == 86400.0
        with pytest.raises(ValueError):
            parse_duration("invalid")

    def test_purge_zero_minutes_raises(self) -> None:
        """ctx_purge(minutes=0) raises ValueError — zero is not a safe value."""
        conn = _make_conn()
        with pytest.raises(ValueError, match="positive"):
            ctx_purge(minutes=0, db=conn)

    def test_purge_negative_minutes_raises(self) -> None:
        """ctx_purge(minutes=-1) raises ValueError."""
        conn = _make_conn()
        with pytest.raises(ValueError, match="positive"):
            ctx_purge(minutes=-1, db=conn)
