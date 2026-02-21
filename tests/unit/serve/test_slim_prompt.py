"""Tests for slim MCP prompt mode."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.serve
def test_slim_mode_produces_short_prompt() -> None:
    """Slim mode produces at most 25 lines."""
    from ot.prompts import PromptsConfig

    slim_text = "Line 1\nLine 2\nLine 3\nDiscovery hint: `>>> ot.help()`"
    config = PromptsConfig(
        instructions="Full long prompt\n" * 50,
        instructions_slim=slim_text,
        slim=True,
    )

    # Simulate what _get_instructions() does
    if config.slim and config.instructions_slim:
        result = config.instructions_slim.strip()
    else:
        result = config.instructions.strip()

    assert len(result.splitlines()) <= 25


@pytest.mark.unit
@pytest.mark.serve
def test_full_mode_uses_instructions() -> None:
    """Full mode uses the full instructions field."""
    from ot.prompts import PromptsConfig

    full_text = "Full prompt content\n" * 10
    config = PromptsConfig(
        instructions=full_text,
        instructions_slim="Slim text",
        slim=False,
    )

    if config.slim and config.instructions_slim:
        result = config.instructions_slim.strip()
    else:
        result = config.instructions.strip()

    assert "Full prompt content" in result
    assert "Slim text" not in result


@pytest.mark.unit
@pytest.mark.serve
def test_slim_default_when_key_absent() -> None:
    """slim defaults to True when not set."""
    from ot.prompts import PromptsConfig

    config = PromptsConfig(instructions="Full prompt")
    assert config.slim is True


@pytest.mark.unit
@pytest.mark.serve
def test_template_prompts_slim_mode() -> None:
    """The global template prompts.yaml has slim=true and instructions_slim."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    assert prompts.slim is True
    assert prompts.instructions_slim is not None
    assert len(prompts.instructions_slim.strip().splitlines()) <= 25


@pytest.mark.unit
@pytest.mark.serve
def test_template_prompts_slim_has_required_elements() -> None:
    """Slim prompt contains identity, triggers, discovery hint, and boundary warning."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    slim = prompts.instructions_slim or ""

    assert ">>>" in slim, "Missing trigger in slim prompt"
    assert "ot.help()" in slim, "Missing discovery hint in slim prompt"
    assert "external-content" in slim or "boundary" in slim.lower(), (
        "Missing external content boundary warning in slim prompt"
    )


@pytest.mark.unit
@pytest.mark.serve
def test_template_prompts_full_mode_has_full_content() -> None:
    """Full instructions contain comprehensive reference material."""
    from ot.prompts import load_prompts

    prompts = load_prompts()
    full = prompts.instructions

    assert len(full.splitlines()) > 25, "Full prompt should be more than 25 lines"
    assert "ot.tools()" in full or "Discovery" in full


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
