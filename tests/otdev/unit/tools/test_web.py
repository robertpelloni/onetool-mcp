"""Unit tests for web tool pack."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.tools
class TestWebPack:
    """Test web pack structure."""

    def test_pack_name(self):
        from otdev.tools import web

        assert web.pack == "web"

    def test_has_all_exports(self):
        from otdev.tools import web

        # Web should export fetch and extract functions
        assert hasattr(web, "__all__")
        assert "fetch" in web.__all__
        assert len(web.__all__) >= 1

    def test_functions_are_callable(self):
        from otdev.tools import web

        for name in web.__all__:
            func = getattr(web, name)
            assert callable(func), f"{name} should be callable"
