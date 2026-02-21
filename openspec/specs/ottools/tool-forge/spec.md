# tool-forge Specification

## Purpose

Provides the `ot_forge` pack for creating and validating in-process extension tools, and installing skill stubs for AI tools. All extensions use the single in-process `extension` template with full `ot.*` access.

## Requirements

### Requirement: Create Extension Function

The ot_forge pack SHALL provide a `create_ext()` function to create new extensions.

#### Scenario: Create project extension
- **WHEN** `ot_forge.create_ext(name="mypack")` is called
- **THEN** it creates `.onetool/tools/mypack/mypack.py`
- **AND** uses the `extension` template (in-process, full `ot.*` access)
- **AND** substitutes `{{pack}}`, `{{function}}`, `{{description}}` placeholders

#### Scenario: Custom function name
- **WHEN** `ot_forge.create_ext(name="mypack", function="search")` is called
- **THEN** the generated file has `def search(...)` instead of `def run(...)`

#### Scenario: Extension already exists
- **WHEN** `ot_forge.create_ext(name="mypack")` is called
- **AND** `.onetool/tools/mypack/mypack.py` already exists
- **THEN** it returns an error message without overwriting

#### Scenario: Next steps guidance
- **WHEN** an extension is successfully created
- **THEN** the return value includes guidance referencing `ot_forge.validate_ext`, `ot.reload()`, and the new function

### Requirement: Validate Extension Function

The ot_forge pack SHALL provide a `validate_ext()` function for pre-reload validation.

#### Scenario: Valid extension
- **WHEN** `ot_forge.validate_ext(path="/path/to/extension.py")` is called
- **AND** the extension has valid syntax and required structure
- **THEN** it returns "Validation PASSED" with any warnings

#### Scenario: Syntax error
- **WHEN** `ot_forge.validate_ext(path="/path/to/extension.py")` is called
- **AND** the file has a Python syntax error
- **THEN** it returns an error with line number and message

#### Scenario: Missing required structure
- **WHEN** `ot_forge.validate_ext(path="/path/to/extension.py")` is called
- **AND** the file is missing `pack` or `__all__`
- **THEN** it returns "Validation FAILED" with errors

#### Scenario: Warn about deprecated ot_sdk imports
- **WHEN** `ot_forge.validate_ext(path="/path/to/tool.py")` is called
- **AND** the file imports from `ot_sdk`
- **THEN** it includes a DEPRECATED warning in the result

#### Scenario: Best practices warnings
- **WHEN** `ot_forge.validate_ext(path="/path/to/extension.py")` is called
- **AND** the file violates best practices (pack after imports, missing logging)
- **THEN** it includes warnings in the result but still passes

### Requirement: Extension Template Structure

The extension template SHALL include all required components for in-process execution with full onetool access.

#### Scenario: Extension template uses ot.* imports
- **WHEN** the extension template is used
- **THEN** the generated file imports from `ot.logging`, `ot.config`

#### Scenario: Extension template includes logging
- **WHEN** the extension template is used
- **THEN** the generated function uses `with LogSpan(...) as s:` pattern
- **AND** imports `LogSpan` from `ot.logging`

### Requirement: Template Location

The extension template SHALL be stored in the bundled config defaults directory.

#### Scenario: Template discovery
- **WHEN** `create_ext()` looks for the template
- **THEN** it uses `get_global_templates_dir() / "tool_templates" / "extension.py"`

### Requirement: Install Skill Stub Function

The ot_forge pack SHALL provide an `install_skill()` function to install skill stubs for AI tools.

#### Scenario: Install stub for Claude Code (default)
- **WHEN** `ot_forge.install_skill(install="ot-guide")` is called
- **THEN** it SHALL write a stub file to `.claude/skills/ot-guide/SKILL.md`
- **AND** the stub SHALL instruct the agent to call `>>> ot.skills(name="ot-guide")`

#### Scenario: Install stub for Codex
- **WHEN** `ot_forge.install_skill(install="ot-chrome-devtools-mcp", tool="codex")` is called
- **THEN** it SHALL write a stub file to `.codex/skills/ot-chrome-devtools-mcp/SKILL.md`

#### Scenario: Install stub for OpenCode
- **WHEN** `ot_forge.install_skill(install="ot-playwright-mcp", tool="opencode")` is called
- **THEN** it SHALL write a stub file to `.opencode/skills/ot-playwright-mcp/SKILL.md`

#### Scenario: Install all stubs
- **WHEN** `ot_forge.install_skill(install="all")` is called
- **THEN** it SHALL install stubs for all bundled skills
- **AND** default tool SHALL be `"claude"`

#### Scenario: Stub already installed
- **WHEN** `ot_forge.install_skill(install="ot-guide")` is called
- **AND** the stub file already exists
- **THEN** it SHALL overwrite the existing stub
- **AND** report that it was updated

#### Scenario: Unknown skill name
- **WHEN** `ot_forge.install_skill(install="unknown-skill")` is called
- **THEN** it SHALL return an error message listing available skill names

#### Scenario: Unsupported tool
- **WHEN** `ot_forge.install_skill(install="ot-guide", tool="unknown-tool")` is called
- **THEN** it SHALL return an error message listing supported tools

### Requirement: Stub File Format

Skill stub files SHALL use a unified frontmatter format with `name:` and `description:` fields.

#### Scenario: Stub frontmatter format (all tools)
- **WHEN** a stub is installed for any supported tool
- **THEN** the file SHALL have YAML frontmatter with both `name:` and `description:` fields
- **AND** the body SHALL contain a single instruction to call `>>> ot.skills(name="<name>")`

### Requirement: Tool Path Configuration

Stub installation paths SHALL be driven by configuration in `global_templates/skills.md`.

#### Scenario: Path config read from skills.md
- **WHEN** `ot_forge.install_skill()` resolves the installation path
- **THEN** it SHALL read the path template from `global_templates/skills.md` for the specified tool
- **AND** substitute `{name}` with the skill name

### Requirement: ot.packs() Extension Visibility

The `ot.packs()` function SHALL identify user extension packs and expose their file path.

#### Scenario: Extension pack marked in packs listing
- **WHEN** `ot.packs()` is called
- **AND** a user extension pack is loaded from `tools_dir`
- **THEN** the pack entry SHALL include `is_extension: true`
- **AND** SHALL include `path` with the full path to the extension file

#### Scenario: Built-in local pack not marked as extension
- **WHEN** `ot.packs()` is called
- **AND** a bundled local pack is listed (e.g. `ot`, `ripgrep`)
- **THEN** the pack entry SHALL NOT include `is_extension`
