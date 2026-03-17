"""Pytest configuration with dual-marker enforcement.

Every test must have:
1. A speed tier marker (smoke, unit, integration)
2. A component marker (pkg)

Tests missing required markers are automatically skipped.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from _pytest.nodes import Item

SPEED_MARKERS = {"smoke", "unit", "integration"}
COMPONENT_MARKERS = {"pkg"}


def pytest_collection_modifyitems(items: list[Item]) -> None:
    """Skip tests that are missing required markers."""
    for item in items:
        markers = {m.name for m in item.iter_markers()}

        if not markers & SPEED_MARKERS:
            warnings.warn(
                f"Test {item.nodeid} is missing a speed marker "
                f"(one of: {', '.join(sorted(SPEED_MARKERS))})",
                stacklevel=1,
            )
            item.add_marker(pytest.mark.skip(reason="Missing speed marker"))

        if not markers & COMPONENT_MARKERS:
            warnings.warn(
                f"Test {item.nodeid} is missing a component marker "
                f"(one of: {', '.join(sorted(COMPONENT_MARKERS))})",
                stacklevel=1,
            )
            item.add_marker(pytest.mark.skip(reason="Missing component marker"))
