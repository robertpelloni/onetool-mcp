# Changelog

## [Unreleased]

### Breaking Changes

- **Configuration System Simplification**: Refactored config system to global-only
  - Removed project-level configuration support (`.onetool/config/onetool.yaml` in projects)
  - Removed `inherit:` directive from configuration files
  - Removed two-tier include fallback (includes now resolve from `.onetool/` only)
  - Removed `OT_CWD` environment variable for config resolution
  - Replaced circular detection with depth limit (5 levels) for includes
  - Config now loads only from `~/.onetool/config/onetool.yaml` or `ONETOOL_CONFIG` env var

### Features

- Added root-level `env:` section in config for shared environment variables across MCP servers
- Embedded all security defaults in Pydantic models (single source of truth)
- Added clean reload pattern with `reset()` functions for config, secrets, prompts, registry

### Improvements

- Reduced config module code from 1,838 lines to ~1,470 lines
- Simplified config resolution logic (no inheritance, no fallbacks)
- Better encapsulation with module-level reset functions
- Improved environment variable merging: PATH → root env → server env → secrets expansion

### Migration Guide

If you were using project-level configuration:
1. Move all config from `.onetool/config/onetool.yaml` to `~/.onetool/config/onetool.yaml`
2. Remove any `inherit:` directives from your config files
3. Update include paths to be relative to `.onetool/` instead of `.onetool/config/`
4. Move any project-specific environment variables to the root-level `env:` section

## [1.0.0rc2] - 2026-02-03

### Highlights

- add proxy server discovery and instructions. Enable chrome-devtools and github mcp by default.
- add transform_file and data param
- implement new security model - category-based allowlists in security.yaml
- remove firecrawl tool pack and docs
- require Python 3.12 and update tooling
- reorganize docs

## [1.0.0b1] - 2026-01-24

### Highlights

- **Stop Context Rot** - 98.7% token reduction (150K to 2K)
- **Explicit Calls** - Five trigger prefixes, three invocation styles
- **Configurable Everything** - Per-tool timeouts, limits, behavior
- **Batteries Included** - 15 packs, 100+ tools ready to use
- **Security First** - AST validation, configurable policies, path boundaries