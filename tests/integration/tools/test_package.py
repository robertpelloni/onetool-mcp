"""Live integration tests for package version tool.

Tests npm, PyPI, and OpenRouter models API endpoints.
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
@pytest.mark.network
@pytest.mark.tools
class TestPackageLive:
    """Live integration tests for package version tool."""

    def test_npm_live(self):
        """Verify npm registry integration works."""
        from otdev.tools.package import npm

        result = npm(packages=["lodash"])

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "lodash"
        assert result[0]["latest"] != "unknown"

    def test_pypi_live(self):
        """Verify PyPI integration works."""
        from otdev.tools.package import pypi

        result = pypi(packages=["requests"])

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "requests"
        assert result[0]["latest"] != "unknown"

    def test_audit_pypi_live(self, tmp_path):
        """Verify audit function works with real PyPI registry."""
        from otdev.tools.package import audit

        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            "[project]\ndependencies = [\n    \"requests>=2.28.0\",\n]\n"
        )

        result = audit(path=str(tmp_path))

        assert "error" not in result, f"Got error: {result.get('error')}"
        assert result["registry"] == "pypi"
        assert len(result["packages"]) == 1
        assert result["packages"][0]["latest"] != "unknown"
