"""Tests for ot.agent_hints() function."""

from __future__ import annotations

import pytest

from ot.meta import agent_hints


@pytest.mark.smoke
@pytest.mark.unit
@pytest.mark.core
def test_agent_hints_returns_markdown():
    """Test agent_hints() returns non-empty markdown content."""
    result = agent_hints()

    assert isinstance(result, str)
    assert len(result) > 100
    assert "# OneTool Agent Hints" in result


@pytest.mark.unit
@pytest.mark.core
def test_agent_hints_contains_examples():
    """Test agent_hints() includes copy-pasteable examples."""
    result = agent_hints()

    # Should contain keyword-only arg examples
    assert "query=" in result
    assert "path=" in result

    # Should not contain snippet references
    assert "$b_q" not in result
    assert "$g " not in result
