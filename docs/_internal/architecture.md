# Architecture

OneTool's source code organization and component structure.

## Directory Structure

```text
src/
├── ot/           # Core library
│   ├── _cli.py   # CLI utilities (create_cli, console, version_callback)
│   ├── config/   # Configuration loading (onetool.yaml, secrets.yaml)
│   ├── logging/  # Logging infrastructure (LogSpan, configure_logging)
│   ├── paths/    # Path resolution utilities
│   └── tools/    # Tool registry and inter-tool calling
│
├── ot_tools/     # Built-in tools (auto-discovered)
│   ├── brave.py  # Brave Search
│   ├── file.py   # File operations
│   ├── db.py     # Database queries
│   └── ...       # 16 tool packs total
│
├── onetool/      # onetool CLI
│   ├── __init__.py  # __version__
│   ├── cli.py       # Entry point
│   └── server.py    # MCP server implementation
│
└── bench/        # bench CLI
    ├── __init__.py  # __version__
    ├── cli.py       # Entry point
    └── commands/    # Subcommands (run, report, etc.)
```

## Components

### Core Library (`ot/`)

Shared utilities used by tools and CLIs:

| Module | Purpose |
|--------|---------|
| `ot._cli` | CLI utilities: `create_cli()`, `console`, `version_callback()` |
| `ot.config` | Load `onetool.yaml`, `secrets.yaml`, tool configs |
| `ot.logging` | `LogSpan`, `configure_logging()`, log formatting |
| `ot.paths` | `resolve_cwd_path()`, `resolve_ot_path()`, path prefixes |
| `ot.tools` | Tool registry, `call_tool()`, `get_pack()` |

### Tool Packs (`ot_tools/`)

Each file in `ot_tools/` is auto-discovered and becomes a tool pack:

- File: `brave.py` with `pack = "brave"` → Pack: `brave.*`
- Functions in `__all__` → Tools: `brave.search()`, `brave.news()`

See [Internal Tools](internal-tools.md) for creating bundled tools.

### CLIs

| CLI | Package | Purpose |
|-----|---------|---------|
| `onetool` | `src/onetool/` | MCP server, setup, configuration |
| `bench` | `src/bench/` | Benchmark harness for testing tools |

See [CLI Patterns](cli-patterns.md) for CLI development patterns.

## Configuration Flow

```text
1. CLI starts → load_env() → configure_logging()
2. Find config → .onetool/config/onetool.yaml (project) or ~/.onetool/config/ (global)
3. Load secrets → config/secrets.yaml
4. Discover tools → tools_dir patterns + src/ot_tools/
5. Start MCP server → FastMCP with discovered tools
```

## Tool Discovery

Tools are discovered from:

1. **Built-in**: `src/ot_tools/*.py` - always loaded
2. **Extension**: Paths in `tools_dir` config - user tools

Discovery process:
1. Glob patterns in `tools_dir` resolve to Python files
2. Each file is imported, `pack` variable extracted
3. Functions in `__all__` registered as `pack.function`
4. Tool schemas generated from function signatures + docstrings

## Logging Architecture

```text
Tool call → LogSpan context → LogEntry → Loguru → File output
                                            ↓
                                      Formatters (truncation, sanitization)
```

See [Logging](logging.md) for infrastructure details.
