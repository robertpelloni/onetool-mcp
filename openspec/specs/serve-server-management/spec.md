# serve-server-management Specification

## Purpose

Defines the `ot.server()` API for listing, querying, enabling, disabling, and restarting named proxy servers at runtime. All state changes are in-memory only; no YAML configuration files are modified.

## Requirements

### Requirement: Server Listing

The system SHALL provide an `ot.server()` function that lists all configured proxy servers and their status.

#### Scenario: List all servers
- **WHEN** `ot.server()` is called with no arguments
- **THEN** it SHALL return a formatted list of all configured servers
- **AND** each entry SHALL include the server name, enabled state, and connection status (connected/disconnected)
- **AND** connected servers SHALL show the number of tools they expose

### Requirement: Server Status Query

The system SHALL support querying detailed status for a single named server.

#### Scenario: Show server status
- **WHEN** `ot.server(status="devtools-isolated")` is called
- **THEN** it SHALL return the connection state and tool count for that server

#### Scenario: Unknown server name
- **WHEN** `ot.server(status="unknown-server")` is called
- **THEN** it SHALL return an error message listing configured server names

### Requirement: Runtime Server Enable/Disable

The system SHALL support enabling and disabling named proxy servers at runtime without restarting the MCP server.

#### Scenario: Enable a disabled server
- **WHEN** `ot.server(enable="devtools-auto")` is called
- **AND** `devtools-auto` is currently disabled
- **THEN** it SHALL set the server's enabled flag to true in-memory
- **AND** connect the server via `proxy_manager.reconnect_sync()`
- **AND** return a confirmation message with tool count

#### Scenario: Disable an enabled server
- **WHEN** `ot.server(disable="devtools-isolated")` is called
- **AND** `devtools-isolated` is currently enabled
- **THEN** it SHALL set the server's enabled flag to false in-memory
- **AND** disconnect the server
- **AND** return a confirmation message

#### Scenario: Enable already-enabled server
- **WHEN** `ot.server(enable="devtools-auto")` is called
- **AND** `devtools-auto` is already enabled and connected
- **THEN** it SHALL report that the server is already enabled
- **AND** SHALL NOT reconnect

#### Scenario: Disable already-disabled server
- **WHEN** `ot.server(disable="devtools-auto")` is called
- **AND** `devtools-auto` is already disabled
- **THEN** it SHALL report that the server is already disabled

#### Scenario: Enable unknown server
- **WHEN** `ot.server(enable="nonexistent")` is called
- **THEN** it SHALL return an error message listing configured server names

#### Scenario: State is in-memory only
- **WHEN** `ot.server(enable="devtools-auto")` is called
- **THEN** the YAML configuration file SHALL NOT be modified
- **AND** the change SHALL be lost when the MCP server restarts

### Requirement: Server Restart

The system SHALL support restarting a named proxy server.

#### Scenario: Restart a connected server
- **WHEN** `ot.server(restart="devtools-isolated")` is called
- **THEN** it SHALL disconnect and reconnect the server
- **AND** return a confirmation message with tool count after reconnection

#### Scenario: Restart a disconnected server
- **WHEN** `ot.server(restart="devtools-isolated")` is called
- **AND** the server is currently disconnected
- **THEN** it SHALL attempt to connect the server
- **AND** report success or failure
