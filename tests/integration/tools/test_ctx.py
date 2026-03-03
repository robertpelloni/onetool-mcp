"""Integration tests for the ot_context (ctx) pack.

Exercises real SQLite I/O — no mocked connections.
Tests the full stack: write → read/grep/list/delete/stats.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.tools
class TestCtxWriteRead:
    """Write content and read it back through real SQLite."""

    def test_write_returns_handle(self) -> None:
        """write() returns a handle immediately."""
        from otutil.tools.ctx import write

        result = write("hello world\nline two\nline three")

        assert "handle" in result
        assert len(result["handle"]) >= 8
        assert "preview" in result

    def test_write_and_read(self) -> None:
        """Content written is retrievable via read()."""
        from otutil.tools.ctx import delete, read, write

        result = write("alpha\nbeta\ngamma\ndelta")
        handle = result["handle"]
        try:
            read_result = read(handle)
            assert "lines" in read_result
            assert any("alpha" in ln for ln in read_result["lines"])
        finally:
            delete(handle)

    def test_write_and_grep(self) -> None:
        """grep() finds matching lines in written content."""
        from otutil.tools.ctx import delete, grep, write

        result = write("apple pie\nbanana split\napricot jam\ncherry tart")
        handle = result["handle"]
        try:
            grep_result = grep(handle, pattern="ap")
            assert "returned" in grep_result
            assert grep_result["returned"] >= 2
        finally:
            delete(handle)


@pytest.mark.integration
@pytest.mark.tools
class TestCtxLifecycle:
    """list, delete, stats reflect real state."""

    def test_delete_removes_handle(self) -> None:
        """delete() removes the handle from list()."""
        from otutil.tools.ctx import delete, list, write

        result = write("to be deleted")
        handle = result["handle"]
        delete(handle)
        handles = [entry["handle"] for entry in list()]
        assert handle not in handles

    def test_stats_returns_counts(self) -> None:
        """stats() reflects at least one handle after write."""
        from otutil.tools.ctx import delete, stats, write

        result = write("some content for stats")
        handle = result["handle"]
        try:
            s = stats()
            assert "total_handles" in s
            assert s["total_handles"] >= 1
        finally:
            delete(handle)
