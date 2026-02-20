"""Unit tests for worktree tool pack.

Tests git worktree management functions using mocked git subprocess calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_tasks_json(base_dir: Path, tasks: dict[str, Any]) -> None:
    """Write tasks.json to base_dir."""
    (base_dir / "tasks.json").write_text(
        json.dumps({"tasks": tasks}, indent=2)
    )


def _make_worktree_json(cwd: Path, data: dict[str, Any]) -> None:
    """Write .gitworktree.json to cwd (simulates a work worktree)."""
    (cwd / ".gitworktree.json").write_text(json.dumps(data))


def _task_dict(
    *,
    description: str = "Test task",
    workspace_dir: str = "/tmp/work/task1",
    root_commit: str | None = "abc1234",
    base: str = "main",
    state: str = "active",
    started_at: str = "2026-01-01T00:00:00+00:00",
    branch_name: str = "",
    num: int = 1,
) -> dict[str, Any]:
    """Build a task dict for tasks.json."""
    return {
        "description": description,
        "workspace_dir": workspace_dir,
        "root_commit": root_commit,
        "base": base,
        "state": state,
        "started_at": started_at,
        "branch_name": branch_name,
        "num": num,
    }


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def base_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Minimal fake git repo in tmp_path with cwd set to it."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n\trepositoryformatversion = 0\n")
    (tmp_path / ".gitignore").write_text("")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def mock_git(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Monkeypatch otdev.tools.worktree._git; returns '' by default."""
    mock = MagicMock(return_value="")
    monkeypatch.setattr("otdev.tools.worktree._git", mock)
    return mock


