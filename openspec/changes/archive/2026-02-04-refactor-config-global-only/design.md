# Design: Global-Only Config System

## Context

The config system has grown organically to support features (project configs, inheritance, two-tier fallback) that add complexity without clear usage. This refactor simplifies to a global-only model with all defaults in Pydantic models.

## Goals / Non-Goals

**Goals:**
- Reduce config module from ~1,838 to ~330 lines
- Single source of truth for defaults (Pydantic models)
- Maintain all essential runtime functionality
- Clean, testable code structure

**Non-Goals:**
- Support project-level configuration (can add later if needed)
- Backwards compatibility with `inherit:` directive
- Support for `tools.stats` legacy path

## Decisions

### 1. Global Config Only

**Decision:** Single config location `~/.onetool/config/onetool.yaml`

**Rationale:** Project configs add significant complexity (inheritance, merge logic, two-tier fallback) with minimal benefit. Global-only is sufficient for current use cases.

**Alternatives considered:**
- Keep project + global (current): Too complex for benefit
- Project-only: Loses shared config capability

### 2. Defaults in Pydantic Models

**Decision:** Embed all defaults directly in Pydantic model field definitions.

**Rationale:**
- Single source of truth
- Type-safe defaults
- No template file parsing at startup
- Easier to understand and maintain

**Example:**
```python
class SecurityConfig(BaseModel):
    builtins: BuiltinsConfig = Field(default_factory=lambda: BuiltinsConfig(
        allow=["str", "int", "len", ...]  # Defaults here, not in YAML
    ))
```

### 3. Simple Include System

**Decision:** Single-tier includes with depth limit (5) instead of circular detection.

**Rationale:**
- Simpler implementation (~10 lines vs ~30)
- Depth limit handles both circular and deep nesting
- Warning on missing include (no fallback)

### 4. Tool Config via extra="allow"

**Decision:** Use `extra="allow"` on `OneToolConfig.tools` dict instead of dynamic schema building.

**Rationale:**
- AST parsing of tool `Config` classes is complex (~121 lines)
- `get_tool_config(pack, schema)` validates at access time
- Tools define their own defaults in their `Config` class

### 5. Remove Compact Array Flattening

**Decision:** Remove nested array flattening for security config. Users must use flat lists.

**Rationale:**
- Simplifies model validation
- YAML format is clearer without nested arrays
- ~20 lines saved

**Migration:** Convert `[[a, b], c]` to `[a, b, c]` in config

### 6. Root-Level Env Section + Remove os.environ Fallback

**Decision:**
- Add root-level `env:` section for shared subprocess environment
- Remove `expand_subprocess_env()` - use `expand_secrets()` for `${VAR}` expansion

**Rationale:**
- Clear separation: `env:` for environment variables, `secrets.yaml` for secrets
- One place to configure env for all MCP servers
- No os.environ reading - explicit configuration only

**Config structure:**
```yaml
# onetool.yaml
env:
  HOME: /home/user
  LANG: en_US.UTF-8
  NODE_OPTIONS: --max-old-space-size=4096

servers:
  github:
    type: stdio
    command: npx
    env:
      GITHUB_TOKEN: ${GITHUB_TOKEN}  # Expanded from secrets.yaml
      # Inherits HOME, LANG from root env
```

**Subprocess env build order:**
1. Start with `PATH` from host (always needed for finding executables)
2. Merge root `env:` section
3. Merge server-specific `env:` section (overrides root)
4. Expand `${VAR}` in values from secrets.yaml only

**Migration:** Move env vars you were relying on os.environ for to the root `env:` section.

### 7. Clean Reload Pattern

**Decision:** Each module with cached state exposes a `reset()` function. The `ot.reload()` function calls these in dependency order.

**Current problem:** `ot.reload()` directly manipulates private attributes across 6+ modules:
```python
# Current - violates encapsulation
ot.config.loader._config = None
ot.config.secrets._secrets = None
ot.prompts._prompts = None
ot.registry._registry = None
ot.executor.tool_loader._module_cache.clear()
ot.executor.validator._get_tool_namespaces.cache_clear()
ot.executor.validator._get_security_config.cache_clear()
```

**Clean approach:** Each module owns its reset:
```python
# loader.py
def reset() -> None:
    """Clear config cache for reload."""
    global _config
    with _config_lock:
        _config = None

# secrets.py
def reset() -> None:
    """Clear secrets cache for reload."""
    global _secrets
    _secrets = None
```

Then `ot.reload()` becomes:
```python
def reload() -> str:
    # Clear in dependency order (config first, others depend on it)
    from ot.config import reset as reset_config
    from ot.config.secrets import reset as reset_secrets
    from ot import prompts, registry, proxy
    from ot.executor import validator, tool_loader

    reset_config()
    reset_secrets()
    prompts.reset()
    tool_loader.reset()
    registry.reset()
    validator.reset()

    # Reload and reconnect
    cfg = get_config()
    proxy.reconnect_proxy_manager()

    return "OK: Configuration reloaded"
```

**Benefits:**
- Encapsulation preserved - modules own their state
- Single responsibility - each module knows how to reset itself
- Easier to maintain - adding a cache doesn't require updating `ot.reload()`
- Testable - can reset individual modules in tests

## Target Structure

```
src/ot/config/
├── __init__.py       # Public API exports (~30 lines)
├── models.py         # All Pydantic models with embedded defaults (~150 lines)
├── loader.py         # YAML loading, includes, secrets expansion (~100 lines)
└── secrets.py        # Secrets cache (~50 lines)
```

Total: ~330 lines (down from 1,838)

## Files Removed

| File | Lines | Reason |
|------|-------|--------|
| dynamic.py | 121 | Replaced by `extra="allow"` |
| tool_config.py | 125 | Merged into loader.py |
| mcp.py | 149 | Merged into models.py |

## Risks / Trade-offs

**Risk:** Users with project configs must migrate
**Mitigation:** Clear error message, migration docs

**Risk:** Tool configs no longer validated at load time
**Mitigation:** `get_tool_config(pack, schema)` validates at access; most tools access config early

**Risk:** Compact array format users must update
**Mitigation:** Warning in changelog; simple manual conversion

## Migration Plan

1. Update spec with REMOVED/MODIFIED requirements
2. Implement new config module alongside old
3. Switch imports to new module
4. Remove old files
5. Update docs and templates

## Open Questions

None - design is straightforward simplification.
