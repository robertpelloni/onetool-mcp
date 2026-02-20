"""Serve CLI entry point for OneTool MCP server."""

from __future__ import annotations

import atexit
import os
import signal
from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from rich.console import Console


def _suppress_shutdown_warnings() -> None:
    """Suppress pymupdf SWIG warnings at exit.

    pymupdf emits a DeprecationWarning about swigvarlink during Python's
    interpreter shutdown. This warning is emitted at the C level during
    garbage collection. Redirecting stderr at the fd level suppresses it.
    """
    try:
        # Redirect stderr at the OS level to suppress C-level warnings
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, 2)
        os.close(devnull_fd)
    except Exception:
        pass


atexit.register(_suppress_shutdown_warnings)
from rich.console import Console

import ot
from ot._cli import create_cli, version_callback
from ot.support import get_support_banner, get_version

# Console for CLI output - no auto-highlighting, output to stderr
console = Console(stderr=True, highlight=False)

app = create_cli(
    "onetool",
    "OneTool MCP server - exposes a single 'run' tool for LLM code generation.",
)


def _print_startup_banner() -> None:
    """Print startup message to stderr."""
    version = get_version()
    console.print(f"[bold cyan]OneTool MCP Server[/bold cyan] [dim]v{version}[/dim]")
    console.print(get_support_banner())


def _setup_signal_handlers() -> None:
    """Set up signal handlers for clean exit."""

    def handle_signal(signum: int, _frame: object) -> None:
        """Handle termination signals gracefully."""
        sig_name = signal.Signals(signum).name
        console.print(f"\nReceived {sig_name}, shutting down...")
        # Use os._exit() for immediate termination - sys.exit() doesn't work
        # well with asyncio event loops and can require multiple Ctrl+C presses
        os._exit(0)

    # Handle SIGINT (Ctrl+C) and SIGTERM
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

# Init subcommand group - manage OneTool configuration directory
init_app = typer.Typer(
    name="init",
    help="Initialize and manage the OneTool configuration directory.",
    invoke_without_command=True,
)
app.add_typer(init_app)


@init_app.callback()
def init_callback(
    ctx: typer.Context,
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to onetool.yaml to initialise (directory will be created).",
    ),
) -> None:
    """Initialize and manage OneTool configuration directory.

    Run without subcommand to initialise: onetool init --config /path/to/.onetool/onetool.yaml
    """
    if ctx.invoked_subcommand is None:
        if config is None:
            console.print("[red]Error: Missing option '--config' / '-c'[/red]")
            console.print("Usage: onetool init --config /path/to/.onetool/onetool.yaml")
            raise typer.Exit(1)
        from ot.paths import ensure_ot_dir
        ensure_ot_dir(config, quiet=False, force=False)


@init_app.command("create", hidden=True)
def init_create(
    config: Path = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to onetool.yaml to create (directory will be initialised).",
    ),
) -> None:
    """Initialize OneTool configuration directory.

    Creates the directory at config file's parent and copies template files.
    Existing files are preserved.
    """
    from ot.paths import ensure_ot_dir

    ot_dir = config.parent
    if ot_dir.exists():
        console.print(f"Config directory already exists at {ot_dir}/")
        console.print("Use 'onetool init reset --config ...' to reinstall templates.")
        return

    ensure_ot_dir(config, quiet=False, force=False)


@init_app.command("reset")
def init_reset(
    config: Path = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to onetool.yaml (directory contains files to reset).",
    ),
) -> None:
    """Reset config directory to default templates.

    Prompts for each file before overwriting. For existing files, offers to
    create a backup first. Backups are named file.bak, file.bak.1, etc.
    """
    import shutil

    from ot.paths import create_backup, get_template_files

    ot_dir = config.parent

    # Ensure directory exists
    ot_dir.mkdir(parents=True, exist_ok=True)

    template_files = get_template_files()
    if not template_files:
        console.print("No template files found.")
        return

    copied_files: list[str] = []
    backed_up_files: list[tuple[str, Path]] = []
    skipped_files: list[str] = []

    for source_path, dest_name in template_files:
        dest_path = ot_dir / dest_name
        exists = dest_path.exists()

        if exists:
            # Prompt for overwrite
            console.print(f"\n{dest_name} already exists.")
            do_overwrite = typer.confirm("Overwrite?", default=True)

            if not do_overwrite:
                skipped_files.append(dest_name)
                continue

            # Prompt for backup
            do_backup = typer.confirm(f"Create backup of {dest_name}?", default=True)

            if do_backup:
                backup_path = create_backup(dest_path)
                backed_up_files.append((dest_name, backup_path))

        shutil.copy(source_path, dest_path)
        copied_files.append(dest_name)

    # Summary
    console.print()
    if copied_files:
        console.print(f"Reset files in {ot_dir}/:")
        for name in copied_files:
            console.print(f"  + {name}")

    if backed_up_files:
        console.print("\nBackups created:")
        for name, backup_path in backed_up_files:
            console.print(f"  {name} -> {backup_path.name}")

    if skipped_files:
        console.print("\nSkipped:")
        for name in skipped_files:
            console.print(f"  - {name}")


