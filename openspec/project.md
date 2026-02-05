# Project Context

## Purpose

OneTool is an MCP server exposing a single `run` tool for AI-assisted development. It addresses MCP's token bloat (~46K tokens for multiple tools, [96% reduction](../docs/data/compare.md)) by moving execution to a cheap LLM.

**Architecture**: `run request` → `LLM codegen` → `Host exec` → `Return` (~2K tokens, 1 call)

## What It Provides

**CLIs**: `onetool` (MCP server), `bench` (benchmarks)

**Built-in tools** in `src/ot_tools/`: `brave.*` (search), `web.*` (fetch), `ground.*` (Gemini), `context7.*` (docs), `code.*` (semantic search), `llm.*` (transform), `db.*` (database), `package.*` (versions), `ripgrep.*` (grep)

## Tech Stack

Python 3.11+, FastMCP, OpenAI SDK (OpenRouter), Typer, Pydantic, YAML config

## Conventions

- **Code**: Type hints, Google-style docstrings, Ruff linting
- **Testing**: pytest markers (`smoke`, `unit`, `integration`) + component markers (`core`, `serve`, `bench`)
- **Git**: Feature branches `feature/[change-id]`, conventional commits

## Configuration

**Resolution order (global-only)**: `ONETOOL_CONFIG` env var → `~/.onetool/config/onetool.yaml` → error (requires `onetool init`)

**Directory structure**: `.onetool/` uses subdirectories to organise files by purpose:

```text
~/.onetool/
├── config/     # YAML configuration files (onetool.yaml, secrets.yaml, etc.)
├── logs/       # Application log files
├── stats/      # Statistics data (stats.jsonl)
└── tools/      # Reserved for installed tool packs
```

**Locations**:
- Global config: `~/.onetool/config/onetool.yaml`
- Global secrets: `~/.onetool/config/secrets.yaml`
- Embedded defaults: Pydantic models in `src/ot/config/models.py`

**Variable expansion**: `${VAR}` in config files reads from `secrets.yaml` only (not environment variables). Use `${VAR:-default}` for defaults. Paths support `~` expansion only.

**Subprocess environment**: stdio MCP servers receive environment in this order:
1. `PATH` from host os.environ
2. Root-level `env:` section (shared across all servers)
3. Server-specific `env:` section (overrides root)
4. `${VAR}` expansion from secrets.yaml only

**Includes**: Config supports `include:` directive. Files resolve relative to `.onetool/` directory. Maximum depth: 5 levels.

Config includes `version` field for migrations. Current version: 1.

## Tool Development

1. Create `src/ot_tools/<name>.py` with `pack = "<name>"` and `__all__`
2. Use `LogSpan` for logging
3. Declare dependencies via `__onetool_requires__ = {"secrets": [...], "system": [...]}`
4. Add spec to `openspec/specs/tool-<name>/spec.md`

See `docs/ot-tools.md` for full guide.

## Dependencies

**Required**: Python 3.11+, uv, FastMCP

**Optional**: Brave API (`brave.*`), Context7 API (`context7.*`), Gemini API (`ground.*`), ripgrep (`ripgrep.*`)

## OpenSpec Workflow

Changes follow: Proposal → Specs → Tasks → Apply → Archive. See `openspec/AGENTS.md`.

## References

- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp) - token reduction research
- [Anthropic: Advanced Tool Use](https://www.anthropic.com/engineering/advanced-tool-use)

---

*Last Updated: 2026-01-26*
