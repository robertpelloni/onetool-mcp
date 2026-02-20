# onetool CLI Specification

## Purpose

Defines the main `onetool` CLI for configuration management utilities. Provides commands for upgrading config files, checking dependencies, and displaying current configuration.

---

## Requirements

### Requirement: CLI Entry Point

The system SHALL provide a `onetool` CLI command.

#### Scenario: CLI invocation
- **GIVEN** the package is installed
- **WHEN** `onetool` is executed
- **THEN** it SHALL display available subcommands

#### Scenario: Help output
- **GIVEN** `onetool --help` is executed
- **WHEN** help is displayed
- **THEN** it SHALL list all available subcommands with descriptions

---

### Requirement: Config Display

The system SHALL display the current configuration.

#### Scenario: Show merged config
- **GIVEN** `onetool config show` is executed
- **WHEN** configuration files exist
- **THEN** it SHALL display the merged configuration as YAML
- **AND** indicate which values came from which source (default, file, env)

#### Scenario: Show config path
- **GIVEN** `onetool config path` is executed
- **WHEN** executed
- **THEN** it SHALL display the resolved config file path

#### Scenario: Validate config
- **GIVEN** `onetool config validate` is executed
- **WHEN** a config file exists
- **THEN** it SHALL validate the configuration against the schema
- **AND** report any errors or warnings

---

### Requirement: Config Upgrade

The system SHALL support upgrading config files to newer schema versions.

#### Scenario: Upgrade config file
- **GIVEN** `onetool config upgrade` is executed
- **WHEN** an older config version is detected
- **THEN** it SHALL migrate settings to the current schema
- **AND** create a backup of the original file

#### Scenario: Dry run upgrade
- **GIVEN** `onetool config upgrade --dry-run` is executed
- **WHEN** an older config version is detected
- **THEN** it SHALL display what changes would be made
- **AND** NOT modify any files

#### Scenario: No upgrade needed
- **GIVEN** `onetool config upgrade` is executed
- **WHEN** the config is already at the current version
- **THEN** it SHALL report that no upgrade is needed

---

### Requirement: Dependency Check

The system SHALL check tool dependencies and report their status.

#### Scenario: Check all dependencies
- **GIVEN** `onetool check` is executed
- **WHEN** tools have external dependencies
- **THEN** it SHALL check each dependency (ripgrep, playwright, etc.)
- **AND** report status as available, missing, or outdated

#### Scenario: Check specific tool
- **GIVEN** `onetool check --tool ripgrep` is executed
- **WHEN** the tool has dependencies
- **THEN** it SHALL check only that tool's dependencies

#### Scenario: Install missing dependencies
- **GIVEN** `onetool check --install` is executed
- **WHEN** dependencies are missing
- **THEN** it SHALL attempt to install them
- **AND** report success or failure for each

---

### Requirement: Version Information

The system SHALL display version information.

#### Scenario: Show version
- **GIVEN** `onetool version` is executed
- **WHEN** executed
- **THEN** it SHALL display:
  - Package version
  - Python version
  - Installation path

#### Scenario: Version flag
- **GIVEN** `onetool --version` is executed
- **WHEN** executed
- **THEN** it SHALL display the package version

---

> **Terminology:** The **config dir** is `config_path.parent` — the directory that contains `onetool.yaml`, passed via `--config`. This is conventionally named `.onetool/` but the code treats it as `config_path.parent`; all materialised files are written to `config_path.parent`, not to a hardcoded `.onetool/` path.

### Requirement: Init Guided Setup

The `onetool init` command SHALL guide users through selective config file materialisation rather than bulk-copying all templates.

#### Scenario: Init with no flags (interactive)
- **GIVEN** `onetool init` is run with no flags
- **AND** stdin is a TTY
- **WHEN** init runs
- **THEN** it SHALL ask: "Configure security rules? [y/N]"
- **AND** ask: "Include proxy servers? (chrome-devtools, playwright, github, none) [none]"
- **AND** materialise only the files corresponding to the user's choices
- **AND** write an `onetool.yaml` that includes only those materialised files

#### Scenario: Init with --security flag
- **GIVEN** `onetool init --security` is run
- **WHEN** init runs
- **THEN** it SHALL materialise `security.yaml` into the config dir (`config_path.parent`) from the package default
- **AND** add `security.yaml` to `include:` in the generated `onetool.yaml`

#### Scenario: Init with --servers flag
- **GIVEN** `onetool init --servers chrome-devtools,playwright` is run
- **WHEN** init runs
- **THEN** it SHALL materialise `servers.yaml` into the config dir, containing only the `chrome-devtools` and `playwright` server blocks
- **AND** add `servers.yaml` to `include:` in the generated `onetool.yaml`

#### Scenario: Init with --file flag
- **GIVEN** `onetool init --file security.yaml` is run
- **WHEN** init runs
- **THEN** it SHALL materialise only `security.yaml` into the config dir from the package default
- **AND** print a message explaining that the file is now user-owned and will override the package default

#### Scenario: Init with --full flag
- **GIVEN** `onetool init --full` is run
- **WHEN** init runs
- **THEN** it SHALL copy all global_templates YAML files into the config dir (`config_path.parent`)
- **AND** generate an `onetool.yaml` that includes all materialised files

#### Scenario: Minimal output config
- **GIVEN** the user does not select security or servers during init
- **WHEN** init completes
- **THEN** the generated `onetool.yaml` SHALL contain only `version: 2` with no `include:` section
- **AND** a message SHALL inform the user that package defaults will be used for security and that no servers are configured

#### Scenario: Init output informs about defaults
- **GIVEN** `onetool init --security` is run
- **WHEN** init completes
- **THEN** output SHALL state which files were materialised
- **AND** for non-materialised files, SHALL note that package defaults will be used via fallback

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
- **THEN** it SHALL include a hint: "Run `onetool init --file <name>` to customise"