@init_app.command("validate")
def init_validate(
    config: Path = typer.Option(
        ...,
        "--config",
        "-c",
        exists=True,
        readable=True,
        help="Path to onetool.yaml to validate.",
    ),
    secrets: Path | None = typer.Option(
        None,
        "--secrets",
        "-s",
        help="Path to secrets file.",
    ),
) -> None:
    """Validate configuration and show status.

    Checks config files for errors, then displays packs, secrets (names only),
    snippets, aliases, and MCP servers.
    """
    from loguru import logger

    from ot import __version__
    from ot.config.loader import get_config, load_config
    from ot.config.secrets import load_secrets
    from ot.executor.tool_loader import load_tool_registry

    # Suppress DEBUG logs from config loader
    logger.remove()

    errors: list[str] = []
    validated: list[str] = []

    try:
        load_config(config, secrets_path=secrets)
        validated.append(str(config))
    except Exception as e:
        errors.append(f"{config}: {e}")

    # Report validation results
    console.print("Configuration\n")
    console.print(f"Version: [cyan]{__version__}[/cyan]\n")

    console.print("Config directory:")
    ot_dir = config.parent
    if ot_dir.exists():
        console.print(f"  {ot_dir}/ - [green]OK[/green]")
    else:
        console.print(f"  {ot_dir}/ - [red]missing[/red]")

    if validated:
        console.print("\nConfig files:")
        for path in validated:
            console.print(f"  + {path}")

    if errors:
        console.print("\n[red]Validation errors:[/red]")
        for error in errors:
            console.print(f"  ! {error}")
        raise typer.Exit(1)

    if not validated and not errors:
        console.print("\nNo configuration files found.")
        return

    # Load merged config for status display
    try:
        cfg = get_config()
    except Exception as e:
        console.print(f"\n[red]Config error:[/red] {e}")
        return

    # Packs and tools
    try:
        registry = load_tool_registry()
        if registry.packs:
            total_tools = 0
            pack_list = []
            for pack_name, pack_funcs in sorted(registry.packs.items()):
                from ot.executor.worker_proxy import WorkerPackProxy

                if isinstance(pack_funcs, WorkerPackProxy):
                    func_count = len(pack_funcs.functions)
                else:
                    func_count = len(pack_funcs)
                total_tools += func_count
                pack_list.append((pack_name, func_count))

            console.print(f"\nPacks ({len(pack_list)}, {total_tools} tools):")
            for pack_name, func_count in pack_list:
                console.print(f"  {pack_name} ({func_count})")
        else:
            console.print("\nPacks:")
            console.print("  (none)")
    except Exception as e:
        console.print("\nPacks:")
        console.print(f"  [red]Error loading tools:[/red] {e}")

    # Secrets (names only) - use explicit --secrets path only
    try:
        secrets_data = load_secrets(secrets)
        if secrets_data:
            sorted_keys = sorted(secrets_data.keys())
            console.print(f"\nSecrets ({len(sorted_keys)}):")
            for key in sorted_keys:
                console.print(f"  {key} - [green]set[/green]")
        else:
            console.print("\nSecrets:")
            console.print("  (none configured)")
    except Exception as e:
        console.print("\nSecrets:")
        console.print(f"  [red]Error:[/red] {e}")

    # Snippets
    if cfg and cfg.snippets:
        sorted_snippets = sorted(cfg.snippets.keys())
        console.print(f"\nSnippets ({len(sorted_snippets)}):")
        console.print(f"  {', '.join(sorted_snippets)}")
    else:
        console.print("\nSnippets:")
        console.print("  (none)")

    # Aliases
    if cfg and cfg.alias:
        sorted_aliases = sorted(cfg.alias.items())
        console.print(f"\nAliases ({len(sorted_aliases)}):")
        alias_items = [f"{name} -> {target}" for name, target in sorted_aliases]
        console.print(f"  {', '.join(alias_items)}")
    else:
        console.print("\nAliases:")
        console.print("  (none)")

    # Servers
    if cfg and cfg.servers:
        sorted_servers = sorted(cfg.servers.keys())
        console.print(f"\nMCP Servers ({len(sorted_servers)}):")
        console.print(f"  {', '.join(sorted_servers)}")
    else:
        console.print("\nMCP Servers:")
        console.print("  (none)")


@app.callback(invoke_without_command=True)
def serve(
    ctx: typer.Context,
    _version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback("onetool", ot.__version__),
        is_eager=True,
        help="Show version and exit.",
    ),
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to onetool.yaml configuration file.",
    ),
    secrets: Path | None = typer.Option(
        None,
        "--secrets",
        "-s",
        help="Path to secrets file. If omitted, no secrets are loaded.",
    ),
) -> None:
    """Run the OneTool MCP server over stdio transport.

    This starts the MCP server that exposes the 'run' tool for LLM integrations.
    The server communicates via stdio and is typically invoked by MCP clients.

    Examples:
        onetool --config /path/to/.onetool/onetool.yaml
        onetool --config /path/to/.onetool/onetool.yaml --secrets /path/to/.onetool/secrets.yaml
    """
    # Only run if no subcommand was invoked (handles --help automatically)
    if ctx.invoked_subcommand is not None:
        return

    if config is None:
        console.print("[red]Error: Missing option '--config' / '-c'.[/red]")
        console.print("Usage: onetool --config /path/to/.onetool/onetool.yaml")
        raise typer.Exit(1)
    if not config.exists():
        console.print(f"[red]Error: Config file not found: {config}[/red]")
        raise typer.Exit(1)

    # Load config (secrets threaded through load_config)
    from ot.config.loader import get_config

    get_config(config, secrets_path=secrets)

    # Set up signal handlers for clean exit (before starting server)
    _setup_signal_handlers()

    # Print startup banner to stderr (stdout is for MCP JSON-RPC)
    _print_startup_banner()

    # Import here to avoid circular imports and only load when needed
    from ot.server import main as server_main

    server_main()


def cli() -> None:
    """Run the CLI application."""
    app()


if __name__ == "__main__":
    cli()
