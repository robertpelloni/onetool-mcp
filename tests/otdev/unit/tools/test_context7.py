"""Unit tests for context7 tool pack."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.tools
class TestContext7Pack:
    """Test context7 pack structure."""

    def test_pack_name(self):
        from otdev.tools import context7

        assert context7.pack == "context7"

    def test_has_all_exports(self):
        from otdev.tools import context7

        # Context7 should export search and doc functions
        assert hasattr(context7, "__all__")
        expected = {"search", "doc"}
        assert expected.issubset(set(context7.__all__))

    def test_functions_are_callable(self):
        from otdev.tools import context7

        for name in context7.__all__:
            func = getattr(context7, name)
            assert callable(func), f"{name} should be callable"
