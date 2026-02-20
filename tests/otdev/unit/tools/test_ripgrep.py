"""Unit tests for ripgrep tool pack."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.tools
class TestRipgrepPack:
    """Test ripgrep pack structure."""

    def test_pack_name(self):
        from otdev.tools import ripgrep

        assert ripgrep.pack == "ripgrep"

    def test_has_all_exports(self):
        from otdev.tools import ripgrep

        # Ripgrep should export search, count, files, types
        assert hasattr(ripgrep, "__all__")
        expected = {"search", "count", "files", "types"}
        assert set(ripgrep.__all__) == expected

    def test_functions_are_callable(self):
        from otdev.tools import ripgrep

        for name in ripgrep.__all__:
            func = getattr(ripgrep, name)
            assert callable(func), f"{name} should be callable"
