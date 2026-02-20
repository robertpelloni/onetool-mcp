"""Pytest configuration and fixtures for onetool-util tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def test_file(tmp_path: Path) -> Path:
    """Create a temporary test file.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to test file with sample content
    """
    test_file = tmp_path / "test.txt"
    test_file.write_text("Hello, World!\nLine 2\nLine 3")
    return test_file
