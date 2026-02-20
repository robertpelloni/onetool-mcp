"""Git worktree management tools.

Manages isolated git worktrees for parallel agents. Trunk mode only.
Each task gets its own directory; agents never touch the main working copy.

Roles:
  - default: runs in the main repo (no .gitworktree.json present)
  - worker: runs in a task directory (.gitworktree.json present)

Requires: git and gh (GitHub CLI, for PR checkout only).
Config: tools.worktree section in .onetool/onetool.yaml (or an included file).
"""

from __future__ import annotations

# Pack for dot notation: worktree.init(), worktree.add(), etc.
pack = "worktree"

__all__ = [
    "add",
    "checkout",
    "clean",
    "commit",
    "diff",
    "info",
    "init",
    "list",
    "log",
    "mark",
    "message",
    "prepare",
    "remove",
    "status",
]

import contextlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from filelock import FileLock
from pydantic import BaseModel, Field

from ot.config import get_tool_config
from ot.logging import LogSpan

# ── Constants ──────────────────────────────────────────────────────────────────

_WORKTREE_FILE = Path(".gitworktree.json")
_TASKS_FILENAME = "tasks.json"
_LOCK_FILENAME = "tasks.json.lock"


# ── Config model ──────────────────────────────────────────────────────────────


class CommitConfig(BaseModel):
    """Conventional commit conventions for worktree.message()."""

    types: list[str] = Field(
        default=[
            "feat", "fix", "refactor", "perf", "docs",
            "test", "build", "ci", "chore", "style", "revert",
        ],
        description="Allowed conventional commit types",
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="Project-specific commit scopes (e.g. tool:worktree, config)",
    )


class Config(BaseModel):
    """Pack configuration - discovered by registry."""

    workspace_dir: str = Field(
        default="../{repo}-work/{task_id}",
        description="Directory template for new worktrees ({task_id}, {base_dir}, {repo})",
    )
    branch_name: str = Field(
        default="{task_id}",
        description="Git branch name template ({task_id}, {repo} available)",
    )
    launch_cmd: str = Field(
        default="cd {workspace_dir} && claude",
        description="Command returned by worktree.add() to start a worker session",
    )
    ot_cmd: str = Field(
        default="worktree.info()",
        description="OneTool tool call the worker agent should run first (e.g. worktree.info())",
    )
    prepare: list[str] = Field(
        default_factory=list,
        description="Shell commands run after git worktree add ({base_dir}, {workspace_dir}, {task_id}, {repo})",
    )
    commit: CommitConfig = Field(
        default_factory=CommitConfig,
        description="Conventional commit conventions for worktree.message()",
    )


# ── Helpers: git subprocess ───────────────────────────────────────────────────


class _GitError(Exception):
    """Raised when a git command returns a non-zero exit code."""


def _git(cmd: list[str], cwd: Path | None = None) -> str:
    """Run a git command and return stdout, raising _GitError on failure."""
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise _GitError(r.stderr.strip())
    return r.stdout.strip()


def _git_is_initialized(path: Path) -> bool:
    """Return True if the given path is inside a git repository."""
    try:
        _git(["git", "rev-parse", "--git-dir"], cwd=path)
        return True
    except _GitError:
        return False


# ── Helpers: config / template expansion ─────────────────────────────────────


def _expand(
    template: str,
    *,
    base_dir: Path,
    workspace_dir: Path,
    task_id: str,
) -> str:
    """Expand template variables: {task_id}, {base_dir}, {workspace_dir}, {repo}."""
    return template.format_map(
        {
            "task_id": task_id,
            "base_dir": str(base_dir),
            "workspace_dir": str(workspace_dir),
            "repo": base_dir.name,
        }
    )


# ── Helpers: state ────────────────────────────────────────────────────────────


@dataclass
class _Task:
    """Runtime state for a single task worktree."""

    description: str
    workspace_dir: str
    root_commit: str | None
    base: str
    state: str  # active | committing | done
    started_at: str
    branch_name: str = ""  # git branch (may differ from task_id)
    num: int = 0  # stable 1-based display number, assigned at add() time


