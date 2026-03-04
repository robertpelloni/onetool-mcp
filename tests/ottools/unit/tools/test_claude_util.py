"""Unit tests for the claude_util pack.

Covers session_id(), start_usage(), and elapsed_usage() with mocked filesystem
and mocked ctx / ccusage subprocess calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ccusage_response(
    session_uuid: str = "test-uuid-1234",
    total_tokens: int = 1000,
    total_cost: float = 0.5,
    output_tokens: int = 200,
    cache_read: int = 300,
    cache_create: int = 100,
) -> dict:
    return {
        "sessionId": session_uuid,
        "totalTokens": total_tokens,
        "totalCost": total_cost,
        "entries": [
            {
                "outputTokens": output_tokens,
                "cacheReadTokens": cache_read,
                "cacheCreationTokens": cache_create,
            }
        ],
    }


def _make_baseline_snapshot(
    session_uuid: str = "test-uuid-1234",
    total_tokens: int = 1000,
    total_cost: float = 0.5,
    output_tokens: int = 200,
    cache_read: int = 300,
    cache_create: int = 100,
    snapshot_at: str = "2026-03-04T10:00:00+00:00",
) -> dict:
    return {
        "session_id": session_uuid,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost,
        "total_output_tokens": output_tokens,
        "total_cache_read_tokens": cache_read,
        "total_cache_create_tokens": cache_create,
        "snapshot_at": snapshot_at,
    }


# ---------------------------------------------------------------------------
# Tests: session_id()
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestSessionId:
    def test_returns_stem_of_most_recent_jsonl(self, tmp_path: Path) -> None:
        import time

        from ottools.claude_util import _project_slug, session_id

        slug = _project_slug()
        project_dir = tmp_path / slug
        project_dir.mkdir(parents=True)

        old_file = project_dir / "old-uuid.jsonl"
        new_file = project_dir / "new-uuid-abc.jsonl"
        old_file.write_text("")
        time.sleep(0.01)
        new_file.write_text("")

        with patch("ottools.claude_util._claude_projects_dir", return_value=tmp_path):
            result = session_id()

        assert result == "new-uuid-abc"

    def test_error_when_project_dir_missing(self, tmp_path: Path) -> None:
        from ottools.claude_util import session_id

        with patch("ottools.claude_util._claude_projects_dir", return_value=tmp_path):
            result = session_id()

        assert isinstance(result, str)
        assert result.startswith("Error:")
        assert "not found" in result

    def test_error_when_no_jsonl_files(self, tmp_path: Path) -> None:
        from ottools.claude_util import _project_slug, session_id

        slug = _project_slug()
        project_dir = tmp_path / slug
        project_dir.mkdir(parents=True)

        with patch("ottools.claude_util._claude_projects_dir", return_value=tmp_path):
            result = session_id()

        assert isinstance(result, str)
        assert result.startswith("Error:")
        assert "no JSONL" in result

    def test_project_slug_derivation(self) -> None:
        from ottools.claude_util import _project_slug

        slug = _project_slug(Path("/Users/gavin/projects/my-app"))
        assert slug == "-Users-gavin-projects-my-app"
        assert slug.startswith("-")


# ---------------------------------------------------------------------------
# Tests: _run_ccusage()
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestRunCcusage:
    def test_returns_parsed_json_on_success(self) -> None:
        from ottools.claude_util import _run_ccusage

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({"sessionId": "abc", "totalTokens": 500})

        with patch("subprocess.run", return_value=mock_result):
            result = _run_ccusage("abc")

        assert isinstance(result, dict)
        assert result["sessionId"] == "abc"
        assert result["totalTokens"] == 500

    def test_returns_error_string_when_ccusage_not_found(self) -> None:
        from ottools.claude_util import _run_ccusage

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = _run_ccusage("abc")

        assert isinstance(result, str)
        assert result.startswith("Error: ccusage not found")

    def test_returns_error_string_on_nonzero_exit(self) -> None:
        from ottools.claude_util import _run_ccusage

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "session not found"

        with patch("subprocess.run", return_value=mock_result):
            result = _run_ccusage("bad-uuid")

        assert isinstance(result, str)
        assert result.startswith("Error:")
        assert "1" in result


# ---------------------------------------------------------------------------
# Tests: start_usage()
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestStartUsage:
    def test_returns_confirmation_dict_on_success(self) -> None:
        from ottools.claude_util import start_usage

        ccusage_data = _make_ccusage_response()

        with (
            patch("ottools.claude_util.session_id", return_value="test-uuid-1234"),
            patch("ottools.claude_util._run_ccusage", return_value=ccusage_data),
            patch("ot.ctx.write.ctx_write", return_value={"handle": "abc12345"}) as mock_write,
        ):
            result = start_usage()

        assert isinstance(result, dict)
        assert result["session_id"] == "test-uuid-1234"
        assert "snapshot_at" in result
        assert result["total_tokens"] == 1000
        assert result["total_cost_usd"] == 0.5
        mock_write.assert_called_once()

    def test_propagates_session_id_error(self) -> None:
        from ottools.claude_util import start_usage

        with patch("ottools.claude_util.session_id", return_value="Error: no dir"):
            result = start_usage()

        assert isinstance(result, str)
        assert result == "Error: no dir"

    def test_propagates_ccusage_error(self) -> None:
        from ottools.claude_util import start_usage

        with (
            patch("ottools.claude_util.session_id", return_value="test-uuid"),
            patch("ottools.claude_util._run_ccusage", return_value="Error: ccusage not found. Install with: npm install -g ccusage"),
        ):
            result = start_usage()

        assert isinstance(result, str)
        assert result.startswith("Error:")

    def test_stores_baseline_in_ctx_with_correct_source(self) -> None:
        from ottools.claude_util import start_usage

        ccusage_data = _make_ccusage_response(
            total_tokens=500, total_cost=0.25,
            output_tokens=100, cache_read=50, cache_create=20,
        )
        stored_content: list[str] = []

        def capture_write(content: str, *, source: str = "", **kwargs: object) -> dict:
            stored_content.append(content)
            return {"handle": "snap0001"}

        with (
            patch("ottools.claude_util.session_id", return_value="test-uuid"),
            patch("ottools.claude_util._run_ccusage", return_value=ccusage_data),
            patch("ot.ctx.write.ctx_write", side_effect=capture_write),
        ):
            start_usage()

        assert stored_content
        snapshot = json.loads(stored_content[0])
        assert snapshot["total_tokens"] == 500
        assert snapshot["total_output_tokens"] == 100
        assert snapshot["total_cache_read_tokens"] == 50
        assert snapshot["total_cache_create_tokens"] == 20

    def test_named_recorder_writes_namespaced_source(self) -> None:
        from ottools.claude_util import start_usage

        ccusage_data = _make_ccusage_response()
        captured_sources: list[str] = []

        def capture_write(content: str, *, source: str = "", **kwargs: object) -> dict:
            captured_sources.append(source)
            return {"handle": "snap0001"}

        with (
            patch("ottools.claude_util.session_id", return_value="test-uuid"),
            patch("ottools.claude_util._run_ccusage", return_value=ccusage_data),
            patch("ot.ctx.write.ctx_write", side_effect=capture_write),
        ):
            start_usage(name="A-1")

        assert captured_sources == ["cld_baseline_A-1"]


# ---------------------------------------------------------------------------
# Tests: elapsed_usage()
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestElapsedUsage:
    def _make_ctx_mocks(
        self,
        baseline: dict,
        handle: str = "snap0001",
    ) -> tuple[MagicMock, MagicMock, MagicMock]:
        mock_list = MagicMock(return_value=[{"handle": handle}])
        mock_read = MagicMock(
            return_value={"lines": json.dumps(baseline).splitlines() or [json.dumps(baseline)]}
        )
        mock_delete = MagicMock(return_value={"deleted": handle})
        return mock_list, mock_read, mock_delete

    def test_returns_correct_delta(self) -> None:
        from ottools.claude_util import elapsed_usage

        baseline = _make_baseline_snapshot(
            total_tokens=1000, total_cost=0.5,
            output_tokens=200, cache_read=300, cache_create=100,
        )
        current_data = _make_ccusage_response(
            total_tokens=1500, total_cost=0.75,
            output_tokens=350, cache_read=450, cache_create=160,
        )
        mock_list, mock_read, mock_delete = self._make_ctx_mocks(baseline)

        with (
            patch("ottools.claude_util._run_ccusage", return_value=current_data),
            patch("ot.ctx.management.ctx_list", mock_list),
            patch("ot.ctx.ctx_read", mock_read),
            patch("ot.ctx.ctx_delete", mock_delete),
        ):
            result = elapsed_usage()

        assert isinstance(result, dict)
        assert result["delta_tokens"] == 500
        assert abs(result["delta_cost_usd"] - 0.25) < 1e-9
        assert result["delta_output_tokens"] == 150
        assert result["delta_cache_read_tokens"] == 150
        assert result["delta_cache_create_tokens"] == 60
        assert result["session_id"] == "test-uuid-1234"
        assert "elapsed_seconds" in result

    def test_error_when_no_baseline(self) -> None:
        from ottools.claude_util import elapsed_usage

        with patch("ot.ctx.management.ctx_list", return_value=[]):
            result = elapsed_usage()

        assert isinstance(result, str)
        assert result.startswith("Error: no baseline found")

    def test_named_recorder_uses_namespaced_source(self) -> None:
        from ottools.claude_util import elapsed_usage

        baseline = _make_baseline_snapshot()
        current_data = _make_ccusage_response(total_tokens=1100, total_cost=0.55)
        mock_list, mock_read, mock_delete = self._make_ctx_mocks(baseline)

        with (
            patch("ottools.claude_util._run_ccusage", return_value=current_data),
            patch("ot.ctx.management.ctx_list", mock_list),
            patch("ot.ctx.ctx_read", mock_read),
            patch("ot.ctx.ctx_delete", mock_delete),
        ):
            result = elapsed_usage(name="A-1")

        mock_list.assert_called_once_with(source="cld_baseline_A-1")
        assert isinstance(result, dict)
        assert result["delta_tokens"] == 100

    def test_baseline_is_deleted_on_success(self) -> None:
        from ottools.claude_util import elapsed_usage

        baseline = _make_baseline_snapshot()
        current_data = _make_ccusage_response(total_tokens=1200, total_cost=0.6)
        mock_list, mock_read, mock_delete = self._make_ctx_mocks(baseline)

        with (
            patch("ottools.claude_util._run_ccusage", return_value=current_data),
            patch("ot.ctx.management.ctx_list", mock_list),
            patch("ot.ctx.ctx_read", mock_read),
            patch("ot.ctx.ctx_delete", mock_delete),
        ):
            elapsed_usage()

        mock_delete.assert_called_once_with("snap0001")

    def test_propagates_ccusage_error(self) -> None:
        from ottools.claude_util import elapsed_usage

        baseline = _make_baseline_snapshot()
        mock_list, mock_read, mock_delete = self._make_ctx_mocks(baseline)

        with (
            patch("ottools.claude_util._run_ccusage", return_value="Error: ccusage not found. Install with: npm install -g ccusage"),
            patch("ot.ctx.management.ctx_list", mock_list),
            patch("ot.ctx.ctx_read", mock_read),
            patch("ot.ctx.ctx_delete", mock_delete),
        ):
            result = elapsed_usage()

        assert isinstance(result, str)
        assert result.startswith("Error:")
