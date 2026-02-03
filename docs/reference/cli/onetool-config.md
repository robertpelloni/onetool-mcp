# onetool Configuration

Complete reference for `onetool.yaml` configuration.

## Two-Tier System

```text
┌──────────────────┐     ┌──────────────────┐
│     Global       │ --> │    Project       │
│  (~/.onetool/)   │     │ (cwd/.onetool/)  │
└──────────────────┘     └──────────────────┘
   User preferences        Project overrides
```

| Location | Purpose | Scope |
|----------|---------|-------|
| `~/.onetool/config/onetool.yaml` | Global config | User |
| `.onetool/config/onetool.yaml` | Project config | Project |

**Resolution order:** CLI flags → `ONETOOL_CONFIG` env var → project → global

**Windows paths:** Replace `~/.onetool/` with `%USERPROFILE%\.onetool\`

## First Run Bootstrap

On first `onetool` invocation, OneTool creates `~/.onetool/` with default configs:

```bash
$ onetool --help
Creating ~/.onetool/
  ✓ config/
  ✓ logs/
  ✓ stats/
  ✓ tools/
  ✓ config/onetool.yaml
  ✓ config/snippets.yaml
  ✓ config/servers.yaml
  ✓ config/secrets.yaml
  ✓ config/prompts.yaml
  ✓ config/security.yaml
  ✓ config/diagram.yaml
  ✓ config/bench.yaml
  ✓ config/bench-secrets.yaml
  ✓ config/diagram-templates/
```

Manage manually:

```bash
onetool init           # Create ~/.onetool/ (if missing)
onetool init reset     # Reset to defaults (prompts per file, offers backups)
onetool init validate  # Check for errors
```

## Configuration Inheritance

Project configs can inherit from global config:

```yaml
version: 1
inherit: global  # global (default) or none

