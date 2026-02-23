# Changelog

## [1.1.0] - 2026-02-18

### Added
- `[util]` extra: file, excel, convert, brave, ground tool packs
- `[dev]` extra: db, ripgrep, web, diagram, package, context7 tool packs
- `[all]` convenience extra
- `--secrets` flag on `onetool serve`
- AST-based ToolRegistry with change detection
- `log_callback` on LogSpan for external telemetry
- JSON auto-parsing for proxy tool responses
- `file` tool: dry_run, symlinks, include_hidden, recursive delete, encoding

### Changed
- Global config location: `~/.onetool/onetool.yaml` (was `~/.onetool/config/onetool.yaml`)
- Server starts with defaults if no config found — `onetool init` no longer required

### Removed
- `ConfigNotFoundError` — replaced by graceful defaults
- `OT_GLOBAL_DIR` env override — single config location
- `[file]` standalone extra — folded into `[util]`

## [1.0.2] - 2026-02-16

### Highlights
- add automatic tool name aliasing for non-Python-friendly names
- add devtools_util and playwright_util browser annotation packs; add chrome devtools guide

### Fixed
- expand env vars from secrets for stdio MCP servers; add inherit_env option

## [1.0.1] - 2026-02-10

### Highlights
- **Mem Tool** - 11-13x faster than accessing files directly and improved user experience
- **Agent Hints** - Agents now can get help on using OneTool via add ot.agent_hints()
- **Timer Pack** - Timer tool pack to measure elapsed time
- **Dev Docs** - Architecture, coding standards, etc now all documented for agents and contributors

### Changes
- add mem.grep regex search; update prompts and guides

## [1.0.0] - 2026-02-09

### Highlights
- **Stop Context Rot** - 98.7% token reduction (150K to 2K)
- **Explicit Calls** - Five trigger prefixes, three invocation styles
- **Configurable Everything** - Per-tool timeouts, limits, behavior
- **Batteries Included** - 15+ packs, 100+ tools ready to use
- **Security First** - AST validation, configurable policies, path boundaries

### Changes
- add persistent memory tool
- fix github mcp by implementing streamable HTTP transport
- add proxy server discovery and instructions. Enable chrome-devtools and github mcp by default
- add transform_file and data param
- remove code_search tool
- remove timed tool
