"""Unit tests for REPL tab completion logic, multi-line input, and smoke tests."""

from __future__ import annotations

import pytest


@pytest.mark.unit
@pytest.mark.core
class TestReplCompletion:
    """Test the tab completer function builds correct completion list."""

    def _build_completions(self, packs: dict) -> list[str]:
        """Simulate the completion list built in direct_repl."""
        completions: list[str] = [":quit", "exit()", "quit()", ":help"]
        for pack_name, pack_funcs in packs.items():
            for fn_name in pack_funcs:
                completions.append(f"{pack_name}.{fn_name}")
        return completions

    def _make_completer(self, completions: list[str]):  # type: ignore[return]
        def _completer(text: str, state: int) -> str | None:
            matches = [c for c in completions if c.startswith(text)]
            return matches[state] if state < len(matches) else None
        return _completer

    def test_completes_pack_prefix(self) -> None:
        comps = self._build_completions({"brave": ["web_search", "local_search"], "ot": ["debug"]})
        completer = self._make_completer(comps)
        assert completer("brave.", 0) == "brave.web_search"
        assert completer("brave.", 1) == "brave.local_search"
        assert completer("brave.", 2) is None

    def test_completes_ot_prefix(self) -> None:
        comps = self._build_completions({"ot": ["debug", "packs", "help"]})
        completer = self._make_completer(comps)
        assert completer("ot.d", 0) == "ot.debug"
        assert completer("ot.d", 1) is None

    def test_no_match_returns_none(self) -> None:
        comps = self._build_completions({"ot": ["debug"]})
        completer = self._make_completer(comps)
        assert completer("xyz.", 0) is None

    def test_empty_prefix_returns_all(self) -> None:
        comps = self._build_completions({"ot": ["debug"], "brave": ["search"]})
        completer = self._make_completer(comps)
        assert completer("", 0) is not None
        assert completer("", 1) is not None

    def test_special_commands_in_completions(self) -> None:
        comps = self._build_completions({"ot": ["debug"]})
        assert ":quit" in comps
        assert "exit()" in comps
        assert "quit()" in comps

    def test_help_command_in_completions(self) -> None:
        comps = self._build_completions({})
        assert ":help" in comps

    def test_quit_completable_from_colon(self) -> None:
        comps = self._build_completions({})
        completer = self._make_completer(comps)
        assert completer(":", 0) is not None
        matches = [completer(":", i) for i in range(10) if completer(":", i) is not None]
        assert ":quit" in matches
        assert ":help" in matches

    def test_exit_completable(self) -> None:
        comps = self._build_completions({})
        completer = self._make_completer(comps)
        assert completer("exit", 0) == "exit()"

    def test_quit_completable(self) -> None:
        comps = self._build_completions({})
        completer = self._make_completer(comps)
        assert completer("quit", 0) == "quit()"


@pytest.mark.unit
@pytest.mark.core
class TestReplMultiline:
    """Test multi-line input detection via codeop."""

    def _compile(self, source: str):
        import codeop
        try:
            return codeop.compile_command(source, "<stdin>", "single")
        except SyntaxError:
            return "error"

    def test_simple_expression_is_complete(self) -> None:
        assert self._compile("ot.debug()") is not None

    def test_open_paren_is_incomplete(self) -> None:
        assert self._compile("ot.debug(") is None

    def test_for_loop_header_is_incomplete(self) -> None:
        assert self._compile("for x in [1,2]:") is None

    def test_for_loop_with_body_is_complete_after_blank(self) -> None:
        # Standard Python: needs trailing newline after block
        result = self._compile("for x in [1,2]:\n    print(x)\n")
        assert result is not None

    def test_syntax_error_raises(self) -> None:
        assert self._compile("def !!!") == "error"

    def test_multiline_call_is_complete(self) -> None:
        result = self._compile("brave.search(\n    query='test'\n)")
        assert result is not None

    def test_dict_literal_incomplete(self) -> None:
        assert self._compile("x = {") is None

    def test_semicolon_separated_complete(self) -> None:
        result = self._compile("x = 1; y = 2")
        assert result is not None


@pytest.mark.unit
@pytest.mark.core
class TestReplSmokeImport:
    """Smoke: the direct_repl function is importable and callable (exit on non-TTY)."""

    def test_direct_repl_importable(self) -> None:
        from onetool.cli_commands.direct_app import direct_repl  # noqa: F401

    def test_direct_repl_exits_when_not_tty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import typer
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        from onetool.cli_commands.direct_app import direct_repl
        with pytest.raises((typer.Exit, SystemExit)):
            direct_repl(config=None, secrets=None)

    def test_direct_repl_reuses_event_loop_across_commands(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """REPL must create one event loop and reuse it, not a new loop per command."""
        import asyncio
        from unittest.mock import MagicMock, patch

        loops_created: list[asyncio.AbstractEventLoop] = []
        original_new_event_loop = asyncio.new_event_loop

        def counting_new_event_loop() -> asyncio.AbstractEventLoop:
            loop = original_new_event_loop()
            loops_created.append(loop)
            return loop

        inputs = iter(["ot.debug()", ":quit"])
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))

        mock_result = MagicMock()
        mock_result.result = "ok"

        with (
            patch("asyncio.new_event_loop", side_effect=counting_new_event_loop),
            patch("ot.executor.runner.execute_command", return_value=mock_result),
            patch("onetool.cli_commands.direct_app._load_config"),
            patch("ot.executor.tool_loader.load_tool_registry", side_effect=Exception("no tools")),
        ):
            from onetool.cli_commands.direct_app import direct_repl
            import contextlib
            with contextlib.suppress(SystemExit, Exception):
                direct_repl(config=None, secrets=None)

        assert len(loops_created) == 1, "REPL must create exactly one event loop for the session"
