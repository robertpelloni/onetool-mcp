# Changelog

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
- **Batteries Included** - 15 packs, 100+ tools ready to use
- **Security First** - AST validation, configurable policies, path boundaries

### Changes
- add persistent memory tool
- fix github mcp by implementing streamable HTTP transport
- add proxy server discovery and instructions. Enable chrome-devtools and github mcp by default
- add transform_file and data param
- remove code_search tool
- remove timed tool
