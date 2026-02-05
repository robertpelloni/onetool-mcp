# Configuration

OneTool uses YAML configuration files stored in the global directory (`~/.onetool/config/`).

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

## Security Configuration

OneTool uses an allowlist-based security model. Everything is blocked by
default; you must explicitly allow what's safe.

Include `security.yaml` in your config (paths resolve from `.onetool/` directory):

```yaml
include:
  - config/security.yaml  # Resolves to ~/.onetool/config/security.yaml
```

Or define inline:

```yaml
security:
  builtins:
    allow:
      - [str, int, float, list, dict, set, tuple]  # Types
      - [len, range, enumerate, zip, sorted]       # Iteration
      - [print, repr, format]                      # Output
  imports:
    allow: [json, re, math, datetime, collections]
    warn: [yaml]
  calls:
    block: [pickle.*, yaml.load]
  dunders:
    allow: [__format__, __sanitize__]
```

Tool namespaces (`ot.*`, `brave.*`, `file.*`, etc.) are auto-allowed.

### Checking Security Rules

Use introspection to check what's allowed:

```python
ot.security()                    # Summary of all rules
ot.security(check="json")        # Check specific pattern
ot.security(check="pickle.load") # Check qualified call
```

## Reference

- **[onetool Configuration](../reference/cli/onetool-config.md)** - Full YAML schema, pack settings, secrets, MCP servers, aliases, snippets, security
- **[bench Configuration](../reference/cli/bench.md#configuration)** - Benchmark harness settings