def _base_dir() -> Path:
    """Return the base repo directory.

    If running inside a worktree (.gitworktree.json present), reads base_dir from
    that file. Otherwise uses the current working directory.
    """
    if _WORKTREE_FILE.exists():
        ws: dict[str, Any] = json.loads(_WORKTREE_FILE.read_text())
        return Path(ws["base_dir"])
    return Path.cwd().resolve()


def _tasks_file() -> Path:
    return _base_dir() / _TASKS_FILENAME


def _lock_file() -> FileLock:
    return FileLock(str(_base_dir() / _LOCK_FILENAME))


def _load_tasks() -> dict[str, _Task]:
    f = _tasks_file()
    if not f.exists():
        return {}
    data: dict[str, Any] = json.loads(f.read_text())
    return {k: _Task(**v) for k, v in data.get("tasks", {}).items()}


def _save_tasks(tasks: dict[str, _Task]) -> None:
    _tasks_file().write_text(
        json.dumps({"tasks": {k: asdict(v) for k, v in tasks.items()}}, indent=2)
    )


def _add_task(task_id: str, task: _Task) -> None:
    with _lock_file():
        tasks = _load_tasks()
        if task_id in tasks:
            raise ValueError(f"task {task_id!r} already exists")
        tasks[task_id] = task
        _save_tasks(tasks)


def _update_task(task_id: str, **kwargs: Any) -> None:
    with _lock_file():
        tasks = _load_tasks()
        if task_id not in tasks:
            raise KeyError(f"task {task_id!r} not found in tasks.json")
        for k, v in kwargs.items():
            setattr(tasks[task_id], k, v)
        _save_tasks(tasks)


# ── Helpers: worktree.json ────────────────────────────────────────────────────


def _read_worktree_json() -> dict[str, Any]:
    """Return contents of .gitworktree.json if present, else empty dict."""
    if not _WORKTREE_FILE.exists():
        return {}
    return json.loads(_WORKTREE_FILE.read_text())  # type: ignore[no-any-return]


def _normalize(s: str) -> str:
    """Normalize a string for fuzzy matching: lowercase, strip spaces/-/_."""
    return s.lower().replace(" ", "").replace("-", "").replace("_", "")


def _resolve_task(id: str) -> tuple[str, _Task] | None:
    """Resolve a task by numeric index or fuzzy task ID match.

    Tries in order:
      1. Numeric index (1-based) into the tasks list
      2. Exact task ID match (case-insensitive)
      3. Fuzzy match ignoring spaces, dashes, underscores

    Returns (task_id, _Task), or None if not found.
    """
    tasks = _load_tasks()
    if not tasks:
        return None

    # 1. Numeric — match stored task.num
    try:
        n = int(id)
        for k, t in tasks.items():
            if t.num == n:
                return k, t
        return None
    except ValueError:
        pass

    # 2. Exact case-insensitive match
    for k, t in tasks.items():
        if k.lower() == id.lower():
            return k, t

    # 3. Fuzzy match
    needle = _normalize(id)
    for k, t in tasks.items():
        if _normalize(k) == needle:
            return k, t

    return None


def _workspace_dir_for(task_id: str, cfg: Config, base_dir: Path) -> Path:
    """Resolve the absolute worktree directory for a task from config template."""
    raw = _expand(cfg.workspace_dir, base_dir=base_dir, workspace_dir=Path("placeholder"), task_id=task_id)
    return Path(raw).resolve()


def _require_default() -> None:
    """Raise if called from inside a worker directory."""
    if _WORKTREE_FILE.exists():
        ws: dict[str, Any] = json.loads(_WORKTREE_FILE.read_text())
        raise RuntimeError(
            f"must be run from the default worktree, not a work worktree "
            f"(task_id={ws.get('task_id')!r})"
        )


def _require_worker() -> dict[str, Any]:
    """Raise if not in a worker directory; return worktree json."""
    if not _WORKTREE_FILE.exists():
        raise RuntimeError(
            "must be run from a work worktree (.gitworktree.json not found)"
        )
    return json.loads(_WORKTREE_FILE.read_text())  # type: ignore[no-any-return]


