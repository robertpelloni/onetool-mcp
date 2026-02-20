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


def _stdin_is_tty() -> bool:
    """Return True if stdin is a TTY. Extracted for testability."""
    import sys

    return sys.stdin.isatty()


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


def _write_onetool_yaml(config_path: Path, includes: list[str]) -> None:
    """Write a minimal onetool.yaml with the given includes."""
    import yaml

    data: dict = {"version": 2}
    if includes:
        data["include"] = includes

    config_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))


def _materialise_servers_yaml(
    ot_dir: Path, server_names: list[str]
) -> None:
    """Materialise servers.yaml with only the requested server blocks."""
    import yaml

    from ot.paths import get_global_templates_dir

    templates_dir = get_global_templates_dir()
    src = templates_dir / "servers.yaml"
    if not src.exists():
        console.print("[yellow]Warning: servers.yaml not found in package templates[/yellow]")
        return

    raw = yaml.safe_load(src.read_text()) or {}
    all_servers = raw.get("servers", {})

    selected: dict = {}
    unknown: list[str] = []
    for name in server_names:
        if name in all_servers:
            selected[name] = all_servers[name]
        else:
            unknown.append(name)

    if unknown:
        console.print(
            f"[yellow]Unknown servers (will be skipped): {', '.join(unknown)}[/yellow]"
        )
        console.print(f"  Available: {', '.join(sorted(all_servers.keys()))}")

    dest = ot_dir / "servers.yaml"
    dest.write_text(
        yaml.dump({"servers": selected}, default_flow_style=False, sort_keys=False)
    )
    console.print(f"  [green]✓[/green] servers.yaml (servers: {', '.join(selected.keys())})")


def _materialise_file(ot_dir: Path, filename: str) -> bool:
    """Materialise a single file from global_templates. Returns True if success."""
    import shutil

    from ot.paths import get_global_templates_dir

    templates_dir = get_global_templates_dir()
    # Support -template suffix stripping (e.g., secrets-template.yaml -> secrets.yaml)
    src_name = filename.replace(".yaml", "-template.yaml")
    src = templates_dir / src_name
    if not src.exists():
        src = templates_dir / filename
    if not src.exists():
        console.print(f"  [red]✗[/red] {filename} not found in package templates")
        return False

    dest = ot_dir / filename
    shutil.copy(src, dest)
    console.print(f"  [green]✓[/green] {filename}")
    return True


@init_app.callback()
def init_callback(
    ctx: typer.Context,
    config: Path | None = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to onetool.yaml to initialise (directory will be created).",
    ),
    security: bool = typer.Option(
        False,
        "--security",
        help="Materialise security.yaml for custom security rules.",
    ),
    servers: str | None = typer.Option(
        None,
        "--servers",
        help="Comma-separated server names to include (e.g. devtools,playwright,github).",
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        "-f",
        help="Materialise a specific template file (e.g. security.yaml).",
    ),
    full: bool = typer.Option(
        False,
        "--full",
        help="Materialise all global template files.",
    ),
) -> None:
    """Initialize OneTool configuration directory.

    Without flags: guided interactive setup (TTY) or minimal config (non-TTY).

    Examples:
      onetool init --config .onetool/onetool.yaml
      onetool init --config .onetool/onetool.yaml --security
      onetool init --config .onetool/onetool.yaml --servers devtools,playwright
      onetool init --config .onetool/onetool.yaml --full
    """
    if ctx.invoked_subcommand is not None:
        return

    if config is None:
        console.print("[red]Error: Missing option '--config' / '-c'[/red]")
        console.print("Usage: onetool init --config /path/to/.onetool/onetool.yaml")
        raise typer.Exit(1)

    import shutil
    import sys

    from ot.paths import get_global_templates_dir

    ot_dir = config.parent
    ot_dir.mkdir(parents=True, exist_ok=True)

    templates_dir = get_global_templates_dir()
    includes: list[str] = []

    if full:
        # Materialise all YAML templates
        console.print(f"Materialising all templates into {ot_dir}/")
        import stat

        for tmpl in sorted(templates_dir.glob("*.yaml")):
            dest_name = tmpl.name.replace("-template.yaml", ".yaml")
            dest = ot_dir / dest_name
            shutil.copy(tmpl, dest)
            if dest_name == "secrets.yaml":
                dest.chmod(stat.S_IRUSR | stat.S_IWUSR)
            console.print(f"  [green]✓[/green] {dest_name}")
            if dest_name not in ("onetool.yaml", "bench.yaml", "bench-secrets.yaml"):
                includes.append(dest_name)
        _write_onetool_yaml(config, includes)
        console.print(f"\n[green]✓[/green] {config.name} written with {len(includes)} includes")
        return

    if file is not None:
        # Materialise a single specific file
        console.print(f"Materialising {file} into {ot_dir}/")
        _materialise_file(ot_dir, file)
        console.print(
            f"\n[dim]Note:[/dim] {file} is now user-owned and will override the package default."
        )
        console.print("[dim]Tip:[/dim]  Add it to your onetool.yaml include: list to activate.")
        return

    # Flag-based setup (--security, --servers, or interactive)
    do_security = security
    selected_servers: list[str] = []

    if servers is not None:
        selected_servers = [s.strip() for s in servers.split(",") if s.strip()]

    is_interactive = not (security or servers is not None) and sys.stdin.isatty()

    if is_interactive:
        # Guided interactive setup
        console.print(f"Setting up OneTool config at {ot_dir}/\n")
        do_security = typer.confirm("Configure security rules? [y/N]", default=False)

        # Ask for servers
        all_servers_src = templates_dir / "servers.yaml"
        if all_servers_src.exists():
            import yaml as _yaml

            raw = _yaml.safe_load(all_servers_src.read_text()) or {}
            available_srv = list((raw.get("servers") or {}).keys())
        else:
            available_srv = ["devtools", "playwright", "github"]

        srv_options = ", ".join(available_srv) + ", none"
        console.print(f"\nInclude proxy servers? ({srv_options}) [none]")
        srv_input = typer.prompt("  Servers", default="none")
        if srv_input.strip().lower() != "none":
            selected_servers = [s.strip() for s in srv_input.split(",") if s.strip() and s.strip().lower() != "none"]

    # Materialise requested files
    if do_security:
        console.print(f"\nMaterialising into {ot_dir}/")
        if _materialise_file(ot_dir, "security.yaml"):
            includes.append("security.yaml")

    if selected_servers:
        if not do_security:
            console.print(f"\nMaterialising into {ot_dir}/")
        _materialise_servers_yaml(ot_dir, selected_servers)
        includes.append("servers.yaml")

    # Write the onetool.yaml
    _write_onetool_yaml(config, includes)

    console.print(f"\n[green]✓[/green] {config} written")

    if includes:
        console.print(f"  Includes: {', '.join(includes)}")
    else:
        console.print(
            "\n[dim]Using package defaults for security rules. "
            "No servers configured.[/dim]"
        )
        console.print(
            "[dim]Run `onetool init --security` or `--servers <list>` to customise.[/dim]"
        )


