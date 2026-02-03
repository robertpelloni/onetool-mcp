# serve-configuration Spec Delta

## MODIFIED Requirements

### Requirement: YAML Configuration File

The system SHALL load configuration from a YAML file using a standard resolution order, requiring initialization if no config exists.

#### Scenario: Default configuration file resolution
- **GIVEN** no explicit config path provided
- **AND** no `ONETOOL_CONFIG` environment variable
- **WHEN** the server starts
- **THEN** it SHALL look for `cwd/.onetool/config/onetool.yaml` first
- **AND** fall back to `~/.onetool/config/onetool.yaml` if not found
- **AND** prompt for initialization if neither exists

#### Scenario: Missing configuration file
- **GIVEN** no configuration file exists at any resolution location
- **WHEN** the server starts
- **THEN** it SHALL prompt "OneTool is not initialized. Initialize now? [Y/n]"
- **AND** on confirmation, run initialization and continue
- **AND** on decline, exit with message "Run 'onetool init' when ready."
- **RATIONALE** Ensures users explicitly opt-in to security configuration

### Requirement: Config Inheritance Directive

The system SHALL support an `inherit` directive to control config merging behaviour, requiring global config to exist for global inheritance.

#### Scenario: Implicit global inheritance
- **GIVEN** a project config without `inherit` field
- **WHEN** the config is loaded
- **THEN** it SHALL behave as if `inherit: global` was specified
- **AND** the project config SHALL be merged on top of global config
- **AND** if global config missing, it SHALL raise an error

#### Scenario: Explicit global inheritance
- **GIVEN** a project config with `inherit: global`
- **WHEN** the config is loaded
- **THEN** it SHALL load `~/.onetool/config/onetool.yaml` first
- **AND** process its includes
- **AND** deep merge the project config on top
- **AND** if global config missing, it SHALL raise an error

#### Scenario: Bundled inheritance preserved
- **GIVEN** a project config with `inherit: bundled`
- **WHEN** the config is loaded
- **THEN** it SHALL load bundled defaults first
- **AND** skip global config
- **AND** deep merge the project config on top
- **RATIONALE** Preserved for reproducible configs that don't depend on user settings

## ADDED Requirements

### Requirement: First-Run Initialization

The system SHALL detect first-run state and prompt for initialization.

#### Scenario: No global config exists
- **GIVEN** `~/.onetool/config/onetool.yaml` does not exist
- **AND** no project config exists
- **AND** no explicit config path provided
- **WHEN** the server starts
- **THEN** it SHALL prompt "OneTool is not initialized. Initialize now? [Y/n]"

#### Scenario: User confirms initialization
- **GIVEN** first-run prompt is displayed
- **WHEN** user confirms (Y or Enter)
- **THEN** it SHALL call `ensure_global_dir()` to create config
- **AND** continue starting the server normally

#### Scenario: User declines initialization
- **GIVEN** first-run prompt is displayed
- **WHEN** user declines (n)
- **THEN** it SHALL print "Run 'onetool init' when ready."
- **AND** exit with code 1

#### Scenario: Non-interactive mode
- **GIVEN** stdin is not a TTY (piped input, CI environment)
- **AND** no config exists
- **WHEN** the server starts
- **THEN** it SHALL print error "OneTool not initialized. Run: onetool init"
- **AND** exit with code 1
- **RATIONALE** Cannot prompt in non-interactive environments

#### Scenario: Init subcommand bypasses check
- **GIVEN** user runs `onetool init` or `onetool init reset`
- **WHEN** the command executes
- **THEN** it SHALL NOT trigger first-run prompt
- **AND** proceed with init logic directly

### Requirement: Config Version Migration Detection

The system SHALL detect outdated config versions and offer migration guidance.

#### Scenario: Config version check on load
- **GIVEN** a config file with `version: N`
- **WHEN** the config is loaded
- **THEN** it SHALL compare N against CURRENT_CONFIG_VERSION
- **AND** if N < CURRENT_CONFIG_VERSION, log warning about outdated config

#### Scenario: Migration hint on version mismatch
- **GIVEN** config version is less than current
- **WHEN** warning is logged
- **THEN** it SHALL include message "Run 'onetool init reset' to update config templates"
- **RATIONALE** Guides users to update without forcing immediate action

#### Scenario: Future version rejection
- **GIVEN** config version is greater than CURRENT_CONFIG_VERSION
- **WHEN** config is loaded
- **THEN** it SHALL fail with error indicating minimum OneTool version required
- **RATIONALE** Prevents running with incompatible newer configs

#### Scenario: Init reset updates version
- **GIVEN** user runs `onetool init reset`
- **WHEN** templates are copied
- **THEN** new config files SHALL contain current version
- **AND** user config is updated to latest templates