# ── Tools ──────────────────────────────────────────────────────────────────────


def init() -> dict[str, Any]:
    """One-time setup for the repo.

    Verifies the repository is a git repo and adds runtime state files
    (tasks.json, tasks.json.lock) to .gitignore.
    Reversed by worktree.clean().

    Returns:
        Status dict with ok=True.

    Raises:
        RuntimeError: If not a git repository.

    Example:
        worktree.init()
    """
    with LogSpan(span="worktree.init") as s:
        _require_default()
        base = Path.cwd().resolve()
        if not _git_is_initialized(base):
            raise RuntimeError("not a git repository — run from a git repo root")
        gitignore = base / ".gitignore"
        lines = gitignore.read_text().splitlines() if gitignore.exists() else []
        added: list[str] = []
        for entry in [_TASKS_FILENAME, _LOCK_FILENAME]:
            if entry not in lines:
                lines.append(entry)
                added.append(entry)
        gitignore.write_text("\n".join(lines) + "\n")
        s.add("gitignore_entries_added", len(added))
        return {"ok": True}


def add(*, id: str, description: str, branch: str | None = None) -> dict[str, Any]:
    """Create a new task worktree, run prepare hooks, and return the launch command.

    Fetches origin, creates a git worktree with a new branch for the task,
    runs prepare hooks from worktree.yaml, writes .gitworktree.json into the task
    directory, and records the task in tasks.json.

    Args:
        id: Unique task identifier (e.g. "change-1", "fix-login").
        description: Human-readable description of the task.
        branch: Base branch to create the worktree from. Defaults to the
            current branch when omitted.

    Returns:
        Dict with task_id, absolute worktree dir path, and launch command.

    Example:
        worktree.add(id="change-1", description="Fix login bug")
        worktree.add(id="change-1", description="Fix login bug", branch="main")
        worktree.add(id="change-1", description="Fix login bug", branch="feat/auth")
    """
    with LogSpan(span="worktree.add", id=id) as s:
        _require_default()
        cfg = get_tool_config("worktree", Config)
        base = Path.cwd().resolve()
        base_branch = _git(["git", "branch", "--show-current"], cwd=base) if branch is None else branch
        ws_dir = _workspace_dir_for(id, cfg, base)
        branch_name = _expand(cfg.branch_name, base_dir=base, workspace_dir=ws_dir, task_id=id)
        ws_dir.parent.mkdir(parents=True, exist_ok=True)
        _git(["git", "fetch", "origin", base_branch], cwd=base)
        _git(["git", "worktree", "add", "-b", branch_name, str(ws_dir), f"origin/{base_branch}"], cwd=base)
        for cmd_template in cfg.prepare:
            expanded = _expand(cmd_template, base_dir=base, workspace_dir=ws_dir, task_id=id)
            subprocess.run(["sh", "-c", expanded], check=True)
        root_commit = _git(["git", "rev-parse", "--short", "HEAD"], cwd=ws_dir)
        (ws_dir / _WORKTREE_FILE).write_text(
            json.dumps({
                "task_id": id,
                "base_dir": str(base),
                "branch": branch_name,
                "branch_name": branch_name,
                "base": base_branch,
                "root_commit": root_commit,
            })
        )
        existing = _load_tasks()
        next_num = max((t.num for t in existing.values()), default=0) + 1
        _add_task(
            id,
            _Task(
                description=description,
                workspace_dir=str(ws_dir),
                root_commit=root_commit,
                base=base_branch,
                state="active",
                started_at=datetime.now(UTC).isoformat(),
                branch_name=branch_name,
                num=next_num,
            ),
        )
        launch_cmd = _expand(cfg.launch_cmd, base_dir=base, workspace_dir=ws_dir, task_id=id)
        ot_cmd = _expand(cfg.ot_cmd, base_dir=base, workspace_dir=ws_dir, task_id=id)
        s.add("workspace_dir", str(ws_dir))
        return {"task_id": id, "dir": str(ws_dir), "launch_cmd": launch_cmd, "ot_cmd": ot_cmd}


