"""Top-level `onetool direct` subcommand group: run, repl, list, search, help, servers, start, stop, status, restart, logs."""

from __future__ import annotations

import contextlib
import json
import os
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console

direct_app = typer.Typer(
    name="direct",
    help="Run tools from the shell, manage the execution host, or launch the REPL.",
    no_args_is_help=True,
)

console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)

_DEFAULT_PORT = 8765
_VALID_FORMATS = ("json", "json_h", "yml", "yml_h", "raw")


# ---------------------------------------------------------------------------
# PID / log file helpers
# ---------------------------------------------------------------------------


def _pid_file(port: int) -> Path:
    """Return the PID file path for an execution host on the given port."""
    return Path.home() / ".onetool" / f"direct-server-{port}.pid"


def _log_file(port: int) -> Path:
    """Return the log file path for an execution host on the given port."""
    return Path.home() / ".onetool" / f"direct-server-{port}.log"


def _read_pid_file(port: int) -> dict | None:
    """Read the PID file for the given port. Returns None if absent or unreadable."""
    try:
        return json.loads(_pid_file(port).read_text())
    except Exception:
        return None


def _write_pid_file(
    pid: int,
    port: int,
    config_path: str | None = None,
    secrets_path: str | None = None,
) -> None:
    path = _pid_file(port)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "pid": pid,
            "port": port,
            "config": config_path,
            "secrets": secrets_path,
            "started": time.time(),
            "log": str(_log_file(port)),
        })
    )


def _remove_pid_file(port: int) -> None:
    with contextlib.suppress(FileNotFoundError):
        _pid_file(port).unlink()


def _is_process_alive(pid: int) -> bool:
    """Return True if a process with the given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _kill_pid(pid: int) -> None:
    """Send SIGTERM (or equivalent) to the given PID."""
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.kernel32.TerminateProcess(  # type: ignore[attr-defined]
            ctypes.windll.kernel32.OpenProcess(1, False, pid), 0  # type: ignore[attr-defined]
        )
    else:
        os.kill(pid, signal.SIGTERM)


def _pack_func_names(pack_funcs: Any) -> list[str]:
    """Return tool names from a pack (handles both dict and WorkerPackProxy)."""
    from ot.executor.worker_proxy import WorkerPackProxy
    if isinstance(pack_funcs, WorkerPackProxy):
        return list(pack_funcs.functions.keys())
    return list(pack_funcs.keys())


def _pack_func_get(pack_funcs: Any, fn_name: str) -> Any:
    """Get a function from a pack by name (handles both dict and WorkerPackProxy)."""
    from ot.executor.worker_proxy import WorkerPackProxy
    if isinstance(pack_funcs, WorkerPackProxy):
        return pack_funcs.functions.get(fn_name)
    return pack_funcs.get(fn_name)


def _tcp_probe(host: str, port: int, timeout: float = 0.1) -> bool:
    """Return True if a TCP connection to host:port succeeds within timeout."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError, TimeoutError):
        return False


def _tcp_probe_wait(host: str, port: int, timeout_secs: float = 5.0, interval: float = 0.1) -> bool:
    """Poll TCP until server is ready. Returns True if ready within timeout."""
    deadline = time.monotonic() + timeout_secs
    while True:
        now = time.monotonic()
        remaining = deadline - now
        if remaining <= 0:
            break
        try:
            with socket.create_connection((host, port), timeout=min(interval, remaining)):
                return True
        except (OSError, ConnectionRefusedError, TimeoutError):
            if time.monotonic() < deadline:
                time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# Config / execution helpers
# ---------------------------------------------------------------------------


def _load_config(config: Path | None, secrets: Path | None) -> object:
    """Load onetool config, raising SystemExit(2) on failure."""
    import ot.logging  # noqa: F401 — removes loguru's default stderr handler
    from ot.config.loader import get_config

    if config is None:
        err_console.print("[red]Error: --config / -c is required for in-process execution.[/red]")
        raise typer.Exit(2)

    if not config.exists():
        err_console.print(f"[red]Config error: file not found: {config}[/red]")
        raise typer.Exit(2)

    if secrets is not None and not secrets.exists():
        err_console.print(f"[red]Config error: secrets file not found: {secrets}[/red]")
        raise typer.Exit(2)

    try:
        return get_config(config, secrets_path=secrets)
    except Exception as e:
        err_console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(2) from e


