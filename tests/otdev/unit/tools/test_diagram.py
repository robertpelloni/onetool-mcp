"""Unit tests for diagram tool pack."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.tools
class TestDiagramPack:
    """Test diagram pack structure."""

    def test_pack_name(self):
        from otdev.tools import diagram

        assert diagram.pack == "diagram"

    def test_has_all_exports(self):
        from otdev.tools import diagram

        # Diagram should export rendering functions
        assert hasattr(diagram, "__all__")
        # Check that key functions exist
        expected = {"render_diagram", "list_providers"}
        assert expected.issubset(set(diagram.__all__))

    def test_functions_are_callable(self):
        from otdev.tools import diagram

        for name in diagram.__all__:
            func = getattr(diagram, name)
            assert callable(func), f"{name} should be callable"