def info() -> dict[str, Any]:
    """Show current worktree role and context.

    Returns role="work" when running inside a task worktree (.gitworktree.json
    present), role="base" otherwise.

    Returns:
        Dict with role, base_dir, and current branch. Work worktrees also
        include task_id, branch, base, and root_commit.

    Example:
        worktree.info()
    """
    with LogSpan(span="worktree.info") as s:
        cwd = Path.cwd().resolve()
        ws = _read_worktree_json()
        if ws:
            s.add("dir_type", "work")
            return {
                "dir_type": "work",
                "task_id": ws["task_id"],
                "branch": ws.get("branch"),
                "base": ws.get("base"),
                "root_commit": ws.get("root_commit"),
                "base_dir": ws["base_dir"],
            }
        s.add("dir_type", "base")
        return {
            "dir_type": "base",
            "branch": _git(["git", "branch", "--show-current"], cwd=cwd),
            "base_dir": str(cwd),
        }


def checkout(*, branch: str | None = None, pr: int | None = None) -> dict[str, Any]:
    """Switch the worktree to an existing branch or PR.

    Resets the worktree to the specified remote branch or PR and updates
    root_commit in .gitworktree.json. Requires branch or pr.

    Args:
        branch: Existing remote branch to check out.
        pr: GitHub PR number to check out.

    Returns:
        Dict with root_commit and base revision.

    Raises:
        ValueError: If neither branch nor pr is provided.

    Example:
        worktree.checkout(branch="feature/auth")
        worktree.checkout(pr=142)
    """
    with LogSpan(span="worktree.checkout", branch=branch, pr=pr) as s:
        if not branch and not pr:
            raise ValueError("branch or pr is required")
        ws = _require_worker()
        task_id: str = ws["task_id"]
        cwd = Path.cwd()
        if pr:
            r = subprocess.run(
                ["gh", "pr", "view", str(pr), "--json", "headRefName"],
                capture_output=True,
                text=True,
                check=True,
            )
            branch = json.loads(r.stdout)["headRefName"]
        _git(["git", "fetch", "origin"], cwd=cwd)
        _git(["git", "reset", "--hard", f"origin/{branch}"], cwd=cwd)
        root_commit = _git(["git", "rev-parse", "--short", "HEAD"], cwd=cwd)
        ws["root_commit"] = root_commit
        _WORKTREE_FILE.write_text(json.dumps(ws))
        _update_task(task_id, root_commit=root_commit)
        s.add("root_commit", root_commit)
        return {"root_commit": root_commit, "base": f"origin/{branch}"}


def prepare() -> dict[str, Any]:
    """Re-run setup hooks (refresh secrets, venv, etc.).

    Re-runs the prepare hooks from worktree.yaml in the current worktree
    directory. Useful after pulling latest changes or refreshing env files.

    Returns:
        Dict with ok=True and count of hooks run.

    Example:
        worktree.prepare()
    """
    with LogSpan(span="worktree.prepare") as s:
        ws = _require_worker()
        task_id: str = ws["task_id"]
        base = Path(ws["base_dir"])
        ws_dir = Path.cwd().resolve()
        cfg = get_tool_config("worktree", Config)
        for cmd_template in cfg.prepare:
            expanded = _expand(
                cmd_template, base_dir=base, workspace_dir=ws_dir, task_id=task_id
            )
            subprocess.run(["sh", "-c", expanded], check=True)
        s.add("hooks_run", len(cfg.prepare))
        return {"ok": True, "hooks_run": len(cfg.prepare)}


