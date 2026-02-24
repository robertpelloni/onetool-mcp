"""Tests for MCP server instructions prompt."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.serve
def test_instructions_is_short() -> None:
    """instructions prompt is at most 25 lines."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    assert len(prompts.instructions.strip().splitlines()) <= 25


@pytest.mark.unit
@pytest.mark.serve
def test_instructions_has_required_elements() -> None:
    """instructions contains trigger, discovery hint, and boundary warning."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    text = prompts.instructions

    assert ">>>" in text, "Missing trigger in instructions"
    assert "ot.help()" in text, "Missing discovery hint in instructions"
    assert "external-content" in text or "boundary" in text.lower(), (
        "Missing external content boundary warning in instructions"
    )


@pytest.mark.unit
@pytest.mark.serve
def test_prompts_config_no_slim_fields() -> None:
    """PromptsConfig no longer has slim or instructions_slim fields."""
    from ot.prompts import PromptsConfig

    config = PromptsConfig(instructions="Hello")
    assert not hasattr(config, "slim")
    assert not hasattr(config, "instructions_slim")


@pytest.mark.unit
@pytest.mark.serve
def test_servers_yaml_has_no_instructions_field() -> None:
    """servers.yaml template has no 'instructions:' fields (moved to skills)."""
    from ot.paths import get_global_templates_dir

    servers_yaml = get_global_templates_dir() / "servers.yaml"
    content = servers_yaml.read_text()

    import yaml

    data = yaml.safe_load(content) or {}
    servers = data.get("servers", {})

    for name, cfg in servers.items():
        if isinstance(cfg, dict):
            assert "instructions" not in cfg, (
                f"Server '{name}' still has instructions: field in servers.yaml"
            )
