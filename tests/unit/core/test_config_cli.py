"""Unit tests for direct config schema (DirectConfig)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


@pytest.mark.unit
@pytest.mark.core
class TestDirectConfig:
    def test_defaults_without_direct_section(self) -> None:
        from ot.config.models import OneToolConfig

        cfg = OneToolConfig()
        assert cfg.direct.host is None
        assert cfg.direct.port == 8765
        assert cfg.direct.timeout == 60

    def test_defaults_load_from_yaml_without_direct(self, write_config: Callable) -> None:
        from ot.config.loader import load_config

        p = write_config({"version": 2})
        cfg = load_config(p)

        assert cfg.direct.host is None
        assert cfg.direct.port == 8765
        assert cfg.direct.timeout == 60

    def test_direct_section_overrides_port(self, write_config: Callable) -> None:
        from ot.config.loader import load_config

        p = write_config({"version": 2, "direct": {"port": 9000}})
        cfg = load_config(p)

        assert cfg.direct.port == 9000
        assert cfg.direct.host is None

    def test_direct_section_host_enable(self, write_config: Callable) -> None:
        from ot.config.loader import load_config

        p = write_config({"version": 2, "direct": {"host": "enable"}})
        cfg = load_config(p)

        assert cfg.direct.host == "enable"
        assert cfg.direct.port == 8765

    def test_direct_section_host_remote(self, write_config: Callable) -> None:
        from ot.config.loader import load_config

        p = write_config({"version": 2, "direct": {"host": "myhost:9001"}})
        cfg = load_config(p)

        assert cfg.direct.host == "myhost:9001"

    def test_direct_section_overrides_timeout(self, write_config: Callable) -> None:
        from ot.config.loader import load_config

        p = write_config({"version": 2, "direct": {"timeout": 120}})
        cfg = load_config(p)

        assert cfg.direct.timeout == 120
        assert cfg.direct.host is None
        assert cfg.direct.port == 8765

    def test_direct_has_no_background_field(self) -> None:
        from ot.config.models import DirectConfig

        cfg = DirectConfig()
        assert not hasattr(cfg, "background")

    def test_direct_host_invalid_bare_hostname_raises(self) -> None:
        """host must be null, 'enable', or 'HOST:PORT' — bare hostname should be rejected."""
        from pydantic import ValidationError

        from ot.config.models import DirectConfig

        with pytest.raises(ValidationError):
            DirectConfig(host="myhost")

    def test_direct_host_valid_values_accepted(self) -> None:
        from ot.config.models import DirectConfig

        assert DirectConfig(host=None).host is None
        assert DirectConfig(host="enable").host == "enable"
        assert DirectConfig(host="myhost:9001").host == "myhost:9001"