def log(*, id: str | int | None = None) -> str:
    """Show commit history and diff stat.

    Shows git log and diff stat for the current worktree task, a task looked
    up by index or fuzzy ID, or a raw git revision range.

    Args:
        id: Task index (1-based), task ID (fuzzy, case-insensitive), or raw
            commit hash (optional; defaults to the current worktree
            root_commit, falling back to HEAD).

    Returns:
        Commit history followed by diff stat as a string.

    Example:
        worktree.log()              # current worktree
        worktree.log(id=1)          # first task by index
        worktree.log(id="a")        # fuzzy match task "A"
        worktree.log(id="big-fix")  # fuzzy: matches "big_fix", "BIGFIX" etc.
        worktree.log(id="abc1234")  # raw commit hash
    """
    with LogSpan(span="worktree.log", id=id) as s:
        cwd = Path.cwd()
        ws = _read_worktree_json()

        header: str | None = None
        root_commit: str | None = None

        if id is not None:
            resolved = _resolve_task(str(id))
            if resolved:
                task_id, task = resolved
                header = f"{task_id}: {task.description}"
                root_commit = task.root_commit
                cwd = Path(task.workspace_dir)
            else:
                # Fall back to raw git commit hash / ref
                root_commit = str(id)
                header = str(id)
        elif ws and ws.get("root_commit"):
            root_commit = ws["root_commit"]

        range_spec = f"{root_commit}..HEAD" if root_commit else "HEAD~10..HEAD"

        history = _git(["git", "log", "--oneline", range_spec], cwd=cwd)
        stat = _git(["git", "diff", "--stat", range_spec], cwd=cwd)
        s.add("range", range_spec)
        prefix = f"# {header}\n\n" if header else ""
        return f"{prefix}{history}\n\n{stat}"


def diff(*, id: str | int | None = None, stat: bool = False) -> str:
    """Show changes in a task worktree since the root commit.

    Args:
        id: Task index (1-based), task ID (fuzzy), or None for current worktree.
        stat: Show diff stat summary instead of full diff.

    Returns:
        Unified diff or diff stat as a string.

    Example:
        worktree.diff()               # current worktree, full diff
        worktree.diff(stat=True)      # current worktree, stat only
        worktree.diff(id=1)           # task 1 by index
        worktree.diff(id="fix-login") # fuzzy task ID
    """
    with LogSpan(span="worktree.diff", id=id, stat=stat) as s:
        cwd = Path.cwd()
        ws = _read_worktree_json()
        root_commit: str | None = None

        if id is not None:
            resolved = _resolve_task(str(id))
            if resolved:
                _, task = resolved
                root_commit = task.root_commit
                cwd = Path(task.workspace_dir)
        elif ws and ws.get("root_commit"):
            root_commit = ws["root_commit"]

        range_spec = f"{root_commit}..HEAD" if root_commit else "HEAD"
        cmd = ["git", "diff", "--stat", range_spec] if stat else ["git", "diff", range_spec]
        result = _git(cmd, cwd=cwd)
        s.add("range", range_spec)
        return result


def status(*, id: str | int | None = None) -> str:
    """Show git status for a task worktree.

    Args:
        id: Task index, task ID (fuzzy), or None for current worktree.

    Returns:
        git status --short output as a string.

    Example:
        worktree.status()          # current worktree
        worktree.status(id=2)      # task 2
    """
    with LogSpan(span="worktree.status", id=id) as s:
        cwd = Path.cwd()
        if id is not None:
            resolved = _resolve_task(str(id))
            if resolved:
                _, task = resolved
                cwd = Path(task.workspace_dir)
        result = _git(["git", "status", "--short"], cwd=cwd)
        s.add("cwd", str(cwd))
        return result