def _load_config_optional(config: Path | None, secrets: Path | None) -> None:
    """Load config if provided; silently skip if None."""
    if config is None:
        return
    import ot.logging  # noqa: F401
    from ot.config.loader import get_config
    try:
        get_config(config, secrets_path=secrets)
    except Exception as e:
        err_console.print(f"[red]Config error:[/red] {e}")
        raise typer.Exit(2) from e


def _build_command_with_meta(command: str, fmt: str, sanitize: bool) -> str:
    """Prepend __format__ and __sanitize__ assignments to a command string."""
    return f"__format__ = {fmt!r}; __sanitize__ = {sanitize!r}\n{command}"


def _run_via_server(command: str, host: str, port: int, timeout: int = 60) -> tuple[str, bool]:
    """POST command to execution host, return (result, success)."""
    import urllib.request

    body = json.dumps({"command": command}).encode()
    req = urllib.request.Request(
        f"http://{host}:{port}/run",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data.get("result", ""), data.get("success", True)


def _run_in_process(command: str) -> tuple[str, bool]:
    """Execute command in-process via execute_command(). Returns (result, success)."""
    import asyncio

    from ot.executor.runner import execute_command

    result = asyncio.run(execute_command(command))
    return result.result, result.success


def _resolve_command_source(cmd_str: str | None) -> str | None:
    """Resolve the command source from the raw argument.

    - None → None (no command given)
    - "-" → read from stdin
    - "foo.py" (file exists, .py extension) → read file contents
    - anything else → use as-is
    """
    if cmd_str is None:
        return None
    if cmd_str == "-":
        return sys.stdin.read().strip() or None
    p = Path(cmd_str)
    if p.suffix == ".py" and p.exists():
        return p.read_text(encoding="utf-8").strip() or None
    return cmd_str


# ---------------------------------------------------------------------------
# Server lifecycle helpers
# ---------------------------------------------------------------------------


def _start_host(
    config: Path | None,
    secrets: Path | None,
    port: int,
) -> None:
    """Start the HTTP execution host as a daemon process."""
    import subprocess

    log_path = _log_file(port)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [sys.executable, "-m", "onetool.cli_commands._direct_host_worker"]
    if config:
        cmd += ["--config", str(config)]
    if secrets:
        cmd += ["--secrets", str(secrets)]
    cmd += ["--port", str(port), "--host", "127.0.0.1"]

    with log_path.open("a") as log_fh:
        if sys.platform == "win32":
            proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=log_fh,
                stderr=log_fh,
            )
        else:
            proc = subprocess.Popen(
                cmd,
                start_new_session=True,
                stdout=log_fh,
                stderr=log_fh,
            )

    _write_pid_file(
        proc.pid,
        port,
        str(config) if config else None,
        str(secrets) if secrets else None,
    )
    err_console.print(f"Execution host started (PID {proc.pid}) on port {port}")
    err_console.print(f"Log: {log_path}")

    err_console.print("Waiting for host to be ready...")
    if _tcp_probe_wait("127.0.0.1", port):
        err_console.print("Host is ready.")
    else:
        err_console.print("[red]Execution host did not become ready within 5 seconds[/red]")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# `onetool direct run`
# ---------------------------------------------------------------------------


