"""Pytest configuration and fixtures for onetool-util tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_config(tmp_path: Path) -> Path:
    """Create a temporary config file for testing.

    Args:
        tmp_path: Pytest temporary directory fixture

    Returns:
        Path to temporary config file
    """
    config_path = tmp_path / "util.yaml"
    config_content = """
version: 1
log_level: DEBUG

file:
  allowed_dirs: ["."]
  max_file_size: 1000000
  backup_on_write: false

excel:
  max_file_size: 10000000

convert:
  default_format: markdown

brave:
  timeout: 30

ground:
  model: gemini-2.5-flash
"""
    config_path.write_text(config_content)
    return config_path


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