def message() -> str:
    """Gather context for writing a conventional commit message.

    Collects git status, diff stat, and recent log from the current worktree,
    then formats it alongside the project's conventional commit conventions
    (types and scopes from worktree config). Returns a ready-to-use context
    block for the agent to synthesize a commit message from.

    Must be run from a work worktree.

    Returns:
        Formatted string with git context and commit conventions.

    Raises:
        RuntimeError: If called from the base worktree.

    Example:
        worktree.message()
    """
    with LogSpan(span="worktree.message") as s:
        ws = _require_worker()
        root_commit: str | None = ws.get("root_commit")
        cwd = Path.cwd()
        cfg = get_tool_config("worktree", Config)

        git_status = _git(["git", "status", "--short"], cwd=cwd)
        range_spec = f"{root_commit}..HEAD" if root_commit else "HEAD"
        diff_stat = _git(["git", "diff", "--stat", range_spec], cwd=cwd)
        git_log = _git(["git", "log", "--oneline", range_spec], cwd=cwd)

        commit_cfg = cfg.commit
        types_str = ", ".join(commit_cfg.types)
        scopes_line = f"Scopes: {', '.join(commit_cfg.scopes)}\n" if commit_cfg.scopes else ""
        root_ref = root_commit or "HEAD"

        conventions = (
            "## Conventional commit format\n"
            "<type>(<scope>): <description>\n"
            "[optional body]\n"
            "[Ref: #issue]\n\n"
            f"Types: {types_str}\n"
            f"{scopes_line}"
            "Rules:\n"
            "- type and scope are required; scope from the list above\n"
            "- description: imperative mood, lowercase, no period, 50-72 chars ideal\n"
            "- multiple changes: separate with semicolons, most important first\n"
            "- issue reference on second line only: Ref: #123 (not Refs)"
        )
        parts = [
            f"## Changed files\n{git_status}",
            f"## Diff stat (since {root_ref})\n{diff_stat}",
            f"## Commits since root\n{git_log}",
            conventions,
        ]
        s.add("root_commit", root_ref)
        return "\n\n".join(parts)


def list() -> dict[str, Any]:
    """Show all active tasks and their state.

    Reads tasks.json and the git worktree list to show all registered tasks
    with their current status and directory.

    Returns:
        Dict with tasks mapping and git worktree list output.

    Example:
        worktree.list()
    """
    with LogSpan(span="worktree.list") as s:
        _require_default()
        tasks = _load_tasks()
        result = [
            {
                "num": task.num,
                "id": task_id,
                "description": task.description,
                "state": task.state,
                "base": task.base,
                "root_commit": task.root_commit,
                "dir": task.workspace_dir,
            }
            for task_id, task in tasks.items()
        ]
        s.add("task_count", len(result))
        return {"tasks": result}


def commit(*, message: str) -> dict[str, Any]:
    """Squash, rebase, conflict-check, and push to main.

    Soft-resets to the root commit to squash all task changes into one commit,
    rebases onto latest main, checks for conflicts, then pushes to origin.

    Args:
        message: Commit message for the squashed change.

    Returns:
        Dict with commit hash and pushed=True.

    Raises:
        RuntimeError: If conflicts are found after rebase.

    Example:
        worktree.commit(message="Fix login session expiry")
    """
    with LogSpan(span="worktree.commit") as s:
        ws = _require_worker()
        task_id: str = ws["task_id"]
        root_commit: str | None = ws.get("root_commit")
        cwd = Path.cwd()
        base_branch: str = ws["base"]
        _update_task(task_id, state="committing")
        conflict_detected = False
        with _lock_file():
            if root_commit:
                _git(["git", "reset", "--soft", root_commit], cwd=cwd)
            _git(["git", "commit", "-m", message], cwd=cwd)
            _git(["git", "fetch", "origin"], cwd=cwd)
            _git(["git", "rebase", f"origin/{base_branch}"], cwd=cwd)
            status = _git(["git", "status", "--porcelain"], cwd=cwd)
            conflict_markers = any(
                line[:2] in ("UU", "AA", "DD", "AU", "UA", "DU", "UD")
                for line in status.splitlines()
            )
            if conflict_markers:
                conflict_detected = True
            else:
                _git(["git", "push", "origin", f"HEAD:{base_branch}"], cwd=cwd)
        if conflict_detected:
            _update_task(task_id, state="active")
            raise RuntimeError(
                "conflicts after rebase — resolve before committing"
            )
        commit_id = _git(["git", "rev-parse", "--short", "HEAD"], cwd=cwd)
        _update_task(task_id, state="done")
        s.add("commit", commit_id)
        return {"commit": commit_id, "pushed": True}


