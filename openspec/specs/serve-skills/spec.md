# serve-skills Specification

## Purpose

Defines the `ot.skills()` API for listing and retrieving bundled skill content at runtime. Skills are Markdown files stored in `global_templates/skills/` and returned on-demand to avoid embedding large reference content in the always-on MCP prompt.

## Requirements

### Requirement: Skills Listing

The system SHALL provide an `ot.skills()` function that lists available bundled skills.

#### Scenario: List all skills
- **WHEN** `ot.skills()` is called with no arguments
- **THEN** it SHALL return a formatted list of all bundled skills
- **AND** each entry SHALL include the skill name and description

#### Scenario: Filter by pattern
- **WHEN** `ot.skills(pattern="devtools")` is called
- **THEN** it SHALL return only skills whose name contains "devtools"

#### Scenario: Full info level
- **WHEN** `ot.skills(info="full")` is called
- **THEN** it SHALL return name, description, tags, and source path for each skill

#### Scenario: No skills match pattern
- **WHEN** `ot.skills(pattern="nonexistent")` is called
- **THEN** it SHALL return a message indicating no skills matched

### Requirement: Skill Content Retrieval

The system SHALL return the full body of a named skill via `ot.skills(name=...)`.

#### Scenario: Retrieve bundled skill
- **WHEN** `ot.skills(name="ot-guide")` is called
- **THEN** it SHALL return the full Markdown body of the skill (below the frontmatter)
- **AND** the body SHALL reflect the currently running server version

#### Scenario: Unknown skill name
- **WHEN** `ot.skills(name="does-not-exist")` is called
- **THEN** it SHALL return an error message listing available skill names

#### Scenario: Bundled skill content location
- **WHEN** a bundled skill is requested
- **THEN** it SHALL be read from `global_templates/skills/<name>.md`
- **AND** frontmatter (between `---` markers) SHALL be parsed and excluded from the returned body

### Requirement: Bundled Skill Set

The system SHALL bundle an initial set of skills for on-demand discovery and server guides.

#### Scenario: onetool-discover skill bundled
- **WHEN** `ot.skills()` is called
- **THEN** `ot-guide` SHALL be listed
- **AND** its content SHALL include discovery functions (`ot.help()`, `ot.tools()`, `ot.packs()`), error recovery patterns, security allowlist guidance, and output format/sanitisation controls

#### Scenario: devtools-guide skill bundled
- **WHEN** `ot.skills()` is called
- **THEN** `ot-chrome-devtools-mcp` SHALL be listed
- **AND** its content SHALL cover the Chrome DevTools MCP server tools, connection modes, and usage patterns

#### Scenario: playwright-guide skill bundled
- **WHEN** `ot.skills()` is called
- **THEN** `ot-playwright-mcp` SHALL be listed
- **AND** its content SHALL cover the Playwright MCP server tools and usage patterns

#### Scenario: github-guide skill bundled
- **WHEN** `ot.skills()` is called
- **THEN** `ot-github-mcp` SHALL be listed
- **AND** its content SHALL cover the GitHub MCP server tools and usage patterns
