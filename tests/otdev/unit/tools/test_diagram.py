"""Unit tests for diagram tool pack."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.tools
class TestOutputDir:
    """Test _resolve_output_dir does not create directories eagerly."""

    def test_does_not_create_directory(self, tmp_path):
        from otdev.tools.diagram import _resolve_output_dir

        target = tmp_path / "new_diagrams"
        assert not target.exists()

        _resolve_output_dir(str(target))

        assert not target.exists(), "_resolve_output_dir should not mkdir"

    def test_returns_resolved_path(self, tmp_path):
        from otdev.tools.diagram import _resolve_output_dir

        target = tmp_path / "output"
        result = _resolve_output_dir(str(target))
        assert result == target.resolve()


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
