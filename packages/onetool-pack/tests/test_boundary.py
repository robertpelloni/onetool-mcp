"""Test that the otpack import boundary is clean."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parent.parent / "scripts" / "check_otpack_boundary.py"


@pytest.mark.unit
@pytest.mark.pkg
def test_boundary_check_passes() -> None:
    """check_otpack_boundary.py must exit 0 (no violations)."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"Boundary check failed:\n{result.stdout}\n{result.stderr}"
    )
