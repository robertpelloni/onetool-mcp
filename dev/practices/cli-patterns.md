# CLI Patterns

Patterns used in OneTool's CLIs: `onetool` and `bench`.

## CLIs Overview

| CLI | Package | Purpose |
|-----|---------|---------|
| `onetool` | `src/onetool/` | MCP server, setup, configuration |
| `bench` | `src/bench/` | Benchmark harness for testing tools |

## Shared Utilities

Both CLIs use shared utilities from `ot._cli`:

```python
from ot._cli import console, create_cli, version_callback
```

| Utility | Purpose |
|---------|---------|
| `create_cli()` | Create Typer app with standard settings |
| `console` | Rich console for formatted output |
| `version_callback()` | Standard `--version` flag handler |

## Required Patterns

### 1. Create CLI with Shared Utilities

```python
from ot._cli import create_cli, version_callback

app = create_cli(
    "onetool",
    "OneTool MCP server.",
    no_args_is_help=False,  # onetool runs server by default
)
```

### 2. Version Flag

```python
@app.callback()
def main(
    version: bool | None = typer.Option(
        None,
        "--version", "-v",
        callback=version_callback("onetool", __version__),
        is_eager=True,
    ),
) -> None:
    """OneTool MCP server."""
    pass
```

### 3. Logging Setup

```python
from ot.logging import configure_logging

def cli() -> None:
    configure_logging(log_name="onetool")
    app()
```

## Output Formatting

### Rich Console

```python
from ot._cli import console

console.print("[green]✓[/green] Success")
console.print("[red]Error:[/red] Failed")
console.print("[yellow]Warning:[/yellow] Check this")
```

### Progress Indicators

| Symbol | Meaning |
|--------|---------|
| ✓ | Success/complete |
| ✗ | Failure/error |
| ● | Active/in-progress |
| ○ | Pending/inactive |

### Tables

```python
from rich.table import Table

table = Table(title="Tools")
table.add_column("Pack", style="bold")
table.add_column("Functions")
table.add_row("brave", "search, news")
console.print(table)
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |

## Multi-Command Structure (bench)

The `bench` CLI uses subcommands:

```text
src/bench/
├── __init__.py          # __version__
├── cli.py               # Main entry point
├── commands/            # Subcommand implementations
│   ├── __init__.py
│   ├── run.py           # bench run
│   └── report.py        # bench report
└── core.py              # Shared business logic
```

### Main Entry Point

```python
# src/bench/cli.py
from ot._cli import create_cli, version_callback

app = create_cli(
    "bench",
    "OneTool benchmark harness.",
    no_args_is_help=True,
)

@app.callback()
def main(
    version: bool | None = typer.Option(
        None, "--version", "-v",
        callback=version_callback("bench", __version__),
        is_eager=True,
    ),
) -> None:
    """Benchmark harness for OneTool."""
    pass

# Import subcommands to auto-register
from bench.commands import run, report  # noqa: E402, F401
```

### Subcommand Module

```python
# src/bench/commands/run.py
from bench.cli import app
from ot.logging import LogSpan

@app.command()
def run(
    scenario: Annotated[str, typer.Argument(help="Scenario file")],
    verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False,
) -> None:
    """Run benchmark scenarios."""
    with LogSpan(span="bench.run", scenario=scenario) as s:
        # Implementation
        s.add("result", "success")
```

## Common Flag Patterns

### Config Flag

```python
config: Path | None = typer.Option(
    None,
    "--config", "-c",
    help="Path to configuration file.",
    exists=True,
)
```

### JSON Output

```python
output_json: Annotated[
    bool,
    typer.Option("--json", help="Output as JSON"),
] = False

if output_json:
    console.print(json.dumps({"items": items}))
```

### Confirmation Prompts

```python
yes: Annotated[
    bool,
    typer.Option("--yes", "-y", help="Skip confirmation"),
] = False

if not yes:
    if not typer.confirm(f"Delete '{name}'?"):
        raise typer.Exit(0)
```

## Testing CLIs

```python
from typer.testing import CliRunner

runner = CliRunner()

def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0

def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "OneTool" in result.stdout
```

## pyproject.toml Entry Points

```toml
[project.scripts]
onetool = "onetool.cli:cli"
bench = "bench.cli:cli"
```