@init_app.command("create", hidden=True)
def init_create(
    config: Path = typer.Option(
        ...,
        "--config",
        "-c",
        help="Path to onetool.yaml to create (directory will be initialised).",
    ),
) -> None:
    """Initialize OneTool configuration directory (legacy: copies all templates).

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

    # Include source reporting
    try:
        import yaml

        from ot.config.loader import _resolve_include_path
        from ot.paths import get_global_templates_dir

        raw_config = yaml.safe_load(config.read_text()) or {}
        include_list: list[str] = raw_config.get("include", [])
        ot_dir = config.parent
        templates_dir = get_global_templates_dir()

        # Known includeable template files
        known_templates = sorted(
            tmpl.name.replace("-template.yaml", ".yaml")
            for tmpl in templates_dir.glob("*.yaml")
            if not tmpl.name.startswith("_")
            and tmpl.name not in ("onetool.yaml", "bench.yaml", "bench-secrets.yaml")
        )

        listed_set = set(include_list)
        console.print(f"\nIncludes ({len(include_list)} listed):")

        # Show source for each listed include
        for inc in include_list:
            resolved = _resolve_include_path(inc, ot_dir)
            if resolved is None:
                console.print(f"  [red]\\[missing][/red] {inc}")
            elif resolved.is_relative_to(ot_dir):
                console.print(f"  [cyan]\\[user][/cyan]    {inc} -> {resolved}")
            elif resolved.is_relative_to(templates_dir):
                console.print(f"  [yellow]\\[default][/yellow] {inc} -> {resolved}")
                console.print(
                    f"             [dim]Hint: Run `onetool init --file {inc}` to customise[/dim]"
                )
            else:
                console.print(f"  [green]\\[absolute][/green] {inc} -> {resolved}")

        # Show known templates that are not listed
        not_listed = [t for t in known_templates if t not in listed_set]
        if not_listed:
            for name in not_listed:
                console.print(f"  [dim]\\[not listed][/dim] {name}")
    except Exception as e:
        console.print(f"\n[dim]Include source check skipped: {e}[/dim]")

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
        if _stdin_is_tty():
            console.print(f"[yellow]OneTool is not initialized.[/yellow]")
            console.print(f"Config file not found: {config}")
            do_init = typer.confirm("Initialize now?", default=True)
            if do_init:
                from ot.paths import ensure_ot_dir

                ensure_ot_dir(config, quiet=False, force=False)
                console.print(f"[green]✓[/green] Initialized at {config.parent}/")
            else:
                console.print(f"Run 'onetool init --config {config}' when ready.")
                raise typer.Exit(1)
        else:
            console.print(f"OneTool not initialized. Run: onetool init --config {config}")
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
