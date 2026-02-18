"""Test fixtures for onetool-dev."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_config() -> dict:
    """Create a sample config for testing.

    Returns:
        Sample configuration dictionary
    """
    return {
        "version": 1,
        "log_level": "INFO",
    }
