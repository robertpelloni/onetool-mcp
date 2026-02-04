# Change: Refactor Config System to Global-Only

## Why

The current config system is 1,838 lines across 6 files with complex features (project-level config, inheritance, two-tier include fallback, dynamic tool config discovery) that are not used in practice. A clean-room rewrite targeting global-only configuration reduces this to ~330 lines while maintaining essential functionality.

## What Changes

- **BREAKING**: Remove `inherit: global|none` directive (project configs will not inherit)
- **BREAKING**: Remove two-tier include fallback (project -> global) - single-tier only
- **BREAKING**: Remove `OT_CWD` from config resolution (global-only)
- **BREAKING**: Remove project config resolution (cwd/.onetool/) - global only
- **BREAKING**: Remove `tools.stats` legacy path (root-level only)
- **BREAKING**: Remove dynamic tool config discovery via AST - use `extra="allow"` instead
- **BREAKING**: Remove compact array flattening for security config - flat lists only
- Remove version migration warnings (just error on incompatible)
- Remove circular include detection (use depth limit instead)
- Embed all default values in Pydantic models (no separate template files as default sources)
- Consolidate from 6 files (~1,838 lines) to 4 files (~330 lines)
- Clean reload pattern: each module exposes `reset()` instead of `ot.reload()` accessing private attributes
- **BREAKING**: Remove `expand_subprocess_env()` - use `expand_secrets()` for subprocess env (no os.environ fallback)
- Add root-level `env:` section for shared subprocess environment variables

## Impact

- Affected specs: `serve-configuration`
- Affected code: `src/ot/config/` (all files)
- Migration: Users must use `~/.onetool/config/onetool.yaml` only; remove `inherit:` field from configs

## Rationale

1. **Global-only simplifies significantly**: No project/global merge logic, no inheritance system
2. **Pydantic defaults are canonical**: Single source of truth instead of YAML templates + code
3. **Include depth limit vs circular detection**: Simpler, same practical effect
4. **Tool config via `extra="allow"`**: Tools define their own defaults; YAML just overrides
