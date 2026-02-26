"""Tests for ot.tools inter-tool calling API."""

from __future__ import annotations

import pytest
from ot.meta import _truncate


@pytest.mark.unit
@pytest.mark.core
class TestCallTool:
    """Tests for call_tool function."""

    def test_call_tool_requires_dot_notation(self) -> None:
        """Should raise ValueError for names without pack prefix."""
        from ot.tools import call_tool

        with pytest.raises(ValueError, match="must include pack prefix"):
            call_tool("search", query="test")

    def test_call_tool_unknown_pack(self) -> None:
        """Should raise KeyError for unknown pack name."""
        from ot.tools import call_tool

        with pytest.raises(KeyError, match="Pack .* not found"):
            call_tool("nonexistent_pack.function", arg="value")

    def test_call_tool_unknown_function(self) -> None:
        """Should raise KeyError for unknown function in valid pack."""
        from ot.tools import call_tool

        # 'ot' pack is always registered, so use it
        with pytest.raises(KeyError, match="Function .* not found"):
            call_tool("ot.nonexistent_function", arg="value")

    def test_call_tool_valid(self) -> None:
        """Should successfully call a valid tool."""
        from ot.tools import call_tool

        # Call ot.help() which should always be available
        result = call_tool("ot.help")
        assert result is not None
        assert isinstance(result, str)


@pytest.mark.unit
@pytest.mark.core
class TestGetPack:
    """Tests for get_pack function."""

    def test_get_pack_unknown(self) -> None:
        """Should raise KeyError for unknown pack name."""
        from ot.tools import get_pack

        with pytest.raises(KeyError, match="Pack .* not found"):
            get_pack("nonexistent_pack")

    def test_get_pack_valid(self) -> None:
        """Should return pack proxy for valid pack."""
        from ot.tools import get_pack

        # 'ot' pack is always registered
        ot_pack = get_pack("ot")
        assert ot_pack is not None
        assert hasattr(ot_pack, "help")

    def test_get_pack_allows_function_calls(self) -> None:
        """Should return pack that allows function calls."""
        from ot.tools import get_pack

        ot_pack = get_pack("ot")
        result = ot_pack.help()
        assert result is not None
        assert isinstance(result, str)


@pytest.mark.unit
@pytest.mark.core
class TestTruncate:
    """Tests for _truncate helper."""

    def test_short_string_unchanged(self) -> None:
        assert _truncate("hello", 100) == "hello"

    def test_exact_length_unchanged(self) -> None:
        s = "x" * 100
        assert _truncate(s, 100) == s

    def test_long_string_truncated(self) -> None:
        s = "x" * 150
        result = _truncate(s, 100)
        assert result == "x" * 100 + "…"
        assert len(result) == 101

    def test_default_limit_is_100(self) -> None:
        s = "a" * 101
        result = _truncate(s)
        assert result.endswith("…")
        assert len(result) == 101


@pytest.mark.unit
@pytest.mark.core
class TestOtToolsDefault:
    """Tests for ot.tools() default info level and description truncation."""

    def test_default_info_is_default(self) -> None:
        """ot.tools() defaults to info='default', returning dicts with name+description."""
        from ot.meta import tools

        result = tools()
        assert len(result) > 0
        assert all(isinstance(item, dict) for item in result)
        assert all("name" in item and "description" in item for item in result)

    def test_info_min_returns_strings(self) -> None:
        """ot.tools(info='min') returns names only as strings."""
        from ot.meta import tools

        result = tools(info="min")
        assert len(result) > 0
        assert all(isinstance(item, str) for item in result)

    def test_info_default_truncates_long_descriptions(self) -> None:
        """ot.tools(info='default') truncates descriptions to 200 chars."""
        from ot.meta import tools

        result = tools(info="default")
        for item in result:
            assert isinstance(item, dict)
            desc = item["description"]
            assert len(desc) <= 201, f"Description too long for {item['name']}: {len(desc)}"
