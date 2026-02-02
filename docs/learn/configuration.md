# Configuration

OneTool uses YAML configuration files with a three-tier system: bundled defaults → global (`~/.onetool/`) → project (`.onetool/`).

## Quick Start

```bash
# Initialize global config
onetool init

# Validate configuration
onetool init validate
```

## Key Files

| File | Purpose |
|------|---------|
| `onetool.yaml` | Main configuration (tools, servers, snippets) |
| `secrets.yaml` | API keys (gitignored) |
| `bench.yaml` | Benchmark harness config |

## Reference

- **[onetool Configuration](../reference/cli/onetool-config.md)** - Full YAML schema, pack settings, secrets, MCP servers, aliases, snippets, security
- **[bench Configuration](../reference/cli/bench.md#configuration)** - Benchmark harness settings