@direct_app.command("run")
def direct_run(
    command: Annotated[
        str | None,
        typer.Argument(
            help="Tool command to execute. Use '-' to read from stdin, or a .py file path."
        ),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to onetool.yaml"),
    ] = None,
    secrets: Annotated[
        Path | None,
        typer.Option("--secrets", "-s", help="Path to secrets file"),
    ] = None,
    fmt: Annotated[
        str,
        typer.Option(
            "--format", "-f",
            help="Output format: json_h (default), json, yml, yml_h, raw",
        ),
    ] = "json_h",
    no_host: Annotated[
        bool,
        typer.Option("--no-host", help="Skip server routing; always run in-process (requires --config)"),
    ] = False,
    sanitize: Annotated[
        bool,
        typer.Option("--sanitize", help="Enable output sanitization (for AI pipeline use)"),
    ] = False,
    timeout_opt: Annotated[
        int | None,
        typer.Option("--timeout", "-t", help="Server request timeout in seconds (overrides direct.timeout)"),
    ] = None,
) -> None:
    """Execute a tool command from the shell.

    COMMAND is the tool call to execute, e.g. 'ot.debug()'.
    Pass '-' to read from stdin, or a path to an existing .py file.

    Without --no-host, probes for a running execution host and routes to it if
    found. If direct.host: enable is set in config and no host is running, the
    server is auto-started before routing.

    Examples:
        onetool direct run -c .onetool/onetool.yaml "ot.debug()"
        echo "ot.debug()" | onetool direct run -c .onetool/onetool.yaml -
        onetool direct run -c .onetool/onetool.yaml report.py
        onetool direct run "ot.version()"           # routes to host if running
        onetool direct run --no-host -c .onetool/onetool.yaml "ot.version()"
    """
    if fmt not in _VALID_FORMATS:
        err_console.print(
            f"[red]Error: --format must be one of {', '.join(_VALID_FORMATS)} (got {fmt!r})[/red]"
        )
        raise typer.Exit(2)

    cmd_str = _resolve_command_source(command)
    if not cmd_str:
        err_console.print("[red]Error: no command provided.[/red]")
        raise typer.Exit(2)

    full_cmd = _build_command_with_meta(cmd_str, fmt, sanitize)

    # Routing: probe for server (unless --no-host)
    if not no_host:
        host = "127.0.0.1"
        port = _DEFAULT_PORT
        timeout = 60
        auto_start = False

        if config is not None and config.exists():
            try:
                import ot.logging  # noqa: F401
                from ot.config.loader import get_config
                cfg = get_config(config, secrets_path=secrets)
                port = cfg.direct.port
                timeout = cfg.direct.timeout
                if cfg.direct.host == "enable":
                    auto_start = True
                elif cfg.direct.host is not None:
                    # HOST:PORT for remote routing
                    parts = cfg.direct.host.rsplit(":", 1)
                    if len(parts) == 2:
                        host = parts[0]
                        port = int(parts[1])
                    else:
                        host = cfg.direct.host
            except Exception as e:
                err_console.print(f"[yellow]Warning: could not read config for routing: {e}[/yellow]")

        if timeout_opt is not None:
            timeout = timeout_opt

        if _tcp_probe(host, port):
            try:
                result_text, success = _run_via_server(full_cmd, host, port, timeout=timeout)
                print(result_text)
                raise typer.Exit(0 if success else 1)
            except typer.Exit:
                raise
            except Exception as e:
                err_console.print(f"[red]Server error:[/red] {e}")
                raise typer.Exit(1) from e

        if auto_start:
            # Start the execution host with the same config, then route
            err_console.print("[dim]Starting execution host...[/dim]")
            try:
                _start_host(config, secrets, port)
            except typer.Exit:
                raise
            except Exception as e:
                err_console.print(f"[red]Failed to auto-start host:[/red] {e}")
                raise typer.Exit(1) from e
            try:
                result_text, success = _run_via_server(full_cmd, host, port, timeout=timeout)
                print(result_text)
                raise typer.Exit(0 if success else 1)
            except typer.Exit:
                raise
            except Exception as e:
                err_console.print(f"[red]Server error:[/red] {e}")
                raise typer.Exit(1) from e

    # In-process execution
    _load_config(config, secrets)

    try:
        result_text, success = _run_in_process(full_cmd)
    except Exception as e:
        err_console.print(f"[red]Execution error:[/red] {e}")
        raise typer.Exit(1) from e

    print(result_text)
    raise typer.Exit(0 if success else 1)


# ---------------------------------------------------------------------------
# `onetool direct list`
# ---------------------------------------------------------------------------


@direct_app.command("list")
def direct_list(
    pattern: Annotated[
        str | None,
        typer.Argument(help="Pack name or glob pattern (e.g. 'brave' or 'brave.*')"),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to onetool.yaml"),
    ] = None,
    secrets: Annotated[
        Path | None,
        typer.Option("--secrets", "-s", help="Path to secrets file"),
    ] = None,
    info: Annotated[
        str,
        typer.Option("--info", "-i", help="Info level: min (default), full"),
    ] = "min",
) -> None:
    """List available tools (one per line, pipe-friendly).

    Examples:
        onetool direct list
        onetool direct list brave
        onetool direct list | fzf
    """
    _load_config_optional(config, secrets)

    try:
        from ot.executor.tool_loader import load_tool_registry
        registry = load_tool_registry()
    except Exception as e:
        err_console.print(f"[red]Error loading tools:[/red] {e}")
        raise typer.Exit(1) from e

    import fnmatch

    for pack_name, pack_funcs in registry.packs.items():
        for fn_name in _pack_func_names(pack_funcs):
            full_name = f"{pack_name}.{fn_name}"
            if pattern:
                pat = pattern if "." in pattern or "*" in pattern else f"{pattern}.*"
                if not fnmatch.fnmatch(full_name, pat):
                    continue

            if info == "full":
                fn = _pack_func_get(pack_funcs, fn_name)
                if fn is not None:
                    import inspect
                    try:
                        sig = str(inspect.signature(fn))
                    except (ValueError, TypeError):
                        sig = "(...)"
                    doc = (inspect.getdoc(fn) or "").split("\n")[0]
                    print(f"{full_name}{sig}" + (f" — {doc}" if doc else ""))
                else:
                    print(full_name)
            else:
                print(full_name)


