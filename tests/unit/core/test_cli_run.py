"""Unit tests for onetool direct run: format injection, command resolution, tcp probe."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestCommandWithMeta:
    """Tests for _build_command_with_meta (format + sanitize injection)."""

    def _meta(self, command: str, fmt: str, sanitize: bool) -> str:
        from onetool.cli_commands.direct_app import _build_command_with_meta
        return _build_command_with_meta(command, fmt, sanitize)

    def test_injects_format_json_h(self) -> None:
        result = self._meta("ot.debug()", "json_h", False)
        assert "__format__ = 'json_h'" in result
        assert "ot.debug()" in result

    def test_injects_sanitize_false(self) -> None:
        result = self._meta("ot.debug()", "json_h", False)
        assert "__sanitize__ = False" in result

    def test_injects_sanitize_true(self) -> None:
        result = self._meta("ot.debug()", "json", True)
        assert "__sanitize__ = True" in result

    def test_original_command_preserved(self) -> None:
        cmd = "brave.search(query='test')"
        result = self._meta(cmd, "raw", False)
        assert cmd in result

    def test_prefix_comes_before_command(self) -> None:
        result = self._meta("ot.debug()", "raw", False)
        prefix_end = result.index("\n")
        assert "ot.debug()" in result[prefix_end:]


@pytest.mark.unit
@pytest.mark.core
class TestResolveCommandSource:
    """Tests for _resolve_command_source."""

    def test_none_returns_none(self) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source
        assert _resolve_command_source(None) is None

    def test_regular_string_returned_as_is(self) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source
        assert _resolve_command_source("ot.debug()") == "ot.debug()"

    def test_py_file_existing_returns_contents(self, tmp_path: Path) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source
        script = tmp_path / "test.py"
        script.write_text("ot.debug()")
        result = _resolve_command_source(str(script))
        assert result == "ot.debug()"

    def test_py_file_nonexistent_returns_as_is(self) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source
        result = _resolve_command_source("/does/not/exist/script.py")
        assert result == "/does/not/exist/script.py"

    def test_py_file_empty_returns_none(self, tmp_path: Path) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source
        script = tmp_path / "empty.py"
        script.write_text("   ")
        result = _resolve_command_source(str(script))
        assert result is None

    def test_non_py_extension_not_treated_as_file(self, tmp_path: Path) -> None:
        from onetool.cli_commands.direct_app import _resolve_command_source
        # A .txt file with .py-like content should be returned as-is (not read)
        txt = tmp_path / "cmd.txt"
        txt.write_text("ot.debug()")
        result = _resolve_command_source(str(txt))
        assert result == str(txt)


@pytest.mark.unit
@pytest.mark.core
class TestTcpProbe:
    """Tests for _tcp_probe helper."""

    def test_probe_unreachable_port(self) -> None:
        from onetool.cli_commands.direct_app import _tcp_probe
        assert _tcp_probe("127.0.0.1", 1, timeout=0.05) is False

    def test_probe_timeout_returns_false(self) -> None:
        from onetool.cli_commands.direct_app import _tcp_probe
        assert _tcp_probe("127.0.0.1", 19999, timeout=0.01) is False


@pytest.mark.unit
@pytest.mark.core
class TestValidFormats:
    """Tests for format validation in direct_run."""

    def test_valid_formats_accepted(self) -> None:
        from onetool.cli_commands.direct_app import _VALID_FORMATS
        assert "json_h" in _VALID_FORMATS
        assert "json" in _VALID_FORMATS
        assert "yml" in _VALID_FORMATS
        assert "yml_h" in _VALID_FORMATS
        assert "raw" in _VALID_FORMATS

    def test_old_text_format_not_valid(self) -> None:
        from onetool.cli_commands.direct_app import _VALID_FORMATS
        assert "text" not in _VALID_FORMATS

    def test_old_yaml_format_not_valid(self) -> None:
        from onetool.cli_commands.direct_app import _VALID_FORMATS
        assert "yaml" not in _VALID_FORMATS
