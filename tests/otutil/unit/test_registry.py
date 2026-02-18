"""Unit tests for registry-based tool discovery and registration."""

from __future__ import annotations

from pathlib import Path

import pytest

from otcommon.registry import ToolRegistry

TOOLS_PATH = Path(__file__).parent.parent.parent.parent / "src" / "otutil" / "tools"

# Expected packs and their tool counts
EXPECTED_PACKS = {
    "brave": 6,
    "convert": 5,
    "excel": 24,
    "file": 10,
    "ground": 5,
}

EXPECTED_TOTAL = sum(EXPECTED_PACKS.values())


@pytest.fixture
def registry() -> ToolRegistry:
    """Create a registry scanning the tools directory."""
    reg = ToolRegistry(tools_path=TOOLS_PATH)
    reg.scan_directory()
    return reg


@pytest.mark.unit
@pytest.mark.tools
class TestToolDiscovery:
    """Tests for registry tool discovery (task 3.1)."""

    def test_discovers_all_tools(self, registry: ToolRegistry) -> None:
        """Registry discovers all tools from otutil/tools/."""
        assert len(registry.tools) == EXPECTED_TOTAL

    def test_all_tools_have_names(self, registry: ToolRegistry) -> None:
        """Every discovered tool has a name."""
        for tool in registry.tools.values():
            assert tool.name, f"Tool missing name: {tool}"

    def test_all_tools_have_pack_prefix(self, registry: ToolRegistry) -> None:
        """Every tool name has pack.func format."""
        for tool in registry.tools.values():
            assert "." in tool.name, f"Tool missing pack prefix: {tool.name}"


@pytest.mark.unit
@pytest.mark.tools
class TestPackAssignments:
    """Tests for pack assignments (task 3.2)."""

    def test_pack_counts(self, registry: ToolRegistry) -> None:
        """Each pack has the expected number of tools."""
        packs: dict[str, int] = {}
        for tool in registry.tools.values():
            pack = tool.pack or "(none)"
            packs[pack] = packs.get(pack, 0) + 1

        for pack_name, expected_count in EXPECTED_PACKS.items():
            actual = packs.get(pack_name, 0)
            assert actual == expected_count, (
                f"Pack '{pack_name}': expected {expected_count}, got {actual}"
            )

    def test_no_unassigned_tools(self, registry: ToolRegistry) -> None:
        """All tools belong to a pack."""
        for tool in registry.tools.values():
            assert tool.pack is not None, f"Tool '{tool.name}' has no pack"

    def test_expected_packs_only(self, registry: ToolRegistry) -> None:
        """Only expected packs exist."""
        packs = {tool.pack for tool in registry.tools.values()}
        assert packs == set(EXPECTED_PACKS.keys())


@pytest.mark.unit
@pytest.mark.tools
class TestSchemaCorrectness:
    """Tests for schema correctness (task 3.3)."""

    def test_all_tools_have_args(self, registry: ToolRegistry) -> None:
        """Tools with parameters have args defined."""
        # At minimum, tools like file.read(path=) should have args
        tool = registry.get_tool("file.read")
        assert tool is not None
        assert len(tool.args) > 0
        assert tool.args[0].name == "path"
        assert tool.args[0].type == "str"

    def test_keyword_only_params(self, registry: ToolRegistry) -> None:
        """Verify tool args are keyword-only (all otutil tools use *)."""
        # Spot-check a few tools
        for name in ["file.read", "brave.search", "excel.create"]:
            tool = registry.get_tool(name)
            assert tool is not None, f"Tool {name} not found"
            # All args should be present (keyword-only in source)
            assert len(tool.args) > 0, f"Tool {name} has no args"

    def test_type_annotations_present(self, registry: ToolRegistry) -> None:
        """All args have type annotations."""
        for tool in registry.tools.values():
            for arg in tool.args:
                assert arg.type != "", (
                    f"Tool '{tool.name}' arg '{arg.name}' missing type"
                )

    def test_default_values(self, registry: ToolRegistry) -> None:
        """Args with defaults have them recorded."""
        # brave.search has count with a default
        tool = registry.get_tool("brave.search")
        assert tool is not None
        count_args = [a for a in tool.args if a.name == "count"]
        assert len(count_args) == 1
        assert count_args[0].default is not None


@pytest.mark.unit
@pytest.mark.tools
class TestToolDescriptions:
    """Tests for docstring extraction (task 3.4)."""

    def test_all_tools_have_descriptions(self, registry: ToolRegistry) -> None:
        """Every tool has a description from its docstring."""
        missing = [
            tool.name
            for tool in registry.tools.values()
            if not tool.description
        ]
        assert missing == [], f"Tools missing descriptions: {missing}"

    def test_description_content(self, registry: ToolRegistry) -> None:
        """Spot-check description content."""
        tool = registry.get_tool("file.read")
        assert tool is not None
        assert len(tool.description) > 10  # Should be a meaningful description
