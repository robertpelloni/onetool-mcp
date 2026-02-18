"""Unit tests for package tool pack."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.tools
class TestPackagePack:
    """Test package pack structure."""

    def test_pack_name(self):
        from otdev.tools import package

        assert package.pack == "package"

    def test_has_all_exports(self):
        from otdev.tools import package

        # Package should export npm, pypi, models, and other functions
        assert hasattr(package, "__all__")
        expected = {"npm", "pypi", "models"}
        assert expected.issubset(set(package.__all__))

    def test_functions_are_callable(self):
        from otdev.tools import package

        for name in package.__all__:
            func = getattr(package, name)
            assert callable(func), f"{name} should be callable"
