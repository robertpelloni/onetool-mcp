"""Smoke tests for onetool-util - verify basic functionality."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.pkg


@pytest.mark.smoke
def test_import_package() -> None:
    """Test that the package can be imported."""
    import otutil

    assert otutil.__version__ == "1.0.0"
    assert otutil.__package_name__ == "onetool-util"


@pytest.mark.smoke
def test_import_tool_modules() -> None:
    """Test that all tool modules can be imported."""
    from otutil.tools import brave, convert, excel, file, ground

    # Check pack names
    assert file.pack == "file"
    assert excel.pack == "excel"
    assert convert.pack == "convert"
    assert brave.pack == "brave"
    assert ground.pack == "ground"
