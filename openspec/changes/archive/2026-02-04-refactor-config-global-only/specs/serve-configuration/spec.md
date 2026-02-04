# serve-configuration Spec Delta

## ADDED Requirements

### Requirement: Root-Level Environment Configuration

The system SHALL support a root-level `env:` section for shared subprocess environment variables.

#### Scenario: Root env section
- **GIVEN** configuration with:
  ```yaml
  env:
    HOME: /home/user
    LANG: en_US.UTF-8
  ```
- **WHEN** a stdio MCP server is spawned
- **THEN** the subprocess SHALL inherit these environment variables

#### Scenario: Server env overrides root env
- **GIVEN** root `env:` with `LANG: en_US.UTF-8`
- **AND** server `env:` with `LANG: C.UTF-8`
- **WHEN** the server subprocess is spawned
- **THEN** `LANG` SHALL be `C.UTF-8` (server overrides root)

#### Scenario: Subprocess env build order
- **GIVEN** a stdio server configuration
- **WHEN** the subprocess environment is built
- **THEN** it SHALL be constructed in order:
  1. `PATH` from host os.environ (always included)
  2. Root `env:` section values
  3. Server-specific `env:` section values (overrides root)
  4. `${VAR}` expansion from secrets.yaml only

#### Scenario: Variable expansion in env values
- **GIVEN** env value containing `${API_KEY}`
- **AND** `API_KEY` defined in secrets.yaml
- **WHEN** the subprocess is spawned
- **THEN** the value SHALL be expanded from secrets.yaml
- **AND** os.environ SHALL NOT be consulted

#### Scenario: No root env section
- **GIVEN** configuration without `env:` section
- **WHEN** a stdio server is spawned
- **THEN** subprocess SHALL receive only `PATH` plus server-specific env

## MODIFIED Requirements

### Requirement: YAML Configuration File

The system SHALL load configuration from a YAML file using a standard resolution order.

#### Scenario: Default configuration file resolution
- **GIVEN** no explicit config path provided
- **AND** no `ONETOOL_CONFIG` environment variable
- **WHEN** the server starts
- **THEN** it SHALL look for `~/.onetool/config/onetool.yaml`
- **AND** require initialisation if not found

#### Scenario: Environment variable override
- **GIVEN** `ONETOOL_CONFIG=/path/to/config.yaml` environment variable
- **WHEN** the server starts
- **THEN** it SHALL load from the specified path
- **AND** skip the standard resolution order

#### Scenario: Custom configuration file
- **GIVEN** `--config /path/to/config.yaml` argument
- **WHEN** the server starts
- **THEN** it SHALL load from the specified path

#### Scenario: Missing configuration file
- **GIVEN** no configuration file exists at any resolution location
- **WHEN** the server starts
- **THEN** it SHALL prompt user to initialise (interactive mode)
- **OR** exit with error message (non-interactive mode)

### Requirement: Config Version Migration Detection

The system SHALL detect incompatible config versions.

#### Scenario: Future config version
- **GIVEN** a config file with `version: N` where N > CURRENT_CONFIG_VERSION
- **WHEN** configuration is loaded
- **THEN** loading SHALL fail with error
- **AND** the error SHALL indicate minimum OneTool version required
- **AND** suggest upgrading: "uv tool upgrade onetool"

#### Scenario: Missing version field
- **GIVEN** a config file without `version` field
- **WHEN** configuration is loaded
- **THEN** version 1 SHALL be assumed

### Requirement: Config Include

The system SHALL support a top-level `include:` key for merging external config files.

#### Scenario: Single include file
- **GIVEN** configuration with:
  ```yaml
  include:
    - base.yaml
  ```
- **WHEN** the config is loaded
- **THEN** the content of `base.yaml` SHALL be merged into the config

#### Scenario: Multiple include files
- **GIVEN** configuration with:
  ```yaml
  include:
    - shared.yaml
    - project.yaml
    - local.yaml
  ```
- **WHEN** the config is loaded
- **THEN** files SHALL be merged left-to-right
- **AND** later files SHALL override earlier files on key conflicts

#### Scenario: Inline content overrides includes
- **GIVEN** configuration with:
  ```yaml
  include:
    - base.yaml  # contains servers: {github: {...}}
  servers:
    github:
      timeout: 120  # override
    local:
      type: stdio   # addition
  ```
- **WHEN** the config is loaded
- **THEN** inline `servers.github` SHALL override included `servers.github`
- **AND** inline `servers.local` SHALL be added

#### Scenario: Deep merge nested dicts
- **GIVEN** `base.yaml` contains `tools: {brave: {timeout: 60}}`
- **AND** main config contains `tools: {brave: {retries: 3}}`
- **WHEN** merged
- **THEN** result SHALL be `tools: {brave: {timeout: 60, retries: 3}}`

#### Scenario: Non-dict values replaced
- **GIVEN** `base.yaml` contains `log_level: DEBUG`
- **AND** main config contains `log_level: INFO`
- **WHEN** merged
- **THEN** result SHALL be `log_level: INFO`

#### Scenario: Include path resolution
- **GIVEN** a relative path in `include:`
- **WHEN** the file is loaded
- **THEN** the path SHALL be resolved relative to the config file directory
- **AND** `~` SHALL expand to user home directory

#### Scenario: Nested includes with depth limit
- **GIVEN** `base.yaml` contains its own `include:` key
- **WHEN** the config is loaded
- **THEN** nested includes SHALL be processed recursively
- **AND** merge order SHALL be depth-first
- **AND** include depth SHALL be limited to 5 levels

