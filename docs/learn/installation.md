# Installation

**Python 3.11+ required.**

For the quickest path, see [Quickstart](quickstart.md). This page covers all platforms and optional features.

## System Requirements

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | >= 3.11 | Runtime environment |
| **uv** | Latest | Package management |

### Installing System Requirements

**macOS:**

```bash
brew install python@3.11
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Linux (Debian/Ubuntu):**

```bash
apt install python3.11
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**

```powershell
winget install Python.Python.3.11
irm https://astral.sh/uv/install.ps1 | iex
```

## Install

```bash
uv tool install onetool-mcp
```

This installs `onetool` and `bench` commands globally.

**Optional:** For safe file deletion (moves to trash instead of permanent delete):

```bash
uv tool install onetool-mcp --with send2trash
```

## Upgrade

```bash
uv tool upgrade onetool-mcp
```

Or to upgrade all tools:

```bash
uv tool upgrade --all
```

## Uninstall

```bash
uv tool uninstall onetool-mcp
```

This removes the tool and its isolated environment. **Config is preserved.**

| Location | Preserved on Uninstall? |
|----------|------------------------|
| `~/.onetool/` (global config) | Yes |
| `.onetool/` (project config) | Yes |
| Tool environment | No (removed) |

To fully reset (including config):

```bash
uv tool uninstall onetool-mcp
rm -rf ~/.onetool/  # Optional: remove global config
```

## From Source (Development)

```bash
git clone https://github.com/beycom/onetool-mcp.git
cd onetool
uv sync --group dev
```

### Local Development Install

```bash
uv tool install -e .
```

Code changes are picked up immediately. Reinstall only for new entry points, dependencies, or top-level packages.

## API Keys

API keys are stored in `secrets.yaml` (gitignored):

| Key | Service | Used By |
|-----|---------|---------|
| `OPENAI_API_KEY` | OpenRouter | `llm.transform`, `code.*` |
| `BRAVE_API_KEY` | [Brave Search](https://brave.com/search/api/) | `brave.*` tools |
| `CONTEXT7_API_KEY` | [Context7](https://context7.com) | `context7.*` tools |

### Example secrets.yaml

```yaml
# .onetool/config/secrets.yaml
BRAVE_API_KEY: "BSA..."
OPENAI_API_KEY: "sk-..."
CONTEXT7_API_KEY: "c7-..."
```

**Resolution order:** `OT_SECRETS_FILE` > `.onetool/config/secrets.yaml` > `~/.onetool/config/secrets.yaml`

### Configuration Variables

| Variable       | Default   | Purpose                                   |
|----------------|-----------|-------------------------------------------|
| `OT_LOG_LEVEL` | `INFO`    | Logging verbosity                         |
| `OT_LOG_DIR`   | `../logs` | Log file directory (relative to config)   |

### Transform Tool Configuration

The transform tool requires explicit configuration in `onetool.yaml`:

```yaml
tools:
  transform:
    base_url: "https://openrouter.ai/api/v1"  # Required
    model: "openai/gpt-5-mini"                 # Required
```

The tool is not available until both `base_url` and `model` are configured, plus `OPENAI_API_KEY` in secrets.

## MCP Configuration

### Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "onetool": {
      "command": "onetool"
    }
  }
}
```

### Project Setup

Create a `.onetool/` directory in your project:

| Platform | Global Config | Project Config |
|----------|--------------|----------------|
| macOS/Linux | `~/.onetool/` | `.onetool/` |
| Windows | `%USERPROFILE%\.onetool\` | `.onetool\` |

## External Tools

### Ripgrep Search

```bash
# macOS
brew install ripgrep

# Linux
apt install ripgrep

# Windows
winget install BurntSushi.ripgrep.MSVC
```

## Verify Installation

```bash
# Check version
onetool --version

# Start MCP server
onetool

# Run benchmarks (from source)
OT_CWD=demo bench run demo/bench/features.yaml
```

## Next Steps

- [Configuration](configuration.md) - YAML schema and options
- [CLI Reference](../reference/cli/onetool.md) - Command-line tools