# ── Tests: init() ─────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.tools
class TestInit:
    def test_init_adds_gitignore_entries(
        self, base_dir: Path, mock_git: MagicMock
    ) -> None:
        """init() appends tasks.json and tasks.json.lock to .gitignore."""
        from otdev.tools.worktree import init

        result = init()

        assert result == {"ok": True}
        gitignore = (base_dir / ".gitignore").read_text()
        assert "tasks.json" in gitignore
        assert "tasks.json.lock" in gitignore

    def test_init_skips_duplicates(
        self, base_dir: Path, mock_git: MagicMock
    ) -> None:
        """init() does not add duplicate entries to .gitignore."""
        from otdev.tools.worktree import init

        (base_dir / ".gitignore").write_text("tasks.json\ntasks.json.lock\n")

        init()

        lines = (base_dir / ".gitignore").read_text().splitlines()
        assert lines.count("tasks.json") == 1
        assert lines.count("tasks.json.lock") == 1

    def test_init_raises_on_non_repo(
        self, base_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """init() raises RuntimeError when not in a git repo."""
        from otdev.tools.worktree import _GitError, init

        def raise_git_error(cmd: list[str], cwd: Path | None = None) -> str:
            raise _GitError("not a git repo")

        monkeypatch.setattr("otdev.tools.worktree._git", raise_git_error)

        with pytest.raises(RuntimeError, match="not a git repository"):
            init()


# ── Tests: add() ──────────────────────────────────────────────────────────────


def _make_add_git_mock(
    monkeypatch: pytest.MonkeyPatch,
    *,
    current_branch: str = "main",
    root_commit: str = "abc1234",
) -> MagicMock:
    """Build a _git mock suitable for add() tests.

    Creates the workspace directory when git worktree add is called,
    mimicking real git behaviour.
    """

    def side_effect(cmd: list[str], cwd: Path | None = None) -> str:
        if cmd[1:3] == ["branch", "--show-current"]:
            return current_branch
        if cmd[1:3] == ["worktree", "add"]:
            # git worktree add -b <branch> <ws_dir> <ref>
            ws_dir = Path(cmd[5])
            ws_dir.mkdir(parents=True, exist_ok=True)
            return ""
        if cmd[1:3] == ["rev-parse", "--short"]:
            return root_commit
        return ""

    mock = MagicMock(side_effect=side_effect)
    monkeypatch.setattr("otdev.tools.worktree._git", mock)
    return mock


@pytest.mark.unit
@pytest.mark.tools
class TestAdd:
    def test_add_creates_worktree_and_registers_task(
        self, base_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """add() creates worktree, registers task in tasks.json, returns launch_cmd."""
        from otdev.tools.worktree import Config, add

        _make_add_git_mock(monkeypatch)
        cfg = Config(workspace_dir=str(tmp_path / "worktrees" / "{task_id}"))
        with patch("otdev.tools.worktree.get_tool_config", return_value=cfg):
            result = add(id="change-1", description="Fix login bug", branch="main")

        assert result["task_id"] == "change-1"
        assert "change-1" in result["dir"]
        assert "launch_cmd" in result
        assert "ot_cmd" in result

        tasks_data = json.loads((base_dir / "tasks.json").read_text())
        assert "change-1" in tasks_data["tasks"]
        task = tasks_data["tasks"]["change-1"]
        assert task["state"] == "active"
        assert task["branch_name"] == "change-1"  # default template = {task_id}

    def test_add_uses_current_branch_when_branch_none(
        self, base_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """add() uses current git branch when branch=None."""
        from otdev.tools.worktree import Config, add

        mock = _make_add_git_mock(monkeypatch, current_branch="feat/auth")
        cfg = Config(workspace_dir=str(tmp_path / "worktrees" / "{task_id}"))
        with patch("otdev.tools.worktree.get_tool_config", return_value=cfg):
            add(id="task-1", description="task", branch=None)

        calls = [c.args[0] for c in mock.call_args_list]
        assert any(c[1:3] == ["branch", "--show-current"] for c in calls)

    def test_add_rejects_duplicate_task(
        self, base_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """add() raises ValueError when task ID already exists."""
        from otdev.tools.worktree import Config, add

        _make_tasks_json(base_dir, {"change-1": _task_dict()})
        _make_add_git_mock(monkeypatch)
        cfg = Config(workspace_dir=str(tmp_path / "worktrees" / "{task_id}"))
        with patch("otdev.tools.worktree.get_tool_config", return_value=cfg):
            with pytest.raises(ValueError, match="already exists"):
                add(id="change-1", description="Duplicate", branch="main")

    def test_add_expands_branch_name_template(
        self, base_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """add() expands branch_name config template when creating the branch."""
        from otdev.tools.worktree import Config, add

        captured_branches: list[str] = []

        def side_effect(cmd: list[str], cwd: Path | None = None) -> str:
            if cmd[1:3] == ["branch", "--show-current"]:
                return "main"
            if cmd[1:3] == ["worktree", "add"]:
                captured_branches.append(cmd[4])  # -b <branch_name>
                ws_dir = Path(cmd[5])
                ws_dir.mkdir(parents=True, exist_ok=True)
                return ""
            if cmd[1:3] == ["rev-parse", "--short"]:
                return "abc1234"
            return ""

        monkeypatch.setattr(
            "otdev.tools.worktree._git", MagicMock(side_effect=side_effect)
        )
        cfg = Config(
            workspace_dir=str(tmp_path / "worktrees" / "{task_id}"),
            branch_name="wt/{task_id}",
        )
        with patch("otdev.tools.worktree.get_tool_config", return_value=cfg):
            add(id="change-1", description="Prefixed branch", branch="main")

        assert captured_branches == ["wt/change-1"]

        tasks_data = json.loads((base_dir / "tasks.json").read_text())
        assert "change-1" in tasks_data["tasks"]
        assert tasks_data["tasks"]["change-1"]["branch_name"] == "wt/change-1"


# ── Tests: info() ─────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.tools
class TestInfo:
    def test_info_returns_base_when_no_worktree_json(
        self, base_dir: Path, mock_git: MagicMock
    ) -> None:
        """info() returns dir_type='base' when .gitworktree.json absent."""
        from otdev.tools.worktree import info

        mock_git.return_value = "main"

        result = info()

        assert result["dir_type"] == "base"
        assert "base_dir" in result
        assert "branch" in result

    def test_info_returns_work_when_worktree_json_present(
        self, base_dir: Path, mock_git: MagicMock
    ) -> None:
        """info() returns dir_type='work' with task context when .gitworktree.json present."""
        from otdev.tools.worktree import info

        _make_worktree_json(
            base_dir,
            {
                "task_id": "change-1",
                "base_dir": str(base_dir),
                "branch": "change-1",
                "branch_name": "change-1",
                "base": "main",
                "root_commit": "abc1234",
            },
        )

        result = info()

        assert result["dir_type"] == "work"
        assert result["task_id"] == "change-1"
        assert result["base"] == "main"
        assert result["root_commit"] == "abc1234"


# ── Tests: list() ─────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.tools
class TestList:
    def test_list_returns_empty_when_no_tasks_json(
        self, base_dir: Path, mock_git: MagicMock
    ) -> None:
        """list() returns empty tasks list when tasks.json absent."""
        from otdev.tools.worktree import list

        result = list()

        assert result == {"tasks": []}

    def test_list_returns_all_tasks(
        self, base_dir: Path, mock_git: MagicMock
    ) -> None:
        """list() returns all registered tasks with expected fields."""
        ws_dir = str(base_dir / "worktrees" / "change-1")
        _make_tasks_json(
            base_dir,
            {
                "change-1": _task_dict(
                    description="Fix login",
                    workspace_dir=ws_dir,
                    num=1,
                    state="active",
                ),
            },
        )

        from otdev.tools.worktree import list

        result = list()

        assert len(result["tasks"]) == 1
        task = result["tasks"][0]
        assert task["id"] == "change-1"
        assert task["description"] == "Fix login"
        assert task["state"] == "active"
        assert task["num"] == 1
        assert task["dir"] == ws_dir


# ── Tests: log() ──────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.tools
class TestLog:
    def test_log_returns_git_log_for_root_commit(
        self, base_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """log() shows git log and diff stat from root_commit to HEAD."""
        _make_worktree_json(
            base_dir,
            {
                "task_id": "change-1",
                "base_dir": str(base_dir),
                "branch": "change-1",
                "base": "main",
                "root_commit": "abc1234",
            },
        )

        expected_log = "abc1234 Add feature"
        expected_stat = "1 file changed, 5 insertions"

        def side_effect(cmd: list[str], cwd: Path | None = None) -> str:
            if cmd[1:3] == ["log", "--oneline"]:
                return expected_log
            if cmd[1:3] == ["diff", "--stat"]:
                return expected_stat
            return ""

        monkeypatch.setattr(
            "otdev.tools.worktree._git", MagicMock(side_effect=side_effect)
        )

        from otdev.tools.worktree import log

        result = log()

        assert expected_log in result
        assert expected_stat in result

    def test_log_resolves_by_index(
        self, base_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """log(id=1) shows log for task with num=1."""
        ws_dir = str(base_dir / "worktrees" / "task-a")
        _make_tasks_json(
            base_dir,
            {"task-a": _task_dict(workspace_dir=ws_dir, num=1, root_commit="def5678")},
        )
        monkeypatch.setattr(
            "otdev.tools.worktree._git", MagicMock(return_value="commit line")
        )

        from otdev.tools.worktree import log

        result = log(id=1)

        assert "task-a" in result

    def test_log_resolves_by_fuzzy_id(
        self, base_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """log(id='bigfix') fuzzy-matches task 'big-fix'."""
        ws_dir = str(base_dir / "worktrees" / "big-fix")
        _make_tasks_json(
            base_dir,
            {"big-fix": _task_dict(workspace_dir=ws_dir, num=1)},
        )
        monkeypatch.setattr(
            "otdev.tools.worktree._git", MagicMock(return_value="")
        )

        from otdev.tools.worktree import log

        result = log(id="bigfix")

        assert "big-fix" in result


# ── Tests: diff() ─────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.tools
class TestDiff:
    def test_diff_returns_diff_since_root_commit(
        self, base_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """diff() returns git diff {root_commit}..HEAD from current worktree."""
        _make_worktree_json(
            base_dir,
            {
                "task_id": "change-1",
                "base_dir": str(base_dir),
                "branch": "change-1",
                "base": "main",
                "root_commit": "abc1234",
            },
        )
        expected = "diff --git a/foo.py b/foo.py\n+added line"
        mock = MagicMock(return_value=expected)
        monkeypatch.setattr("otdev.tools.worktree._git", mock)

        from otdev.tools.worktree import diff

        result = diff()

        assert result == expected
        args = mock.call_args.args[0]
        assert "abc1234..HEAD" in args

    def test_diff_stat_adds_stat_flag(
        self, base_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """diff(stat=True) calls git diff --stat."""
        _make_worktree_json(
            base_dir,
            {
                "task_id": "change-1",
                "base_dir": str(base_dir),
                "branch": "change-1",
                "base": "main",
                "root_commit": "abc1234",
            },
        )
        mock = MagicMock(return_value="1 file changed")
        monkeypatch.setattr("otdev.tools.worktree._git", mock)

        from otdev.tools.worktree import diff

        diff(stat=True)

        args = mock.call_args.args[0]
        assert "--stat" in args

    def test_diff_resolves_by_id(
        self, base_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """diff(id='fix-login') resolves task and runs diff in task directory."""
        ws_dir = base_dir / "worktrees" / "fix-login"
        _make_tasks_json(
            base_dir,
            {
                "fix-login": _task_dict(
                    workspace_dir=str(ws_dir), root_commit="abc1234", num=1
                )
            },
        )
        mock = MagicMock(return_value="diff output")
        monkeypatch.setattr("otdev.tools.worktree._git", mock)

        from otdev.tools.worktree import diff

        result = diff(id="fix-login")

        assert result == "diff output"
        actual_cwd = mock.call_args.kwargs["cwd"]
        assert Path(actual_cwd) == ws_dir


# ── Tests: status() ───────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.tools
class TestStatus:
    def test_status_returns_git_status_short(
        self, base_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """status() returns git status --short output."""
        mock = MagicMock(return_value="M  foo.py")
        monkeypatch.setattr("otdev.tools.worktree._git", mock)

        from otdev.tools.worktree import status

        result = status()

        assert result == "M  foo.py"
        args = mock.call_args.args[0]
        assert "status" in args
        assert "--short" in args

    def test_status_resolves_by_id(
        self, base_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """status(id=2) runs git status --short in that task's directory."""
        ws_dir = base_dir / "worktrees" / "task-2"
        _make_tasks_json(
            base_dir,
            {"task-2": _task_dict(workspace_dir=str(ws_dir), num=2)},
        )
        mock = MagicMock(return_value="?? new_file.py")
        monkeypatch.setattr("otdev.tools.worktree._git", mock)

        from otdev.tools.worktree import status

        result = status(id=2)

        assert result == "?? new_file.py"
        actual_cwd = mock.call_args.kwargs["cwd"]
        assert Path(actual_cwd) == ws_dir


# ── Tests: commit() ───────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.tools
class TestCommit:
    def _setup_work_worktree(self, base_dir: Path, task_state: str = "active") -> None:
        """Write .gitworktree.json and tasks.json for commit() tests."""
        _make_worktree_json(
            base_dir,
            {
                "task_id": "change-1",
                "base_dir": str(base_dir),
                "branch": "change-1",
                "base": "main",
                "root_commit": "abc1234",
            },
        )
        _make_tasks_json(
            base_dir,
            {"change-1": _task_dict(state=task_state)},
        )

    def test_commit_sets_state_done_and_returns_commit(
        self, base_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """commit() pushes to base branch, sets task state to done, returns commit hash."""
        self._setup_work_worktree(base_dir)

        def side_effect(cmd: list[str], cwd: Path | None = None) -> str:
            if cmd[1:3] == ["status", "--porcelain"]:
                return ""  # no conflicts
            if cmd[1:3] == ["rev-parse", "--short"]:
                return "def5678"
            return ""

        monkeypatch.setattr(
            "otdev.tools.worktree._git", MagicMock(side_effect=side_effect)
        )

        from otdev.tools.worktree import commit

        result = commit(message="Fix login bug")

        assert result == {"commit": "def5678", "pushed": True}
        tasks_data = json.loads((base_dir / "tasks.json").read_text())
        assert tasks_data["tasks"]["change-1"]["state"] == "done"

    def test_commit_raises_on_conflict_markers_and_reverts_state(
        self, base_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """commit() raises RuntimeError on conflicts and reverts state to active."""
        self._setup_work_worktree(base_dir)

        def side_effect(cmd: list[str], cwd: Path | None = None) -> str:
            if cmd[1:3] == ["status", "--porcelain"]:
                return "UU conflicted_file.py"
            return ""

        monkeypatch.setattr(
            "otdev.tools.worktree._git", MagicMock(side_effect=side_effect)
        )

        from otdev.tools.worktree import commit

        with pytest.raises(RuntimeError, match="conflicts"):
            commit(message="This will conflict")

        tasks_data = json.loads((base_dir / "tasks.json").read_text())
        assert tasks_data["tasks"]["change-1"]["state"] == "active"


# ── Tests: remove() ───────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.tools
class TestRemove:
    def test_remove_removes_worktree_and_unregisters_task(
        self, base_dir: Path, mock_git: MagicMock
    ) -> None:
        """remove() removes worktree, branch, and task from tasks.json."""
        ws_dir = str(base_dir / "worktrees" / "change-1")
        _make_tasks_json(
            base_dir,
            {"change-1": _task_dict(workspace_dir=ws_dir, state="done", num=1)},
        )

        from otdev.tools.worktree import remove

        result = remove(id=1)

        assert result["removed"] is True
        assert result["task_id"] == "change-1"
        assert result["warnings"] == []
        tasks_data = json.loads((base_dir / "tasks.json").read_text())
        assert "change-1" not in tasks_data["tasks"]

    def test_remove_warns_on_active_task(
        self, base_dir: Path, mock_git: MagicMock
    ) -> None:
        """remove() warns when removing a task that is not done."""
        ws_dir = str(base_dir / "worktrees" / "change-1")
        _make_tasks_json(
            base_dir,
            {"change-1": _task_dict(workspace_dir=ws_dir, state="active", num=1)},
        )

        from otdev.tools.worktree import remove

        result = remove(id="change-1")

        assert result["removed"] is True
        assert len(result["warnings"]) > 0
        assert "active" in result["warnings"][0]

    def test_remove_raises_on_unknown_task(
        self, base_dir: Path, mock_git: MagicMock
    ) -> None:
        """remove() raises KeyError for an unknown task ID."""
        _make_tasks_json(base_dir, {})

        from otdev.tools.worktree import remove

        with pytest.raises(KeyError):
            remove(id="unknown-task")


# ── Tests: mark() ─────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.tools
class TestMark:
    def test_mark_updates_state_in_tasks_json(
        self, base_dir: Path, mock_git: MagicMock
    ) -> None:
        """mark() updates state in tasks.json and returns task_id + state."""
        _make_tasks_json(
            base_dir,
            {"change-1": _task_dict(state="active", num=1)},
        )

        from otdev.tools.worktree import mark

        result = mark(id="change-1", state="done")

        assert result == {"task_id": "change-1", "state": "done"}
        tasks_data = json.loads((base_dir / "tasks.json").read_text())
        assert tasks_data["tasks"]["change-1"]["state"] == "done"


# ── Tests: clean() ────────────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.tools
class TestClean:
    def test_clean_removes_all_tasks_and_gitignore_entries(
        self, base_dir: Path, mock_git: MagicMock
    ) -> None:
        """clean() removes all tasks, tasks.json, and gitignore entries."""
        (base_dir / ".gitignore").write_text("tasks.json\ntasks.json.lock\n")
        ws_dir = str(base_dir / "worktrees" / "task-1")
        _make_tasks_json(
            base_dir,
            {"task-1": _task_dict(workspace_dir=ws_dir, state="done", num=1)},
        )

        from otdev.tools.worktree import clean

        result = clean()

        assert "task-1" in result["removed"]
        assert result["warnings"] == []
        assert not (base_dir / "tasks.json").exists()
        gitignore = (base_dir / ".gitignore").read_text()
        assert "tasks.json" not in gitignore

    def test_clean_returns_warnings_for_active_tasks(
        self, base_dir: Path, mock_git: MagicMock
    ) -> None:
        """clean() includes active task IDs in warnings but still proceeds."""
        ws_dir = str(base_dir / "worktrees" / "active-task")
        _make_tasks_json(
            base_dir,
            {"active-task": _task_dict(workspace_dir=ws_dir, state="active", num=1)},
        )

        from otdev.tools.worktree import clean

        result = clean()

        assert "active-task" in result["removed"]
        assert len(result["warnings"]) > 0
        assert "active-task" in result["warnings"][0]


# ── Tests: _resolve_task() ────────────────────────────────────────────────────


@pytest.mark.unit
@pytest.mark.tools
class TestResolveTask:
    def test_resolves_by_1_based_num(self, base_dir: Path) -> None:
        """_resolve_task("1") resolves to the task with num=1."""
        _make_tasks_json(base_dir, {"change-1": _task_dict(num=1)})

        from otdev.tools.worktree import _resolve_task

        result = _resolve_task("1")

        assert result is not None
        task_id, task = result
        assert task_id == "change-1"
        assert task.num == 1

    def test_resolves_by_exact_id(self, base_dir: Path) -> None:
        """_resolve_task("change-1") resolves by exact case-insensitive match."""
        _make_tasks_json(base_dir, {"change-1": _task_dict(num=1)})

        from otdev.tools.worktree import _resolve_task

        result = _resolve_task("CHANGE-1")

        assert result is not None
        task_id, _ = result
        assert task_id == "change-1"

    def test_resolves_by_fuzzy_id(self, base_dir: Path) -> None:
        """_resolve_task strips dashes/underscores/spaces for fuzzy matching."""
        _make_tasks_json(base_dir, {"change-1": _task_dict(num=1)})

        from otdev.tools.worktree import _resolve_task

        result = _resolve_task("CHANGE1")

        assert result is not None
        task_id, _ = result
        assert task_id == "change-1"

    def test_returns_none_for_unknown(self, base_dir: Path) -> None:
        """_resolve_task returns None when no matching task is found."""
        _make_tasks_json(base_dir, {"change-1": _task_dict(num=1)})

        from otdev.tools.worktree import _resolve_task

        result = _resolve_task("totally-unknown-xyz")

        assert result is None