#### Scenario: Include depth exceeded
- **GIVEN** includes nested more than 5 levels deep
- **WHEN** the config is loaded
- **THEN** an error SHALL be raised indicating depth exceeded

#### Scenario: Missing include file
- **GIVEN** `include:` references a file that does not exist
- **WHEN** the config is loaded
- **THEN** a warning SHALL be logged
- **AND** loading SHALL continue without that include

#### Scenario: No include key
- **GIVEN** configuration without `include:` key
- **WHEN** the config is loaded
- **THEN** loading SHALL proceed normally with no external files

### Requirement: Security Configuration

The system SHALL support allowlist-based security configuration via security.yaml.

**IMPORTANT:** The security model provides defence-in-depth but is NOT a sandbox. Never run code you do not trust.

#### Scenario: Security section structure
- **GIVEN** configuration with:

  ```yaml
  security:
    validate_code: true
    enabled: true
    builtins:
      allow: [str, int, len, print]
    imports:
      allow: [json, re, math]
      warn: [yaml]
    calls:
      block: [pickle.*, yaml.load]
      warn: [random.seed]
    dunders:
      allow: [__format__, __sanitize__]
  ```

- **WHEN** code is validated
- **THEN** only explicitly allowed items SHALL pass validation

#### Scenario: Security disabled
- **GIVEN** configuration with `security.enabled: false`
- **WHEN** code is validated
- **THEN** security pattern checks SHALL be skipped

#### Scenario: Default security configuration
- **GIVEN** no security section in config
- **WHEN** code is validated
- **THEN** defaults embedded in Pydantic models SHALL be used
- **AND** defaults SHALL include safe builtins and standard library imports

#### Scenario: Wildcard patterns in security config
- **GIVEN** security patterns containing wildcards (*, ?, [seq])
- **WHEN** patterns are loaded
- **THEN** they SHALL be matched using fnmatch semantics
- **EXAMPLE** `pickle.*` matches `pickle.load`, `pickle.loads`, etc.

### Requirement: Runtime Tool Config Access

Tools SHALL access their configuration via `get_tool_config()` at runtime.

#### Scenario: Get tool config with schema
- **GIVEN** a tool needs its configuration
- **WHEN** `get_tool_config("brave", Config)` is called
- **THEN** it SHALL return a Config instance with merged values
- **AND** values from onetool.yaml SHALL override defaults

#### Scenario: Get tool config without schema
- **GIVEN** a tool calls `get_tool_config("brave")`
- **WHEN** no schema is provided
- **THEN** it SHALL return a dict with raw config values
- **OR** empty dict if no config exists

#### Scenario: Unknown tool in config
- **GIVEN** a `tools.unknown_pack:` section in onetool.yaml
- **AND** no tool with pack "unknown_pack" exists
- **WHEN** configuration is loaded
- **THEN** the section SHALL be preserved (extra="allow")
- **AND** no error SHALL occur

### Requirement: Stats Configuration Location

Statistics configuration SHALL be at the root level.

#### Scenario: Stats config at root level
- **GIVEN** configuration with:
  ```yaml
  stats:
    enabled: true
    flush_interval_seconds: 60
  ```
- **WHEN** the server starts
- **THEN** it SHALL use the root-level `stats` configuration

#### Scenario: Default stats location
- **GIVEN** no stats configuration specified
- **WHEN** the server starts
- **THEN** stats SHALL use defaults from Pydantic model
- **DEFAULT** enabled: true, flush_interval_seconds: 30, persist_dir: stats

## REMOVED Scenarios

#### Scenario: OT_CWD affects config resolution
**From Requirement**: YAML Configuration File
**Reason**: Global-only configuration does not use working directory
**Migration**: Use `~/.onetool/config/onetool.yaml` for all configuration

### Requirement: Outdated config version warning
**Reason**: Simplified to error-only on incompatible versions
**Migration**: None - just error handling simplification

### Requirement: Missing version field warning
**Reason**: Simplified - missing version silently defaults to 1
**Migration**: None - just warning removal

### Requirement: Config Inheritance Directive
**Reason**: Global-only configuration removes need for inheritance
**Migration**: Remove `inherit: global` or `inherit: none` from configs; all config is global

### Requirement: Two-Tier Include Resolution
**Reason**: Single-tier includes only (config directory)
**Migration**: Use absolute paths or `~` expansion for shared includes

### Requirement: Deep Merge Behaviour (inheritance context)
**Reason**: No inheritance means no global/project merge
**Migration**: Use includes for composition

### Requirement: Tool-Local Configuration Schema (AST discovery)
**Reason**: Replaced with `extra="allow"` and runtime validation
**Migration**: Tools define defaults in their Config class; YAML overrides at runtime

### Requirement: Dynamic Tool Configuration Building
**Reason**: Replaced with `extra="allow"` on tools dict
**Migration**: None - tool config access unchanged

### Requirement: Compact array format
**Reason**: Simplifies config parsing; flat lists are clearer
**Migration**: Convert `[[a, b], c]` to `[a, b, c]` in security config

### Requirement: Projects Configuration
**Reason**: Not used in practice; global config is sufficient
**Migration**: Remove `projects:` section from config

### Requirement: Legacy tools.stats path
**Reason**: Root-level stats only; no migration shim
**Migration**: Move `tools.stats:` to root-level `stats:`

### Requirement: Circular include detection
**Reason**: Replaced with depth limit (simpler, same effect)
**Migration**: None - depth limit handles circular includes

### Requirement: Subprocess Environment Pass-through
**Reason**: All secrets in one place (secrets.yaml). No os.environ fallback.
**Migration**: Add any env vars you were passing through (like `HOME`, `LANG`) to secrets.yaml if needed by subprocess
