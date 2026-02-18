"""Unit tests for server registry usage.

Tests that ToolRegistry correctly scans and registers tools from otdev.tools.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.tools
class TestServerRegistry:
    """Test ToolRegistry scanning of otdev.tools package."""

    def test_registry_scan_discovers_tools(self):
        """Test that registry.scan_directory discovers all expected tools."""
        from otcommon.registry import ToolRegistry

        registry = ToolRegistry()
        tools_dir = Path(__file__).parent.parent.parent.parent / "src" / "otdev" / "tools"
        registry.scan_directory(tools_dir)

        # Get all discovered tools (dict of name -> ToolInfo)
        tool_infos = registry.tools

        # Should have tools from all 6 packs
        assert len(tool_infos) > 20, f"Expected at least 20 tools, got {len(tool_infos)}"

        # Get tool names (keys of the dict)
        tool_names = list(tool_infos.keys())

        # Verify some key tools from each pack
        expected_tools = {
            "ripgrep": ["search", "count", "files", "types"],
            "web": ["fetch", "fetch_batch"],
            "package": ["npm", "pypi", "version", "models", "audit"],
            "context7": ["search", "doc"],
            "db": ["tables", "schema", "query"],
            "diagram": ["render_diagram", "batch_render", "generate_source"],
        }

        for pack, tools in expected_tools.items():
            for tool in tools:
                # Tools may be namespaced with pack prefix
                # Check if either the plain name or pack.name exists
                assert (
                    tool in tool_names or f"{pack}.{tool}" in tool_names
                ), f"Expected tool {tool} or {pack}.{tool} to be discovered"

    def test_registry_extracts_signatures(self):
        """Test that registry extracts correct signatures from tool functions."""
        from otcommon.registry import ToolRegistry

        registry = ToolRegistry()
        tools_dir = Path(__file__).parent.parent.parent.parent / "src" / "otdev" / "tools"
        registry.scan_directory(tools_dir)

        # Find a specific tool to check signature
        ripgrep_search = registry.tools.get("ripgrep.search")

        assert ripgrep_search is not None, "Should find ripgrep.search tool"

        # Check signature has expected parameters
        assert ripgrep_search.args is not None
        param_names = [p.name for p in ripgrep_search.args]

        # ripgrep.search should have these key parameters
        assert "pattern" in param_names, "ripgrep.search should have 'pattern' parameter"
        assert "path" in param_names, "ripgrep.search should have 'path' parameter"

        # Check pattern parameter is required (no default)
        pattern_param = next(p for p in ripgrep_search.args if p.name == "pattern")
        assert pattern_param.default is None, "pattern parameter should be required (no default)"

        # Check path parameter is optional (has default)
        path_param = next(p for p in ripgrep_search.args if p.name == "path")
        assert path_param.default is not None, "path parameter should be optional (has default)"

    def test_registry_extracts_docstrings(self):
        """Test that registry extracts docstrings as tool descriptions."""
        from otcommon.registry import ToolRegistry

        registry = ToolRegistry()
        tools_dir = Path(__file__).parent.parent.parent.parent / "src" / "otdev" / "tools"
        registry.scan_directory(tools_dir)

        # All tools should have descriptions (from docstrings)
        for tool_name, tool_info in registry.tools.items():
            assert tool_info.description, f"Tool {tool_name} should have description"
            assert len(tool_info.description) > 10, (
                f"Tool {tool_name} description too short: {tool_info.description}"
            )

    def test_registry_extracts_pack_names(self):
        """Test that registry extracts correct pack names from module paths."""
        from otcommon.registry import ToolRegistry

        registry = ToolRegistry()
        tools_dir = Path(__file__).parent.parent.parent.parent / "src" / "otdev" / "tools"
        registry.scan_directory(tools_dir)

        # Get all pack names
        pack_names = set(t.pack for t in registry.tools.values())

        # Should have 6 packs
        expected_packs = {"ripgrep", "web", "package", "context7", "db", "diagram"}
        assert expected_packs.issubset(pack_names), (
            f"Expected packs {expected_packs}, got {pack_names}"
        )

    def test_registry_handles_function_with_no_params(self):
        """Test that registry handles functions with no parameters correctly."""
        from otcommon.registry import ToolRegistry

        registry = ToolRegistry()
        tools_dir = Path(__file__).parent.parent.parent.parent / "src" / "otdev" / "tools"
        registry.scan_directory(tools_dir)

        # ripgrep.types() has no parameters
        types_tool = registry.tools.get("ripgrep.types")

        assert types_tool is not None, "Should find ripgrep.types tool"
        assert types_tool.args is not None
        assert len(types_tool.args) == 0, "types() should have no parameters"

    def test_registry_type_annotations(self):
        """Test that registry extracts type annotations correctly."""
        from otcommon.registry import ToolRegistry

        registry = ToolRegistry()
        tools_dir = Path(__file__).parent.parent.parent.parent / "src" / "otdev" / "tools"
        registry.scan_directory(tools_dir)

        # Find db.tables which has specific type annotations
        tables_tool = registry.tools.get("db.tables")

        assert tables_tool is not None, "Should find db.tables tool"

        # Check parameter types
        param_dict = {p.name: p for p in tables_tool.args}

        # db_url should be str type (required)
        assert "db_url" in param_dict
        assert param_dict["db_url"].type == "str"
        assert param_dict["db_url"].default is None, "db_url should be required"

        # filter should be str | None (optional)
        assert "filter" in param_dict
        # Type could be "str | None" or "Optional[str]" depending on parser
        assert param_dict["filter"].type in ("str | None", "Optional[str]", "str")
        assert param_dict["filter"].default is not None, "filter should be optional"
