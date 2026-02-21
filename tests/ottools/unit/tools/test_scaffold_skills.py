"""Unit tests for scaffold.skills() — skill stub installation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


@pytest.fixture
def fake_env(tmp_path: Path):
    """Set up a fake environment with skills.md, skills dir, and mock config."""
    # Create a fake skills dir
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "my-skill.md").write_text(
        "---\nname: my-skill\ndescription: My test skill\n---\n\nBody."
    )
    (skills_dir / "other-skill.md").write_text(
        "---\nname: other-skill\ndescription: Another skill\n---\n\nOther body."
    )

    # Create a fake skills.md
    tools_yaml = tmp_path / "skills.md"
    tools_yaml.write_text(
        yaml.dump({
            "tools": {
                "claude": {"stub_path": ".claude/skills/{name}/SKILL.md"},
                "codex": {"stub_path": ".codex/skills/{name}/SKILL.md"},
                "opencode": {"stub_path": ".opencode/skills/{name}/SKILL.md"},
            }
        })
    )

    # Create a fake stub template (unified frontmatter for all tools)
    stub_tmpl = tmp_path / "skill_stub.md.j2"
    stub_tmpl.write_text(
        "---\nname: {{ name }}\ndescription: {{ description }}\n---\n\n`>>> ot.skills(name=\"{{ name }}\")`\n"
    )

    # Create project dir (where relative paths resolve from)
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    return {
        "tmp": tmp_path,
        "skills_dir": skills_dir,
        "tools_yaml": tools_yaml,
        "stub_tmpl": stub_tmpl,
        "project_dir": project_dir,
    }


def _patch_env(env: dict):
    """Create a context manager that patches key functions."""
    from contextlib import ExitStack

    def patcher():
        stack = ExitStack()
        stack.enter_context(
            patch("ottools.scaffold._get_tools_config", return_value={
                "claude": {"stub_path": ".claude/skills/{name}/SKILL.md"},
                "codex": {"stub_path": ".codex/skills/{name}/SKILL.md"},
                "opencode": {"stub_path": ".opencode/skills/{name}/SKILL.md"},
            })
        )
        stack.enter_context(
            patch("ottools.scaffold._list_bundled_skills", return_value=["my-skill", "other-skill"])
        )
        stack.enter_context(
            patch("ottools.scaffold._get_skill_description", side_effect=lambda n: f"Desc for {n}")
        )
        stack.enter_context(
            patch("ottools.scaffold._get_skill_stub_template",
                  return_value="---\nname: {{ name }}\ndescription: {{ description }}\n---\n\n`>>> ot.skills(name=\"{{ name }}\")`\n")
        )
        mock_cfg = MagicMock()
        mock_cfg._config_dir = str(env["project_dir"] / ".onetool")
        stack.enter_context(
            patch("ottools.scaffold.get_config", return_value=mock_cfg)
        )
        return stack

    return patcher()


# =============================================================================
# List Skills Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_scaffold_skills_list(fake_env: dict) -> None:
    """scaffold.skills() with no args lists available stubs."""
    from ottools.scaffold import skills

    with _patch_env(fake_env):
        result = skills()

    assert "my-skill" in result
    assert "other-skill" in result
    assert "scaffold.skills(install=" in result


# =============================================================================
# Install Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_scaffold_skills_install_claude(fake_env: dict, tmp_path: Path) -> None:
    """scaffold.skills(install=...) installs stub for Claude Code."""
    from ottools.scaffold import skills

    with _patch_env(fake_env):
        result = skills(install="my-skill", tool="claude")

    assert "installed" in result or "updated" in result
    stub_file = fake_env["project_dir"] / ".claude" / "skills" / "my-skill" / "SKILL.md"
    assert stub_file.exists(), f"Stub file not created at {stub_file}"
    content = stub_file.read_text()
    assert "my-skill" in content


@pytest.mark.unit
@pytest.mark.tools
def test_scaffold_skills_install_codex(fake_env: dict) -> None:
    """scaffold.skills(install=..., tool='codex') installs stub for Codex."""
    from ottools.scaffold import skills

    with _patch_env(fake_env):
        result = skills(install="my-skill", tool="codex")

    assert "installed" in result or "updated" in result
    stub_file = fake_env["project_dir"] / ".codex" / "skills" / "my-skill" / "SKILL.md"
    assert stub_file.exists(), f"Codex stub not created at {stub_file}"


@pytest.mark.unit
@pytest.mark.tools
def test_scaffold_skills_install_all(fake_env: dict) -> None:
    """scaffold.skills(install='all') installs stubs for all bundled skills."""
    from ottools.scaffold import skills

    with _patch_env(fake_env):
        result = skills(install="all", tool="claude")

    assert "my-skill" in result
    assert "other-skill" in result
    project = fake_env["project_dir"]
    assert (project / ".claude" / "skills" / "my-skill" / "SKILL.md").exists()
    assert (project / ".claude" / "skills" / "other-skill" / "SKILL.md").exists()


@pytest.mark.unit
@pytest.mark.tools
def test_scaffold_skills_install_overwrites(fake_env: dict) -> None:
    """Installing an already-existing stub reports 'updated'."""
    from ottools.scaffold import skills

    with _patch_env(fake_env):
        # Install first time
        skills(install="my-skill", tool="claude")
        # Install again
        result = skills(install="my-skill", tool="claude")

    assert "updated" in result


@pytest.mark.unit
@pytest.mark.tools
def test_scaffold_skills_unknown_skill(fake_env: dict) -> None:
    """scaffold.skills(install='unknown') returns error listing available skills."""
    from ottools.scaffold import skills

    with _patch_env(fake_env):
        result = skills(install="nonexistent-skill")

    assert "Error" in result or "Unknown" in result
    assert "my-skill" in result


@pytest.mark.unit
@pytest.mark.tools
def test_scaffold_skills_unsupported_tool(fake_env: dict) -> None:
    """scaffold.skills(install=..., tool='unknown-tool') returns error."""
    from ottools.scaffold import skills

    with _patch_env(fake_env):
        result = skills(install="my-skill", tool="unknown-tool")

    assert "Error" in result or "Unsupported" in result
    assert "claude" in result


# =============================================================================
# skills.md Config Tests
# =============================================================================


@pytest.mark.unit
@pytest.mark.tools
def test_get_tools_config_loads_yaml() -> None:
    """_get_tools_config() reads skills.md from global_templates."""
    from ottools.scaffold import _get_tools_config

    config = _get_tools_config()

    assert "claude" in config
    assert "codex" in config
    assert "opencode" in config
    assert "stub_path" in config["claude"]
    assert "{name}" in config["claude"]["stub_path"]
