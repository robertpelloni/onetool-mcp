## Purpose

Anonymous usage telemetry fired at server start via a Scarf pixel endpoint.
Covers event types (install, upgrade, start), opt-out mechanism, and disclosure.

## Requirements

### Requirement: Anonymous startup ping
On each server start, the server SHALL fire a single anonymous GET request to
the Scarf pixel endpoint with event type, version, OS, and Python version.
The request SHALL be non-blocking and SHALL NOT affect server startup time or
reliability. All failures SHALL be silently ignored.

#### Scenario: Ping fires on start
- **WHEN** the MCP server starts
- **THEN** a GET request is sent to the Scarf pixel URL with params `e`, `v`, `os`, `py`

#### Scenario: Ping does not block startup
- **WHEN** the Scarf endpoint is unreachable
- **THEN** the server starts normally with no error or delay

### Requirement: Install event on first run
The server SHALL fire an `install` event on the first ever start on a machine
(marker file `~/.onetool_telemetry` absent). After firing, the marker file
SHALL be written with the current version string.

#### Scenario: First start fires install
- **WHEN** `~/.onetool_telemetry` does not exist and the server starts
- **THEN** event `install` is sent and `~/.onetool_telemetry` is created containing the current version

#### Scenario: Subsequent start fires start
- **WHEN** `~/.onetool_telemetry` exists with the current version and the server starts
- **THEN** event `start` is sent

### Requirement: Upgrade event on version change
The server SHALL fire an `upgrade` event when the running version differs from
the version stored in `~/.onetool_telemetry`. The marker SHALL be updated with
the new version after firing.

#### Scenario: Version change fires upgrade
- **WHEN** `~/.onetool_telemetry` contains a version string different from the running version
- **THEN** event `upgrade` is sent with `v_from` and `v_to` params, and the marker is updated

### Requirement: Opt-out via environment variable
The server SHALL respect `DO_NOT_TRACK=1` and `SCARF_NO_ANALYTICS=1`
environment variables. When either is set to a non-empty, non-zero value,
no telemetry request SHALL be made.

#### Scenario: DO_NOT_TRACK disables telemetry
- **WHEN** `DO_NOT_TRACK=1` is set and the server starts
- **THEN** no request is sent to the Scarf pixel endpoint

#### Scenario: SCARF_NO_ANALYTICS disables telemetry
- **WHEN** `SCARF_NO_ANALYTICS=1` is set and the server starts
- **THEN** no request is sent to the Scarf pixel endpoint

### Requirement: Opt-out via config flag
The server SHALL respect `telemetry.enabled: false` in `onetool.yaml`.
When set to `false`, no telemetry request SHALL be made.

#### Scenario: Config flag disables telemetry
- **WHEN** `telemetry.enabled: false` is set in `onetool.yaml` and the server starts
- **THEN** no request is sent to the Scarf pixel endpoint

### Requirement: Telemetry disclosure
The project SHALL provide a `docs/telemetry.md` page that clearly states what
data is collected, what is not collected, and how to opt out.

#### Scenario: Disclosure page exists
- **WHEN** a user reads `docs/telemetry.md`
- **THEN** they can find: collected fields, fields not collected, and opt-out instructions