def remove(*, id: str | int) -> dict[str, Any]:
    """Remove a task worktree, delete its branch, and unregister it.

    Args:
        id: Task index (1-based), task ID, or fuzzy match.

    Returns:
        Dict with removed=True and task_id.

    Example:
        worktree.remove(id=1)
        worktree.remove(id="big-change")
    """
    with LogSpan(span="worktree.remove", id=id) as s:
        _require_default()
        resolved = _resolve_task(str(id))
        if not resolved:
            raise KeyError(f"task {id!r} not found")
        task_id, task = resolved
        warnings: list[str] = []
        if task.state not in ("done",):
            warnings.append(f"task {task_id!r} was {task.state!r} — removed anyway")
        base = _base_dir()
        ws_dir = Path(task.workspace_dir)
        branch = task.branch_name or task_id
        with contextlib.suppress(_GitError):
            _git(["git", "worktree", "remove", "--force", str(ws_dir)], cwd=base)
        if ws_dir.exists():
            shutil.rmtree(ws_dir)
        with contextlib.suppress(_GitError):
            _git(["git", "branch", "-D", branch], cwd=base)
        with _lock_file():
            tasks = _load_tasks()
            tasks.pop(task_id, None)
            _save_tasks(tasks)
        s.add("task_id", task_id)
        return {"removed": True, "task_id": task_id, "warnings": warnings}


def mark(*, id: str | int, state: str) -> dict[str, Any]:
    """Set the state of a task.

    Args:
        id: Task ID (fuzzy match supported).
        state: New state (e.g. "active", "done", "pending").

    Returns:
        Dict with task_id and updated state.

    Example:
        worktree.mark(id="big-change", state="done")
    """
    with LogSpan(span="worktree.mark", id=id, state=state) as s:
        _require_default()
        resolved = _resolve_task(str(id))
        if not resolved:
            raise KeyError(f"task {id!r} not found")
        task_id, _ = resolved
        _update_task(task_id, state=state)
        s.add("task_id", task_id)
        return {"task_id": task_id, "state": state}


def clean() -> dict[str, Any]:
    """Tear down all tasks and remove manager state.

    Removes all task directories, unregisters all git worktrees, deletes
    tasks.json, and strips the tasks.json / tasks.json.lock entries from
    .gitignore. Warns (but does not abort) if any tasks are active or
    committing.

    Returns:
        Dict with removed list and any warnings.

    Example:
        worktree.clean()
    """
    with LogSpan(span="worktree.clean") as s:
        _require_default()
        base = _base_dir()
        with _lock_file():
            tasks = _load_tasks()
            active = [k for k, t in tasks.items() if t.state in ("active", "committing")]
            warnings: list[str] = []
            if active:
                warnings.append(f"active tasks: {', '.join(active)}")
            removed: list[str] = []
            for task_id, task in tasks.items():
                ws_dir = Path(task.workspace_dir)
                branch = task.branch_name or task_id
                with contextlib.suppress(_GitError):
                    _git(["git", "worktree", "remove", "--force", str(ws_dir)], cwd=base)
                if ws_dir.exists():
                    shutil.rmtree(ws_dir)
                with contextlib.suppress(_GitError):
                    _git(["git", "branch", "-D", branch], cwd=base)
                removed.append(task_id)
            _git(["git", "worktree", "prune"], cwd=base)
            tasks_f = _tasks_file()
            lock_f = base / _LOCK_FILENAME
            if tasks_f.exists():
                tasks_f.unlink()
            if lock_f.exists():
                lock_f.unlink()

        # Strip tasks.json / tasks.json.lock from .gitignore
        gitignore = base / ".gitignore"
        if gitignore.exists():
            lines = [
                ln for ln in gitignore.read_text().splitlines()
                if ln not in (_TASKS_FILENAME, _LOCK_FILENAME)
            ]
            gitignore.write_text("\n".join(lines) + "\n")

        s.add("removed_count", len(removed))
        return {"removed": removed, "warnings": warnings}
