# onetool CLI Specification

## Purpose

Defines the main `onetool` CLI. Provides the MCP server entry point and the `init` subcommand group for configuration management.

---

## Requirements

### Requirement: CLI Entry Point

The system SHALL provide a `onetool` CLI command.

#### Scenario: CLI invocation
- **GIVEN** the package is installed
- **WHEN** `onetool` is executed
- **THEN** it SHALL start the MCP server over stdio

#### Scenario: Help output
- **GIVEN** `onetool --help` is executed
- **WHEN** help is displayed
- **THEN** it SHALL list available options and subcommands with descriptions

#### Scenario: Version flag
- **GIVEN** `onetool --version` is executed
- **WHEN** executed
- **THEN** it SHALL display the package version

---

> **Terminology:** The **config dir** is the directory that contains `onetool.yaml`. All materialised files are written to this directory.

### Requirement: Init Guided Setup

The `onetool init` command SHALL guide users through selective config file materialisation rather than bulk-copying all templates.

The primary interface is `onetool init` (uses current directory) or `onetool init -c <path>` for an explicit path. No mandatory flags are required.

`--config` / `-c` uses suffix detection to determine intent:
- Path ending in `.yaml` or `.yml` → treated as the config file path; parent directory is the config dir
- Any other path → treated as the config directory; `onetool.yaml` is written inside it

Existing files in the target directory SHALL be backed up to `<filename>.bak` (or `<filename>.bak1`, `<filename>.bak2`, etc. to avoid collisions) before being overwritten, and a warning SHALL be printed.

#### Scenario: Init with no flags (interactive)
- **GIVEN** `onetool init` or `onetool init -c <path>` is run
- **AND** stdin is a TTY
- **WHEN** init runs
- **THEN** it SHALL first prompt the user to confirm or edit the resolved config file path (e.g. `Config file: onetool.yaml`)
  - The default shown is the fully-resolved `config_path`; pressing enter accepts it; typing a new path overrides it
  - Ctrl+C at this prompt cancels without writing any files
- **AND** it SHALL display a checkbox multi-select TUI listing all available extensions:
  - `prompts.yaml`, `servers.yaml`, `security.yaml`, `diagram.yaml`, `snippets.yaml`, `worktree.yaml`
- **AND** materialise only the extensions selected by the user
- **AND** write an `onetool.yaml` that includes only the materialised YAML files
- **AND** if the user cancels (Ctrl+C) at the checkbox, exit with code 0 without writing any files

#### Scenario: diagram.yaml sidecar directory
- **GIVEN** the user selects `diagram.yaml` during init
- **WHEN** init materialises `diagram.yaml`
- **THEN** it SHALL also copy the `diagram-templates/` directory from package templates into the config dir alongside `diagram.yaml`
- **AND** if `diagram-templates/` already exists it SHALL be backed up using the standard `.bak` scheme before overwriting

#### Scenario: Conflict handling
- **GIVEN** a file already exists in the target directory
- **WHEN** `onetool init` would overwrite it
- **THEN** the existing file SHALL be renamed to `<filename>.bak` (incrementing to `.bak1`, `.bak2`, etc. if needed)
- **AND** a warning SHALL be printed naming both the original and backup paths
- **AND** the new file SHALL be written to the original path

#### Scenario: Minimal output config
- **GIVEN** the user does not select any extensions during init (or stdin is not a TTY)
- **WHEN** init completes
- **THEN** the generated `onetool.yaml` SHALL contain only `version: 2` with no `include:` section

### Requirement: Init Validate Source Reporting

The `onetool init validate` command SHALL report the source of each resolved include.

#### Scenario: Validate shows include sources
- **GIVEN** `onetool init validate` is run
- **AND** some includes are user-owned and some use package defaults
- **WHEN** validation output is displayed
- **THEN** each include SHALL be listed with its source tag:
  - `[user]` — loaded from the config dir (`config_path.parent/<path>`)
  - `[default]` — loaded from `global_templates/<path>`
  - `[missing]` — listed in `include:` but not found in either location
  - `[absolute]` — resolved from an absolute path
  - `[not listed]` — not in `include:`, not loaded
- **AND** the resolved file path SHALL be shown for each loaded include

#### Scenario: Validate suggests materialisation
- **GIVEN** an include using a package default (`[default]` source)
- **WHEN** validation output is shown
- **THEN** it SHALL include a hint suggesting how to materialise the file locally to customise it
