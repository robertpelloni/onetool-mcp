# onetool

Exposes a single `run` tool that executes Python code. Your agent writes code; OneTool runs it.

## Usage

```bash
onetool [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-c, --config PATH` | Path to onetool.yaml configuration file |
| `-v, --version` | Show version and exit |

## Commands

### init

Initialize and manage global configuration in `~/.onetool/`.

```bash
onetool init [subcommand]
```

Running `onetool init` without a subcommand runs an interactive TUI to select which extensions to materialise. Existing files are backed up to `.bak` automatically.

| Subcommand | Description |
|------------|-------------|
| `validate` | Validate config and show status |

#### init (default)

Interactive setup — select which extensions to materialise into the config directory. Pass `-c` to specify a directory or config file path.

```bash
onetool init                     # uses current directory
onetool init -c .onetool         # explicit directory
onetool init -c .onetool/ot.yaml # explicit file path
```

#### init validate

Validates configuration files and displays status including packs, secrets (names only), snippets, aliases, and MCP servers.

```bash
onetool init validate -c .onetool/onetool.yaml
```

## Examples

```bash
# Start MCP server (stdio)
onetool

# Use specific config
onetool --config config/onetool.yaml
```

## Configuration

Configuration files: `.onetool/onetool.yaml` (project) or `~/.onetool/onetool.yaml` (global)

See [onetool Configuration](onetool-config.md) for full schema reference.

### Quick Setup

```bash
onetool init           # Interactive TUI setup
onetool init validate  # Check for errors
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OT_LOG_LEVEL` | Log level (DEBUG/INFO/WARNING/ERROR) |
| `OT_LOG_DIR` | Log directory path |

## How It Works

1. Loads tools from `src/ottools/` via AST-based discovery
2. Exposes a single `run` tool that executes Python code
3. Communicates via stdio using the MCP protocol

## Tool Discovery

Tools are discovered statically from `tools_dir` patterns in config:

```yaml
tools_dir:
  - src/ottools/*.py
```

Benefits:
- No code execution during discovery
- Instant startup
- Hot reload support