tools_dir:
  - ./tools/*.py
```

| Value | Behaviour |
|-------|-----------|
| `global` (default) | Merge global config first, project overrides |
| `none` | No inheritance, use project config as-is |

**Merge semantics:**

- Nested dicts are deep-merged (partial overrides work)
- Lists and scalars are replaced entirely

## YAML Schema

```yaml
version: 1                    # Config schema version (required)

include:                      # External config files to merge
  - prompts.yaml
  - snippets.yaml
  - servers.yaml

tools_dir:                    # Tool discovery patterns
  - src/ot_tools/*.py

log_level: INFO               # DEBUG, INFO, WARNING, ERROR

security:                     # Code validation settings
  validate_code: true
  enabled: true

projects: {}                  # Named project paths
servers: {}                   # External MCP servers
tools: {}                     # Pack-specific configuration
alias: {}                     # Function aliases
snippets: {}                  # Reusable code templates
prompts: {}                   # Inline prompts (overrides included)
```

## Config Includes

Compose configuration from multiple files:

```yaml
version: 1

include:
  - config/prompts.yaml     # Relative to OT_DIR (.onetool/)
  - config/snippets.yaml
  - local-snippets.yaml     # Project-only additions

servers:
  local_dev:
    type: stdio
    command: python
```

**Include resolution (two-tier fallback):**

1. OT_DIR (project `.onetool/` or wherever the config is)
2. Global (`~/.onetool/`)

**Merge behaviour:**

- Files are merged left-to-right (later files override earlier)
- Inline content in the main file overrides everything

## Pack Configuration Reference

| Pack | Field | Type | Default | Range | Description |
|------|-------|------|---------|-------|-------------|
| brave | timeout | float | 60.0 | 1-300 | API request timeout (seconds) |
| code | base_url | string | https://openrouter.ai/api/v1 | - | Embedding API base URL |
| code | content_limit | int | 500 | 100-10K | Content preview character limit |
| code | content_limit_expanded | int | 2000 | 500-20K | Expanded content character limit |
| code | db_path | string | .chunkhound/chunks.db | - | Chunks database path |
| code | dimensions | int | 1536 | - | Embedding dimensions |
| code | limit | int | 10 | 1-100 | Max search results |
| code | model | string | text-embedding-3-small | - | Embedding model |
| code | provider | string | openai | - | Embedding provider |
| context7 | docs_limit | int | 10 | 1-20 | Max documentation results |
| context7 | timeout | float | 30.0 | 1-120 | API request timeout (seconds) |
| db | max_chars | int | 4000 | 100-100K | Query output truncation |
| ground | model | string | gemini-2.5-flash | - | Gemini model for grounding |
| package | timeout | float | 30.0 | 1-120 | Registry request timeout |
| ripgrep | relative_paths | bool | true | - | Use relative paths in output |
| ripgrep | timeout | float | 60.0 | 1-300 | Search timeout (seconds) |
| stats | chars_per_token | float | 4.0 | ≥1.0 | Characters per token estimate |
| stats | context_per_call | int | 30000 | ≥0 | Context tokens saved per call |
| stats | cost_per_million_input_tokens | float | 15.0 | ≥0 | Input token cost (USD) |
| stats | cost_per_million_output_tokens | float | 75.0 | ≥0 | Output token cost (USD) |
| stats | enabled | bool | true | - | Enable statistics collection |
| stats | flush_interval_seconds | int | 30 | 1-300 | Disk flush interval |
| stats | model | string | anthropic/claude-opus-4.5 | - | Model for cost estimation |
| stats | persist_dir | string | stats | - | Stats directory path |
| stats | persist_path | string | stats.jsonl | - | Stats file path |
| stats | time_overhead_per_call_ms | int | 4000 | ≥0 | Time overhead saved (ms) |
| transform | base_url | string | "" | - | OpenAI-compatible API base URL |
| transform | max_tokens | int | null | - | Max output tokens (null=no limit) |
| transform | model | string | "" | - | Model for transformations |
| transform | timeout | int | 30 | - | API timeout in seconds |
| web | max_length | int | 50000 | 1K-500K | Max content characters |
| web | timeout | float | 30.0 | 1-120 | Page fetch timeout (seconds) |

Example:

```yaml
tools:
  brave:
    timeout: 120.0
  context7:
    timeout: 60.0
    docs_limit: 20
  db:
    max_chars: 8000
```

## Projects Configuration

Named projects for path resolution and attributes:

```yaml
projects:
  myapp:
    path: /path/to/myapp
    attrs:
      db_url: postgresql://localhost/myapp
      api_key: ${MY_API_KEY}

  demo:
    path: .
    attrs:
      db_url: sqlite:///demo/db/northwind.db
```

## Secrets Configuration

API keys stored separately in `secrets.yaml` (gitignored):

| Location | Purpose | Scope |
|----------|---------|-------|
| `.onetool/config/secrets.yaml` | Project secrets | Project |
| `~/.onetool/config/secrets.yaml` | Global secrets | User |

**Resolution:** `OT_SECRETS_FILE` env var → project → global

```yaml
# API keys for tools (values are literal, no ${VAR} expansion)
BRAVE_API_KEY: "your-brave-api-key"
OPENAI_API_KEY: "sk-..."
CONTEXT7_API_KEY: "your-context7-key"
GEMINI_API_KEY: "your-gemini-key"
DATABASE_URL: "postgresql://user:pass@localhost/db"
```

### Accessing Secrets in Tools

```python
from ot.config.secrets import get_secret

api_key = get_secret("BRAVE_API_KEY")
if not api_key:
    return "Error: BRAVE_API_KEY not configured in secrets.yaml"
```

## External MCP Servers

Proxy external MCP servers through OneTool:

```yaml
servers:
  github:
    type: stdio
    command: npx
    args: ["-y", "@anthropic-ai/github-mcp-server@latest"]
    timeout: 30

  chrome-devtools:
    type: stdio
    command: npx
    args: ["-y", "@anthropic-ai/chrome-devtools-mcp@latest"]
```

## Aliases

Short names for common tool functions:

```yaml
alias:
  ws: brave.web_search
  ns: brave.news
  wf: web.fetch
```

## Snippets

Reusable code templates with Jinja2 substitution:

```yaml
snippets:
  multi_search:
    description: Search multiple queries
    params:
      queries: { required: true, description: "List of queries" }
    body: |
      results = []
      for q in {{ queries }}:
          results.append(brave.web_search(query=q))
      "\n---\n".join(results)
```

External snippet files:

```yaml
include:
  - config/snippets.yaml       # Falls back to global
  - local-snippets.yaml        # Project-specific additions

snippets:
  custom:
    body: "demo.foo()"         # Inline overrides included
```

## Statistics Configuration

Track runtime statistics:

```yaml
stats:
  enabled: true
  persist_dir: stats
  persist_path: stats.jsonl
  flush_interval_seconds: 30
  context_per_call: 30000
  time_overhead_per_call_ms: 4000
  model: anthropic/claude-opus-4.5
  cost_per_million_input_tokens: 15.0
  cost_per_million_output_tokens: 75.0
  chars_per_token: 4.0
```

View with `ot.stats()`:

```python
ot.stats()                           # All-time
ot.stats(period="day")               # Last 24 hours
ot.stats(period="week", tool="brave.search")
ot.stats(output="stats_report.html") # HTML report
```

## Transform Configuration

Configure the `llm.transform()` tool for LLM-powered text transformations:

```yaml
tools:
  transform:
    model: "gpt-4o-mini"                    # Model for transformations
    base_url: "https://api.openai.com/v1"   # OpenAI-compatible API endpoint
    max_tokens: 4096                        # Max output tokens
```

Requires `OPENAI_API_KEY` in secrets.yaml (or compatible provider key).

## Message Configuration

Configure `ot.notify()` topic-to-file routing:

```yaml
tools:
  msg:
    topics:
      - pattern: "status:*"           # Glob-style topic pattern
        file: "~/.onetool/status.log" # Output file (supports ~ and ${VAR})
      - pattern: "doc:*"
        file: "./docs/notes.md"
```

Messages are appended to matching files. First pattern match wins.

## Output Configuration

Control large output handling:

```yaml
output:
  max_inline_size: 50000      # Threshold in bytes (0 to disable)
  result_store_dir: tmp       # Directory for stored results
  result_ttl: 3600            # Time-to-live in seconds
  preview_lines: 10           # Lines in summary preview
```

When output exceeds `max_inline_size`, OneTool stores the result and returns a handle. Query with `ot.result(handle="...")`.

## Security Configuration

OneTool uses an **allowlist-based** security model: everything is blocked by default, you explicitly allow what's safe. Tool namespaces (`ot.*`, `brave.*`, etc.) are auto-allowed.

Security rules are defined in `security.yaml` (included by default):

```yaml
security:
  validate_code: true          # Enable AST validation
  enabled: true                # Enable security checks

  builtins:
    allow:
      - [str, int, float, list, dict, set, tuple]  # Types
      - [len, range, enumerate, zip, sorted]       # Iteration
      - [print, repr, format]                      # Output

  imports:
    allow: [json, re, math, datetime, collections, itertools]
    warn: [yaml]               # Allowed but logs warning

  calls:
    block: [pickle.*, yaml.load]  # Blocked qualified calls
    warn: [random.seed]           # Warned qualified calls

  dunders:
    allow: [__format__, __sanitize__]  # Allowed magic variables

  sanitize:
    enabled: true              # Output sanitization (prompt injection protection)
```

**Compact array format:** Group related items for readability:

```yaml
allow:
  - [str, int, float]  # Grouped items
  - print              # Single item
```

### Security Introspection

Check what's allowed at runtime:

```python
ot.security()                    # Summary of all rules
ot.security(check="json")        # Check specific pattern
ot.security(check="pickle.load") # Check qualified call
```

### Output Sanitization

The `security.sanitize` subsection protects against indirect prompt injection by sanitizing tool outputs:

1. **Trigger sanitization:** Replace `__ot`, `mcp__onetool` patterns
2. **Tag sanitization:** Remove `<external-content-*>` patterns
3. **GUID-tagged boundaries:** Wrap content in unpredictable tags

Disable per-call with `__sanitize__ = False` prefix.

See [Security Model](../../learn/security.md) for full documentation.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ONETOOL_CONFIG` | Config file path override |
| `OT_LOG_LEVEL` | Log level (DEBUG/INFO/WARNING/ERROR) |
| `OT_LOG_VERBOSE` | Enable verbose logging (true/false) |
| `OT_LOG_DIR` | Log directory path |
| `OT_SECRETS_FILE` | Secrets file path override |
| `OT_COMPACT_MAX_LENGTH` | Max value length in compact output |

## Environment Variable Expansion

Config values support `${VAR}` and `${VAR:-default}` syntax:

```yaml
projects:
  myapp:
    path: ${HOME}/projects/myapp
    attrs:
      db_url: ${DATABASE_URL:-sqlite:///local.db}
```

## Validation

Invalid values are rejected at load time:

```
ValueError: Invalid configuration in config/onetool.yaml:
  tools.brave.timeout: Input should be greater than or equal to 1
```

## Example Configurations

### Minimal

```yaml
version: 1
tools_dir:
  - src/ot_tools/*.py
```

### Production

```yaml
version: 1

tools_dir:
  - src/ot_tools/*.py

log_level: WARNING

security:
  validate_code: true

tools:
  brave:
    timeout: 120.0
  context7:
    timeout: 60.0
    docs_limit: 20
  db:
    max_chars: 8000
  ripgrep:
    timeout: 120.0

projects:
  app:
    path: /srv/myapp
    attrs:
      db_url: ${DATABASE_URL}
```