# ---------------------------------------------------------------------------
# `onetool direct search`
# ---------------------------------------------------------------------------


@direct_app.command("search")
def direct_search(
    query: Annotated[
        str,
        typer.Argument(help="Search query (e.g. 'web search', 'convert pdf')"),
    ],
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to onetool.yaml"),
    ] = None,
    secrets: Annotated[
        Path | None,
        typer.Option("--secrets", "-s", help="Path to secrets file"),
    ] = None,
) -> None:
    """Find tools by name or description.

    Examples:
        onetool direct search "web search"
        onetool direct search "convert pdf"
    """
    _load_config_optional(config, secrets)

    try:
        from ot.meta._help import help as ot_help
        result = ot_help(query=query, info="min")
        print(result)
    except Exception as e:
        err_console.print(f"[red]Search error:[/red] {e}")
        raise typer.Exit(1) from e


# ---------------------------------------------------------------------------
# `onetool direct help`
# ---------------------------------------------------------------------------


@direct_app.command("help")
def direct_help(
    query: Annotated[
        str | None,
        typer.Argument(help="Tool name, pack name, or search phrase"),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to onetool.yaml"),
    ] = None,
    secrets: Annotated[
        Path | None,
        typer.Option("--secrets", "-s", help="Path to secrets file"),
    ] = None,
    info: Annotated[
        str,
        typer.Option("--info", "-i", help="Info level: min, default, full"),
    ] = "full",
) -> None:
    """Show tool signatures, parameters, and docstrings.

    Examples:
        onetool direct help brave.search
        onetool direct help brave
        onetool direct help "web search"
    """
    _load_config_optional(config, secrets)

    try:
        from ot.meta._help import help as ot_help
        result = ot_help(query=query or "", info=info)
        print(result)
    except Exception as e:
        err_console.print(f"[red]Help error:[/red] {e}")
        raise typer.Exit(1) from e


# ---------------------------------------------------------------------------
# `onetool direct servers`
# ---------------------------------------------------------------------------


@direct_app.command("servers")
def direct_servers(
    pattern: Annotated[
        str | None,
        typer.Argument(help="Filter by server name pattern"),
    ] = None,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to onetool.yaml"),
    ] = None,
    secrets: Annotated[
        Path | None,
        typer.Option("--secrets", "-s", help="Path to secrets file"),
    ] = None,
    info: Annotated[
        str,
        typer.Option("--info", "-i", help="Info level: min, default, full"),
    ] = "default",
) -> None:
    """List configured proxy servers and their connection status.

    Examples:
        onetool direct servers -c onetool.yaml
        onetool direct servers github
    """
    _load_config_optional(config, secrets)

    try:
        from ot.meta._discovery import servers as ot_servers
        result = ot_servers(pattern=pattern, info=info)
        print(result)
    except Exception as e:
        err_console.print(f"[red]Servers error:[/red] {e}")
        raise typer.Exit(1) from e


# ---------------------------------------------------------------------------
# `onetool direct repl`
# ---------------------------------------------------------------------------


