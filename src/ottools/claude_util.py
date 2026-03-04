"""Claude Code session utilities — token usage measurement via ccusage.

Provides start/stop measurement of token usage and cost for a Claude Code
session. Requires ``ccusage`` on PATH (Node.js tool, install with
``npm install -g ccusage``).
"""

from __future__ import annotations

# Pack name for dot notation: claude_util.session_id(), etc.
# Must appear before other imports.
pack = "claude_util"

__all__ = ["elapsed_usage", "session_id", "start_usage"]

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _claude_projects_dir() -> Path:
    return Path.home() / ".claude" / "projects"


def _project_slug(cwd: Path | None = None) -> str:
    """Derive the Claude Code project slug from the working directory.

    Claude Code maps ``/a/b/c`` → ``-a-b-c`` (replaces ``/`` with ``-``,
    keeping the leading ``-`` from the root ``/``).
    """
    p = cwd or Path.cwd()
    return str(p).replace("/", "-")


def _run_ccusage(session_uuid: str) -> dict[str, Any] | str:
    """Call ``ccusage session --id <uuid> --json`` and return parsed JSON.

    Returns a dict on success, or an error string beginning with ``"Error:"``
    if ccusage is not found or returns a non-zero exit code.
    """
    try:
        result = subprocess.run(
            ["ccusage", "session", "--id", session_uuid, "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return "Error: ccusage not found. Install with: npm install -g ccusage"
    except subprocess.TimeoutExpired:
        return "Error: ccusage timed out after 30s"

    if result.returncode != 0:
        stderr = result.stderr.strip()
        return f"Error: ccusage exited with code {result.returncode}: {stderr}"

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return f"Error: failed to parse ccusage output: {exc}"


def _snapshot_from_data(data: dict[str, Any]) -> dict[str, Any]:
    """Extract a normalised snapshot dict from raw ccusage JSON."""
    entries = data.get("entries") or []
    return {
        "session_id": data.get("sessionId", ""),
        "total_tokens": data.get("totalTokens", 0),
        "total_cost_usd": data.get("totalCost", 0.0),
        "total_output_tokens": sum(e.get("outputTokens", 0) for e in entries),
        "total_cache_read_tokens": sum(e.get("cacheReadTokens", 0) for e in entries),
        "total_cache_create_tokens": sum(e.get("cacheCreationTokens", 0) for e in entries),
    }


# ---------------------------------------------------------------------------
# Public tools
# ---------------------------------------------------------------------------


def session_id() -> str:
    """Return the UUID of the current Claude Code session.

    Derives the project slug from the current working directory and finds the
    most recently modified ``*.jsonl`` file in
    ``~/.claude/projects/<slug>/``.

    Returns:
        Session UUID string (e.g. ``"cac49288-0e20-4190-9008-25551a9b3569"``)
        on success, or an error string beginning with ``"Error:"`` on failure.
    """
    slug = _project_slug()
    project_dir = _claude_projects_dir() / slug

    if not project_dir.is_dir():
        return f"Error: project directory not found: {project_dir}"

    jsonl_files = list(project_dir.glob("*.jsonl"))
    if not jsonl_files:
        return f"Error: no JSONL files found in {project_dir}"

    latest = max(jsonl_files, key=lambda p: p.stat().st_mtime)
    return latest.stem


def start_usage(*, name: str = "_default") -> dict[str, Any] | str:
    """Capture a token/cost baseline for the current Claude Code session.

    Calls ``ccusage session --id <uuid> --json`` and stores the result as a
    baseline snapshot in ctx under source ``"cld_baseline_<name>"``. Call
    :func:`elapsed_usage` later with the same ``name`` to compute the delta.

    Args:
        name: Recorder name, allowing multiple independent baselines.
            Defaults to ``"_default"``.

    Returns:
        A dict with ``session_id``, ``snapshot_at``, ``total_tokens``, and
        ``total_cost_usd`` on success, or an error string beginning with
        ``"Error:"`` on failure.
    """
    uuid = session_id()
    if uuid.startswith("Error:"):
        return uuid

    data = _run_ccusage(uuid)
    if isinstance(data, str):
        return data  # error string

    snapshot = _snapshot_from_data(data)
    snapshot["snapshot_at"] = datetime.now(UTC).isoformat()

    # Store in ctx for retrieval by elapsed_usage()
    from ot.ctx.write import ctx_write

    ctx_write(json.dumps(snapshot), source=f"cld_baseline_{name}")

    return {
        "session_id": snapshot["session_id"],
        "snapshot_at": snapshot["snapshot_at"],
        "total_tokens": snapshot["total_tokens"],
        "total_cost_usd": snapshot["total_cost_usd"],
    }


def elapsed_usage(*, name: str = "_default") -> dict[str, Any] | str:
    """Compute the token/cost delta since :func:`start_usage` was called.

    Retrieves the stored baseline from ctx, calls ``ccusage`` again, computes
    the difference, deletes the baseline, and returns a structured report.

    Args:
        name: Recorder name matching the one passed to :func:`start_usage`.
            Defaults to ``"_default"``.

    Returns:
        A dict with ``session_id``, ``delta_tokens``, ``delta_cost_usd``,
        ``delta_output_tokens``, ``delta_cache_read_tokens``,
        ``delta_cache_create_tokens``, and ``elapsed_seconds`` on success,
        or an error string beginning with ``"Error:"`` on failure.
    """
    from ot.ctx import ctx_delete, ctx_read
    from ot.ctx.management import ctx_list

    # Find baseline in ctx
    entries = ctx_list(source=f"cld_baseline_{name}")
    if not entries:
        return f"Error: no baseline found for name={name!r}. Call start_usage(name={name!r}) first."

    baseline_handle = entries[0]["handle"]
    read_result = ctx_read(baseline_handle, limit=10000)
    if "error" in read_result:
        return f"Error: could not read baseline: {read_result['error']}"

    content = "\n".join(read_result["lines"])
    try:
        baseline = json.loads(content)
    except json.JSONDecodeError as exc:
        return f"Error: corrupt baseline snapshot: {exc}"

    # Delete baseline before anything else that could fail
    ctx_delete(baseline_handle)

    uuid = baseline.get("session_id") or session_id()
    if uuid.startswith("Error:"):
        return uuid

    data = _run_ccusage(uuid)
    if isinstance(data, str):
        return data  # error string

    current = _snapshot_from_data(data)
    snapshot_at = baseline.get("snapshot_at", "")
    elapsed: float = 0.0
    if snapshot_at:
        try:
            start_dt = datetime.fromisoformat(snapshot_at)
            elapsed = (datetime.now(UTC) - start_dt).total_seconds()
        except ValueError:
            elapsed = 0.0

    return {
        "session_id": uuid,
        "delta_tokens": current["total_tokens"] - baseline.get("total_tokens", 0),
        "delta_cost_usd": current["total_cost_usd"] - baseline.get("total_cost_usd", 0.0),
        "delta_output_tokens": current["total_output_tokens"] - baseline.get("total_output_tokens", 0),
        "delta_cache_read_tokens": current["total_cache_read_tokens"] - baseline.get("total_cache_read_tokens", 0),
        "delta_cache_create_tokens": current["total_cache_create_tokens"] - baseline.get("total_cache_create_tokens", 0),
        "elapsed_seconds": round(elapsed, 1),
    }
