# Forge

Create, validate, and install extension tools and skill stubs.

## Highlights

- Single in-process extension template with full `ot.*` access
- Validation before reload catches errors early
- Best practices checking and warnings
- Skill stub installation for Claude, Codex, and OpenCode

## Functions

| Function | Description |
|----------|-------------|
| `ot_forge.create_ext(name, ...)` | Create a new in-process extension tool |
| `ot_forge.validate_ext(path)` | Validate an extension before reload |
| `ot_forge.install_skill(install, ...)` | Install a skill stub for an AI tool |

## Key Parameters

### create_ext

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | str | Extension name (used as directory and file name) |
| `pack_name` | str | Pack name for dot notation (default: same as name) |
| `function` | str | Main function name (default: `run`) |
| `description` | str | Module description |

### validate_ext

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | str | Full path to the extension file |

### install_skill

| Parameter | Type | Description |
|-----------|------|-------------|
| `install` | str | Skill name to install, or `"all"` for all skills |
| `tool` | str | Target AI tool: `"claude"` (default), `"codex"`, `"opencode"` |

## Requires

No API key required.

## Workflow

The recommended workflow for creating and activating extensions:

```text
ot_forge.create_ext(name) → (edit) → ot_forge.validate_ext(path) → ot.reload() → use
```

## Examples

```python
# Create a new extension
ot_forge.create_ext(name="my_tool", function="search")

# Validate before reload
ot_forge.validate_ext(path=".onetool/tools/my_tool/my_tool.py")

# List available skills (use ot.skills, not ot_forge)
ot.skills()

# Install a skill stub for Claude Code
ot_forge.install_skill(install="ot-guide")

# Install for a different AI tool
ot_forge.install_skill(install="ot-chrome-devtools-mcp", tool="codex")

# Install all skills at once
ot_forge.install_skill(install="all")
```