@direct_app.command("repl")
def direct_repl(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to onetool.yaml"),
    ] = None,
    secrets: Annotated[
        Path | None,
        typer.Option("--secrets", "-s", help="Path to secrets file"),
    ] = None,
) -> None:
    """Launch an interactive REPL for tool execution.

    Tab-completes pack.tool names. History persists to ~/.onetool/repl_history.
    Multi-line input supported (open brackets trigger continuation prompt).
    Exit with :quit or Ctrl+D.

    Examples:
        onetool direct repl -c .onetool/onetool.yaml
    """
    if not sys.stdin.isatty():
        err_console.print(
            "[red]REPL requires an interactive terminal. "
            "Use 'onetool direct run -' for non-interactive input.[/red]"
        )
        raise typer.Exit(1)

    _load_config(config, secrets)

    console.print("[dim]Loading tools...[/dim]")
    try:
        from ot.executor.tool_loader import load_tool_registry
        registry = load_tool_registry()
    except Exception as e:
        err_console.print(f"[yellow]Warning: could not load tool registry: {e}[/yellow]")
        registry = None

    # Set up readline
    try:
        import readline as _rl

        history_file = Path.home() / ".onetool" / "repl_history"
        history_file.parent.mkdir(parents=True, exist_ok=True)
        with contextlib.suppress(OSError):
            _rl.read_history_file(str(history_file))
        _rl.set_history_length(1000)

        completions: list[str] = [":quit", "exit()", "quit()", ":help"]
        if registry is not None:
            for pack_name, pack_funcs in registry.packs.items():
                for fn_name in _pack_func_names(pack_funcs):
                    completions.append(f"{pack_name}.{fn_name}")

        def _completer(text: str, state: int) -> str | None:
            matches = [c for c in completions if c.startswith(text)]
            return matches[state] if state < len(matches) else None

        _rl.set_completer(_completer)
        _rl.parse_and_bind("tab: complete")
    except ImportError:
        history_file = None  # type: ignore[assignment]
        _rl = None  # type: ignore[assignment]
        completions = []

    import asyncio
    import codeop

    from ot.executor.runner import execute_command

    console.print("[bold]OneTool REPL[/bold] — type :quit or press Ctrl+D to exit")

    # Create one event loop for the full REPL session to avoid per-command loop overhead
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    buf: list[str] = []

    while True:
        prompt = "... " if buf else ">>> "
        try:
            line = input(prompt)
        except EOFError:
            console.print("\n[dim]Goodbye.[/dim]")
            break
        except KeyboardInterrupt:
            console.print("")
            buf.clear()
            continue

        if not buf and not line.strip():
            continue

        # Special commands (only at fresh prompt)
        if not buf:
            stripped = line.strip()
            if stripped in (":quit", "exit()", "quit()"):
                console.print("[dim]Goodbye.[/dim]")
                break
            if stripped == ":help":
                try:
                    from ot.meta._help import help as ot_help
                    print(ot_help(query="", info="min"))
                except Exception as e:
                    err_console.print(f"[red]Error:[/red] {e}")
                continue

        buf.append(line)
        source = "\n".join(buf)

        try:
            compiled = codeop.compile_command(source, "<stdin>", "single")
        except SyntaxError as e:
            err_console.print(f"[red]SyntaxError:[/red] {e}")
            buf.clear()
            continue

        if compiled is None:
            continue  # Incomplete — need more input

        cmd = source.strip()
        buf.clear()

        try:
            with console.status("[dim]running...[/dim]"):
                result = loop.run_until_complete(execute_command(cmd))
            print(result.result)
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted[/dim]")
        except Exception as e:
            err_console.print(f"[red]Error:[/red] {e}")

    loop.close()

    if history_file is not None and _rl is not None:
        with contextlib.suppress(Exception):
            _rl.write_history_file(str(history_file))


# ---------------------------------------------------------------------------
# `onetool direct start`
# ---------------------------------------------------------------------------


@direct_app.command("start")
def direct_start(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to onetool.yaml"),
    ] = None,
    secrets: Annotated[
        Path | None,
        typer.Option("--secrets", "-s", help="Path to secrets file"),
    ] = None,
    port: Annotated[
        int | None,
        typer.Option("--port", "-p", help="Port to listen on (overrides direct.port in config)"),
    ] = None,
) -> None:
    """Start the HTTP execution host.

    Starts the host and blocks until it is ready to accept connections.
    PID and log are written to ~/.onetool/direct-server-{port}.pid and direct-server-{port}.log.

    Use 'onetool direct run' to route commands to the running host.
    Set direct.host: enable in onetool.yaml to auto-start the host on first use.

    Examples:
        onetool direct start --config .onetool/onetool.yaml
        onetool direct start --config .onetool/onetool.yaml --port 9000
    """
    if config is None:
        err_console.print(
            "[yellow]Warning: no --config provided; starting with no tools loaded[/yellow]"
        )

    resolved_port = port
    if config is not None:
        try:
            import ot.logging  # noqa: F401
            from ot.config.loader import get_config
            cfg = get_config(config, secrets_path=secrets)
            if resolved_port is None:
                resolved_port = cfg.direct.port
        except Exception as e:
            err_console.print(f"[red]Config error:[/red] {e}")
            raise typer.Exit(2) from e

    if resolved_port is None:
        resolved_port = _DEFAULT_PORT

    _start_host(config, secrets, resolved_port)


# ---------------------------------------------------------------------------
# `onetool direct stop`
# ---------------------------------------------------------------------------


@direct_app.command("stop")
def direct_stop(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port of the server to stop (default: 8765)"),
    ] = _DEFAULT_PORT,
) -> None:
    """Stop the background execution host."""
    info = _read_pid_file(port)
    if info is None:
        err_console.print("No execution host running")
        return

    pid = info["pid"]
    if not _is_process_alive(pid):
        _remove_pid_file(port)
        err_console.print("Stale PID file removed (process was not running)")
        return

    try:
        _kill_pid(pid)
    except Exception as e:
        err_console.print(f"[red]Failed to stop host:[/red] {e}")
        raise typer.Exit(1) from e

    _remove_pid_file(port)
    err_console.print("Execution host stopped")


# ---------------------------------------------------------------------------
# `onetool direct status`
# ---------------------------------------------------------------------------


@direct_app.command("status")
def direct_status(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port of the server to query (default: 8765)"),
    ] = _DEFAULT_PORT,
) -> None:
    """Show execution host status (PID, port, uptime)."""
    info = _read_pid_file(port)
    if info is None:
        err_console.print("No execution host running")
        raise typer.Exit(1)

    pid = info["pid"]
    if not _is_process_alive(pid):
        err_console.print("No execution host running")
        raise typer.Exit(1)

    port_val = info.get("port", "unknown")
    started = info.get("started")
    if started:
        uptime_secs = int(time.time() - started)
        if uptime_secs >= 3600:
            uptime = f"{uptime_secs // 3600}h {(uptime_secs % 3600) // 60}m"
        elif uptime_secs >= 60:
            uptime = f"{uptime_secs // 60}m {uptime_secs % 60}s"
        else:
            uptime = f"{uptime_secs}s"
    else:
        uptime = "unknown"

    log = info.get("log")
    msg = f"Execution host running — PID {pid}, port {port_val}, uptime {uptime}"
    if log:
        msg += f"\nLog: {log}"
    err_console.print(msg)


# ---------------------------------------------------------------------------
# `onetool direct restart`
# ---------------------------------------------------------------------------


@direct_app.command("restart")
def direct_restart(
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to onetool.yaml (defaults to saved value)"),
    ] = None,
    secrets: Annotated[
        Path | None,
        typer.Option("--secrets", "-s", help="Path to secrets file (defaults to saved value)"),
    ] = None,
    port: Annotated[
        int | None,
        typer.Option("--port", "-p", help="Port (default: saved port or 8765)"),
    ] = None,
) -> None:
    """Stop the running execution host and start it again.

    Reuses the saved --config and --port from the previous start.
    Override any of them by passing the flag explicitly.
    If no host is running, behaves like start.
    """
    target_port = port if port is not None else _DEFAULT_PORT
    info = _read_pid_file(target_port)

    if info:
        pid = info["pid"]
        if _is_process_alive(pid):
            try:
                _kill_pid(pid)
                time.sleep(0.3)
            except Exception as e:
                err_console.print(f"[yellow]Warning: could not stop existing server:[/yellow] {e}")
        _remove_pid_file(target_port)

        if config is None and info.get("config"):
            config = Path(info["config"])
        if secrets is None and info.get("secrets"):
            secrets = Path(info["secrets"])
        resolved_port = port if port is not None else int(info.get("port", _DEFAULT_PORT))
    else:
        err_console.print("No execution host running; starting fresh")
        resolved_port = port if port is not None else _DEFAULT_PORT

    _start_host(config, secrets, resolved_port)


# ---------------------------------------------------------------------------
# `onetool direct logs`
# ---------------------------------------------------------------------------


@direct_app.command("logs")
def direct_logs(
    port: Annotated[
        int,
        typer.Option("--port", "-p", help="Port of the server whose logs to show (default: 8765)"),
    ] = _DEFAULT_PORT,
    lines: Annotated[
        int,
        typer.Option("--lines", "-n", help="Number of lines to show (default: 50)"),
    ] = 50,
) -> None:
    """Print the last N lines of the execution host log."""
    info = _read_pid_file(port)
    log_path_str = info.get("log") if info else None
    log_path = Path(log_path_str) if log_path_str else _log_file(port)

    if not log_path.exists():
        if info is None:
            err_console.print(f"No host running on port {port} and no log file found")
        else:
            err_console.print(f"No log file found at {log_path}")
        raise typer.Exit(1)

    all_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in all_lines[-lines:]:
        print(line)
