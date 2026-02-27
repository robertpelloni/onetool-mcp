# tool-ot Specification

## Purpose

Defines the `ot` pack providing internal tool functions for accessing onetool state, tool discovery, configuration inspection, and system health. All output uses YAML flow style for compact, readable context that LLMs can easily parse.

This spec consolidates `tool-internal` and `tool-info`.
## Requirements
### Requirement: List Tools

The `ot.tools()` function SHALL list all available tools with optional filtering.

#### Scenario: List all tools
- **GIVEN** tools are registered
- **WHEN** `ot.tools()` is called
- **THEN** it SHALL return a list of all tools
- **AND** default info level SHALL be `default` (name + description)

#### Scenario: Filter by pattern
- **GIVEN** a pattern parameter
- **WHEN** `ot.tools(pattern="search")` is called
- **THEN** it SHALL return only tools with names containing the pattern (case-insensitive substring)
- **AND** pattern SHALL always perform partial matching

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter
- **WHEN** `ot.tools(info="min")` is called
- **THEN** it SHALL return only tool names as a list of strings

#### Scenario: Info level default
- **GIVEN** `info="default"` parameter (or no info parameter)
- **WHEN** `ot.tools()` or `ot.tools(info="default")` is called
- **THEN** each entry SHALL include: `{name, description}`
- **AND** description SHALL be truncated to 200 characters with `…` appended if cut

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.tools(info="full")` is called
- **THEN** each entry SHALL include: `{name, description, source}`
- **AND** source SHALL be "local" or "mcp:{server}"

---

### Requirement: Tool Detail

The `ot.tool_info()` function SHALL return detailed info (signature + args) for one or more tools.

#### Scenario: Exact name lookup
- **GIVEN** `name="brave.search"` parameter
- **WHEN** `ot.tool_info(name="brave.search")` is called
- **THEN** it SHALL return a single dict

#### Scenario: Pattern lookup
- **GIVEN** `pattern="brave"` parameter
- **WHEN** `ot.tool_info(pattern="brave")` is called
- **THEN** it SHALL return a list of dicts for all matching tools

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter
- **WHEN** `ot.tool_info(name="brave.search", info="min")` is called
- **THEN** each entry SHALL include: `{name, signature, args}`

#### Scenario: Info level default
- **GIVEN** `info="default"` parameter (or no info parameter)
- **WHEN** `ot.tool_info(name="brave.search")` is called
- **THEN** each entry SHALL include: `{name, signature, args, description, source}`
- **AND** description SHALL be truncated to 200 characters

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.tool_info(pattern="brave.search", info="full")` is called
- **THEN** each entry SHALL include: `{name, signature, description, source}`
- **AND** each entry SHALL include `{args, returns, example}` when available

#### Scenario: Proxy tool signature from schema
- **GIVEN** a proxy MCP server with tools exposing `inputSchema`
- **WHEN** `ot.tool_info(pattern="github.search", info="full")` is called
- **THEN** signature SHALL be derived from schema properties (e.g., `github.search(query: str, repo: str = '...')`)
- **AND** required parameters SHALL appear without defaults
- **AND** optional parameters SHALL show default values or `'...'` placeholder

---

### Requirement: Configuration Summary

The `ot.config()` function SHALL return key configuration values.

#### Scenario: Show config
- **GIVEN** configuration is loaded
- **WHEN** `ot.config()` is called
- **THEN** it SHALL return YAML with:
```yaml
aliases: {ws: brave.web_search}
snippets: {}
servers: [proxy_package_version]
```

#### Scenario: Empty config
- **GIVEN** no aliases or snippets configured
- **WHEN** `ot.config()` is called
- **THEN** it SHALL return empty values: `{aliases: {}, snippets: {}, servers: []}`

---

### Requirement: Health Check

The `ot.health()` function SHALL check health of OneTool components.

#### Scenario: Show health
- **GIVEN** OneTool is running
- **WHEN** `ot.health()` is called
- **THEN** it SHALL return YAML with component status:
```yaml
version: "1.0.0"
python: "3.11.x"
cwd: /current/working/directory
registry: {status: ok, tool_count: 15}
proxy: {status: ok, server_count: 1, servers: {proxy_package_version: connected}}
```

#### Scenario: Disconnected server
- **GIVEN** an MCP server is configured but not connected
- **WHEN** `ot.health()` is called
- **THEN** server status SHALL show "disconnected"
- **AND** proxy status SHALL show "degraded"

---

### Requirement: Notify Message

The `ot.notify()` function SHALL publish messages to configured topics.

#### Scenario: Send notification
- **WHEN** `ot.notify(topic="notes", message="Remember to review PR #123")`
- **THEN** the message is routed to the matching topic file
- **AND** appended as a YAML document

#### Scenario: No matching topic
- **GIVEN** no topic pattern matches the provided topic
- **WHEN** `ot.notify(topic="unknown:topic", message="test")` is called
- **THEN** it SHALL return "SKIP: no matching topic"

---

### Requirement: Reload Configuration

The `ot.reload()` function SHALL force reload of all configuration.

#### Scenario: Reload config
- **GIVEN** configuration files have been modified
- **WHEN** `ot.reload()` is called
- **THEN** it SHALL clear all cached configuration
- **AND** reload from disk
- **AND** return "OK: Configuration reloaded"

---

### Requirement: Runtime Statistics

The `ot.stats()` function SHALL return aggregated runtime statistics with configurable detail level.

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter
- **WHEN** `ot.stats(info="min")` is called
- **THEN** it SHALL return summary only: `{period, total_calls, success_rate, error_count, savings_usd}`
- **AND** it SHALL NOT include tools breakdown

#### Scenario: Info level default (default)
- **GIVEN** `info="default"` parameter or no info parameter
- **WHEN** `ot.stats()` or `ot.stats(info="default")` is called
- **THEN** it SHALL return summary stats: `{period, total_calls, success_rate, error_count, total_duration_ms, savings_usd, coffees}`
- **AND** it SHALL include `top_tools` with the top 10 tools sorted by call count (descending)
- **AND** each tool entry SHALL include: `{tool, calls, success_rate, avg_ms}`

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.stats(info="full")` is called
- **THEN** it SHALL return all fields including: `total_chars_in`, `total_chars_out`, `model`, `cost_estimate_usd`, `context_saved`, `time_saved_ms`
- **AND** it SHALL include `tools` with all tools and full per-tool stats
- **AND** it SHALL include `support` dict

#### Scenario: Filter by period
- **GIVEN** statistics collection is enabled
- **WHEN** `ot.stats(period="day")` is called
- **THEN** it SHALL return statistics for the specified period
- **AND** valid periods SHALL be: "day", "week", "month", "all"

#### Scenario: Filter by tool
- **GIVEN** statistics collection is enabled
- **WHEN** `ot.stats(tool="brave.search")` is called
- **THEN** it SHALL return statistics filtered to that tool

#### Scenario: Generate HTML report
- **GIVEN** statistics collection is enabled
- **WHEN** `ot.stats(output="stats.html")` is called
- **THEN** it SHALL generate an HTML report at the specified path
- **AND** include the path in the response as `html_report`

#### Scenario: Stats disabled
- **GIVEN** statistics collection is disabled in config
- **WHEN** `ot.stats()` is called
- **THEN** it SHALL return an error message indicating stats are disabled

#### Scenario: HTML write error
- **GIVEN** the output path is not writable
- **WHEN** `ot.stats(output="report.html")` is called
- **THEN** it SHALL return an error message: "Error: Cannot write to '<path>': <error>"

#### Scenario: Invalid period
- **GIVEN** an invalid period value
- **WHEN** `ot.stats(period="invalid")` is called
- **THEN** it SHALL return: "Error: Invalid period 'invalid'. Valid: day, week, month, all. Example: ot.stats(period='day')"

#### Scenario: Invalid info
- **GIVEN** an invalid info value
- **WHEN** `ot.stats(info="invalid")` is called
- **THEN** it SHALL return: "Error: Invalid info level 'invalid'. Valid: min, default, full. Example: ot.stats(info='default')"

---

### Requirement: YAML Flow Style Output

All `ot.*` functions SHALL format output using YAML flow style.

#### Scenario: Flow style formatting
- **GIVEN** any ot function is called
- **WHEN** results are formatted
- **THEN** simple objects SHALL use inline flow style: `{key: value, key2: value2}`
- **AND** lists of objects SHALL use block sequence with flow items

#### Scenario: Readability
- **GIVEN** YAML output is generated
- **WHEN** formatted
- **THEN** output SHALL be readable by humans and easily parseable by LLMs
- **AND** nested structures SHALL not exceed 2 levels of flow style

---

### Requirement: Logging

The tool SHALL follow [_nf-conventions](../_nf-conventions/spec.md) for logging.

#### Scenario: Span naming
- **GIVEN** an ot function is called
- **WHEN** LogSpan is created
- **THEN** span name SHALL be `ot.{function_name}` (e.g., `ot.tools`, `ot.health`)

---

### Requirement: Pack Discovery

The `ot.packs()` function SHALL list packs with optional filtering. The `ot.pack_info()` function SHALL return detailed info for a specific pack.

#### Scenario: List all packs
- **GIVEN** packs are registered (local and proxy)
- **WHEN** `ot.packs()` is called
- **THEN** it SHALL return a list of all packs
- **AND** default info level SHALL be `default` (name + description)

#### Scenario: Filter by pattern
- **GIVEN** a pattern parameter
- **WHEN** `ot.packs(pattern="brav")` is called
- **THEN** it SHALL return only packs with names containing the pattern (case-insensitive substring)

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter
- **WHEN** `ot.packs(info="min")` is called
- **THEN** it SHALL return only pack names as a list of strings

#### Scenario: Info level default
- **GIVEN** `info="default"` parameter (or no info parameter)
- **WHEN** `ot.packs()` or `ot.packs(info="default")` is called
- **THEN** each entry SHALL include: `{name, description}`
- **AND** description SHALL be sourced from prompts.yaml `packs:` section

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.packs(pattern="brave", info="full")` is called
- **THEN** each entry SHALL include: `{name, source, description, instructions, tool_names}`
- **AND** source SHALL be "local" or "mcp:{server}"

---

### Requirement: Pack Detail

The `ot.pack_info()` function SHALL return detailed info for one pack.

#### Scenario: Exact name lookup
- **GIVEN** `name="brave"` parameter
- **WHEN** `ot.pack_info(name="brave")` is called
- **THEN** it SHALL return a single dict

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter
- **WHEN** `ot.pack_info(name="brave", info="min")` is called
- **THEN** it SHALL include: `{name, source, tool_names}`

#### Scenario: Info level default
- **GIVEN** `info="default"` parameter (or no info parameter)
- **WHEN** `ot.pack_info(name="brave")` is called
- **THEN** it SHALL include: `{name, source, description, instructions, tool_names}`

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.pack_info(name="brave", info="full")` is called
- **THEN** it SHALL return markdown-formatted pack detail including:
  - Pack header with name
  - Type indicator ("Local" or "MCP Proxy Server")
  - Configured instructions (if present in prompts.yaml or server config)
  - List of tools in the pack with descriptions

#### Scenario: Pack with configured instructions
- **GIVEN** prompts.yaml contains instructions for pack "excel"
- **WHEN** `ot.pack_info(name="excel", info="full")` is called
- **THEN** it SHALL include the configured instructions text

#### Scenario: MCP server pack
- **GIVEN** a proxy server "github" is configured
- **WHEN** `ot.pack_info(name="github", info="full")` is called
- **THEN** it SHALL list tools from the proxy server
- **AND** show type as "MCP Proxy Server"
- **AND** include server instructions if configured in servers.yaml

---

### Requirement: Server Discovery

The `ot.servers()` function SHALL list configured MCP proxy servers with optional filtering.

#### Scenario: List all servers
- **GIVEN** MCP servers are configured in servers.yaml
- **WHEN** `ot.servers()` is called
- **THEN** it SHALL return a list of all configured servers
- **AND** default info level SHALL be `default`

#### Scenario: Filter by pattern
- **GIVEN** a pattern parameter
- **WHEN** `ot.servers(pattern="git")` is called
- **THEN** it SHALL return only servers with names containing the pattern (case-insensitive substring)

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter
- **WHEN** `ot.servers(info="min")` is called
- **THEN** it SHALL return only server names as a list of strings

#### Scenario: Info level default
- **GIVEN** `info="default"` parameter (or no info parameter)
- **WHEN** `ot.servers()` or `ot.servers(info="default")` is called
- **THEN** each entry SHALL include: `{name, type, enabled, status}`
- **AND** type SHALL be "stdio" or "http"
- **AND** status SHALL be "connected" or "disconnected"

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.servers(pattern="chrome-devtools", info="full")` is called
- **THEN** it SHALL return detailed server info including:
  - Server name as heading
  - Type (MCP Proxy Server with stdio/http)
  - Connection status
  - Enabled state
  - URL or command (depending on type)
  - Resource count (if connected)
  - Prompt count (if connected)
  - Instructions (if configured)
  - List of tools (if connected)

#### Scenario: Info level resources
- **GIVEN** `info="resources"` parameter
- **WHEN** `ot.servers(info="resources")` is called
- **THEN** each entry SHALL include: `{server, status, resource_count, resources}`
- **AND** status SHALL be "connected", "disconnected", or "error"
- **AND** resources SHALL be a list of `{uri, name, description}` dicts if connected
- **AND** resources SHALL be an empty list if disconnected

#### Scenario: Info level prompts
- **GIVEN** `info="prompts"` parameter
- **WHEN** `ot.servers(info="prompts")` is called
- **THEN** each entry SHALL include: `{server, status, prompt_count, prompts}`
- **AND** status SHALL be "connected", "disconnected", or "error"
- **AND** prompts SHALL be a list of `{name, description}` dicts if connected
- **AND** prompts SHALL be an empty list if disconnected

#### Scenario: Server with instructions
- **GIVEN** a server has `instructions` configured in servers.yaml
- **WHEN** `ot.servers(pattern="chrome-devtools", info="full")` is called
- **THEN** it SHALL include the configured instructions text

#### Scenario: Disconnected server
- **GIVEN** a server is configured but not connected
- **WHEN** `ot.servers(info="full")` is called
- **THEN** it SHALL show status as "disconnected"
- **AND** tools section SHALL show "(not connected)"

---

### Requirement: Alias Introspection

The `ot.aliases()` function SHALL list aliases with optional filtering.

#### Scenario: List all aliases
- **GIVEN** aliases are configured
- **WHEN** `ot.aliases()` is called with no arguments
- **THEN** it SHALL return all alias mappings
- **AND** default info level SHALL be `default`

#### Scenario: Filter by pattern
- **GIVEN** aliases are configured
- **WHEN** `ot.aliases(pattern="search")` is called
- **THEN** it SHALL return only aliases where name or target matches the pattern (case-insensitive substring)

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter
- **WHEN** `ot.aliases(info="min")` is called
- **THEN** it SHALL return only alias names as a list of strings

#### Scenario: Info level default
- **GIVEN** `info="default"` parameter (or no info parameter)
- **WHEN** `ot.aliases()` or `ot.aliases(info="default")` is called
- **THEN** it SHALL return structured data: `[{name, target}]`

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.aliases(info="full")` is called
- **THEN** it SHALL return the same structured data: `[{name, target}]`

---

### Requirement: Snippet Introspection

The `ot.snippets()` function SHALL list snippets with optional filtering. The `ot.snippet_info()` function SHALL return detailed info for a specific snippet.

#### Scenario: List all snippets
- **GIVEN** snippets are configured
- **WHEN** `ot.snippets()` is called with no arguments
- **THEN** it SHALL return all snippet names with descriptions
- **AND** default info level SHALL be `default`

#### Scenario: Filter snippets by pattern
- **GIVEN** snippets are configured
- **WHEN** `ot.snippets(pattern="pkg")` is called
- **THEN** it SHALL return only snippets where name or description matches the pattern (case-insensitive substring)

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter
- **WHEN** `ot.snippets(info="min")` is called
- **THEN** it SHALL return only snippet names as a list of strings

#### Scenario: Info level default
- **GIVEN** `info="default"` parameter (or no info parameter)
- **WHEN** `ot.snippets()` or `ot.snippets(info="default")` is called
- **THEN** it SHALL return structured data: `[{name, description}]`

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.snippets(info="full")` is called
- **THEN** it SHALL return structured data: `[{name, description, params}]`
- **AND** each params entry SHALL include type and default when available

---

### Requirement: Snippet Detail

The `ot.snippet_info()` function SHALL return the full definition of a specific snippet.

#### Scenario: Exact name lookup
- **GIVEN** `name="brv_research"` parameter
- **WHEN** `ot.snippet_info(name="brv_research")` is called
- **THEN** it SHALL return a single dict

#### Scenario: Info level default
- **GIVEN** `info="default"` parameter (or no info parameter)
- **WHEN** `ot.snippet_info(name="brv_research")` is called
- **THEN** it SHALL return the snippet definition including:
  - description
  - params with types and defaults
  - body template
  - example invocation

#### Scenario: Snippet output format
- **GIVEN** a valid snippet
- **WHEN** definition is retrieved with `ot.snippet_info()`
- **THEN** output SHALL be formatted as:
```yaml
name: brv_research
description: Search web and extract structured findings
params:
  topic: {description: "Topic to research"}
  count: {default: 5, description: "Number of sources"}
body: |
  results = brave.search(query="{{ topic }}", count={{ count }})
  ot_llm.transform(data=results, prompt="Extract key findings")

# Example with defaults:
# $brv_research topic=Python
# Expands to:
results = brave.search(query="Python", count=5)
ot_llm.transform(data=results, prompt="Extract key findings")
```

### Requirement: Unified Help

The `ot.help()` function SHALL provide unified help across tools, packs, snippets, and aliases.

#### Scenario: General help (no query)
- **GIVEN** no query parameter
- **WHEN** `ot.help()` is called
- **THEN** it SHALL return a general overview with:
  - Discovery commands (`ot.tools()`, `ot.packs()`, `ot.servers()`, etc.)
  - Info level documentation
  - Quick examples
  - Usage tips

#### Scenario: Exact tool lookup
- **GIVEN** a query matching a tool name exactly (e.g., `brave.search`)
- **WHEN** `ot.help(query="brave.search")` is called
- **THEN** it SHALL return detailed tool help including:
  - Tool name as heading
  - Description
  - Signature
  - Arguments with types and descriptions
  - Return type
  - Example usage
  - Documentation URL

#### Scenario: Exact server lookup
- **GIVEN** a query matching an MCP server name exactly (e.g., `chrome-devtools`)
- **WHEN** `ot.help(query="chrome-devtools")` is called
- **THEN** it SHALL return server help including:
  - Server name as heading
  - Type (MCP Proxy Server)
  - Connection status
  - Server instructions (if configured)
  - List of tools (if connected)

#### Scenario: Exact pack lookup
- **GIVEN** a query matching a pack name exactly (e.g., `brave`)
- **WHEN** `ot.help(query="brave")` is called
- **THEN** it SHALL return pack help including:
  - Pack name as heading
  - Pack instructions (if configured)
  - List of tools in the pack
  - Documentation URL

#### Scenario: Snippet lookup
- **GIVEN** a query starting with `$` (e.g., `$b_q`)
- **WHEN** `ot.help(query="$b_q")` is called
- **THEN** it SHALL return snippet help including:
  - Snippet name
  - Description
  - Parameters with defaults
  - Body template
  - Example invocation

#### Scenario: Alias lookup
- **GIVEN** a query matching an alias name
- **WHEN** `ot.help(query="ws")` is called
- **THEN** it SHALL return alias help including:
  - Alias name
  - Target function it maps to
  - Usage hint

#### Scenario: Fuzzy search
- **GIVEN** a query that does not match exactly but matches partially or fuzzily
- **WHEN** `ot.help(query="web fetch")` is called
- **THEN** it SHALL return search results grouped by type:
  - Tools matching the query
  - Packs matching the query
  - Snippets matching the query
  - Aliases matching the query

#### Scenario: Fuzzy matching with typos
- **GIVEN** a query with typos (e.g., `scaffoldl`, `frirecrawl`)
- **WHEN** `ot.help(query="scaffoldl")` is called
- **THEN** it SHALL use fuzzy matching to find close matches
- **AND** return results sorted by match score

#### Scenario: Info level min
- **GIVEN** `info="min"` parameter
- **WHEN** `ot.help(query="webfetch", info="min")` is called
- **THEN** it SHALL return only names of matching items

#### Scenario: Info level default (default)
- **GIVEN** `info="default"` parameter or no info parameter
- **WHEN** `ot.help(query="brave")` is called
- **THEN** it SHALL return names with brief descriptions

#### Scenario: Info level full
- **GIVEN** `info="full"` parameter
- **WHEN** `ot.help(query="brave.search", info="full")` is called
- **THEN** it SHALL return complete documentation including all available fields

#### Scenario: Documentation URL generation
- **GIVEN** a tool or pack query
- **WHEN** help is displayed
- **THEN** it SHALL include a documentation URL in format:
  `https://onetool.beycom.online/reference/tools/{doc_slug}/`
- **AND** doc_slug SHALL map from pack name using hardcoded overrides:
  - `brave` -> `brave-search`
  - `code` -> `code-search`
  - `db` -> `database`
  - `ground` -> `grounding-search`
  - `ot_llm` -> `ot_llm`
  - `webfetch` -> `web-fetch`
- **AND** packs not in override map SHALL use pack name as slug

#### Scenario: No matches
- **GIVEN** a query that matches nothing
- **WHEN** `ot.help(query="xyznonexistent")` is called
- **THEN** it SHALL return a message indicating no matches found
- **AND** suggest using `ot.tools()` or `ot.packs()` to browse available items

---

### Requirement: Query Stored Results

The `ot.result()` function SHALL query stored large outputs with pagination, filtering, and navigation hints.

#### Scenario: Basic query with defaults
- **GIVEN** a stored result with handle `abc123`
- **WHEN** `ot.result(handle="abc123")` is called
- **THEN** it SHALL return lines 1-100 (default offset=1, limit=100)

#### Scenario: Query with offset and limit
- **GIVEN** a stored result with 500 lines
- **WHEN** `ot.result(handle="abc123", offset=101, limit=50)` is called
- **THEN** it SHALL return lines 101-150

#### Scenario: Query with search filter
- **GIVEN** a stored result containing lines with "error" and lines without
- **WHEN** `ot.result(handle="abc123", search="error")` is called
- **THEN** it SHALL return only lines matching the regex pattern "error"
- **AND** offset/limit SHALL apply to filtered results

#### Scenario: Query with fuzzy matching
- **GIVEN** a stored result containing "configuration"
- **WHEN** `ot.result(handle="abc123", search="config", fuzzy=True)` is called
- **THEN** it SHALL use fuzzy matching to find similar content
- **AND** results SHALL be sorted by match score

#### Scenario: Query with tail
- **GIVEN** a stored result with N lines
- **WHEN** `ot.result(handle="abc123", tail=20)` is called
- **THEN** it SHALL return the last 20 lines without requiring total_lines to be known first
- **AND** if tail > total_lines, all lines SHALL be returned

#### Scenario: Query with context
- **GIVEN** a stored result with search matches
- **WHEN** `ot.result(handle="abc123", search="TARGET", context=2)` is called
- **THEN** it SHALL return matching lines plus 2 lines before and after each match
- **AND** non-contiguous groups SHALL be separated by `---`

#### Scenario: Invalid handle
- **GIVEN** handle "nonexistent" does not exist
- **WHEN** `ot.result(handle="nonexistent")` is called
- **THEN** it SHALL return an error message indicating handle not found

#### Scenario: Expired handle
- **GIVEN** a stored result that has exceeded TTL
- **WHEN** `ot.result(handle="expired123")` is called
- **THEN** it SHALL return an error message indicating result has expired

#### Scenario: Query response format
- **GIVEN** a stored result is queried
- **WHEN** results are returned
- **THEN** response SHALL include:
  - `lines`: List of matching lines
  - `total_lines`: Total lines in stored result (after search filter)
  - `returned`: Number of lines returned in this chunk
  - `offset`: Starting offset used
  - `has_more`: Boolean indicating if more lines exist after this chunk
  - `progress`: Human-readable position e.g. "lines 1-50 of 343 (15%)"
  - `total_size_bytes`: Full size of stored result in bytes
- **AND** when `has_more` is True, response SHALL also include:
  - `next_query`: Exact `ot.result()` call to fetch the next chunk

#### Scenario: 1-indexed offset
- **GIVEN** a stored result
- **WHEN** `ot.result(handle="abc123", offset=1)` is called
- **THEN** it SHALL start from the first line (matching Claude's `Read` tool semantics)

#### Scenario: Offset validation
- **GIVEN** offset < 1
- **WHEN** `ot.result(handle="abc123", offset=0)` is called
- **THEN** it SHALL raise ValueError with message "offset must be >= 1 (1-indexed), got 0"

#### Scenario: Limit validation
- **GIVEN** limit < 1
- **WHEN** `ot.result(handle="abc123", limit=0)` is called
- **THEN** it SHALL raise ValueError with message "limit must be >= 1, got 0"

---

### Requirement: Stored Result Usage Hints

When large output is stored, the returned summary SHALL include navigation hints.

#### Scenario: Usage hints format
- **GIVEN** a tool output is stored
- **WHEN** the `StoredResult` summary is returned
- **THEN** it SHALL include a `usage` dict (not `query` string) with keys:
  - `page`: fetch first page
  - `search`: filter by pattern
  - `fuzzy`: fuzzy search
  - `slice`: fetch a specific slice
  - `tail`: fetch last N lines
- **AND** each value SHALL be a ready-to-run `ot.result()` call containing the handle

---

### Requirement: Result Query Logging

The `ot.result()` function SHALL follow logging conventions.

#### Scenario: Span naming
- **GIVEN** `ot.result()` is called
- **WHEN** LogSpan is created
- **THEN** span name SHALL be `ot.result`
- **AND** span SHALL include: `handle`, `offset`, `limit`, `search` (if provided), `tail` (if > 0), `context` (if > 0)

---

### Requirement: Security Introspection

The `ot.security()` function SHALL allow agents to query security rules.

#### Scenario: Security summary
- **GIVEN** no arguments
- **WHEN** `ot.security()` is called
- **THEN** it SHALL return a summary including:
  - `status`: "configured" or "fallback"
  - `enabled`: boolean
  - `builtins`: count and sample of allowed builtins
  - `imports`: count of allowed/warned imports
  - `calls`: blocked and warned patterns
  - `dunders`: allowed magic variables
  - `tool_namespaces`: auto-allowed tool patterns

#### Scenario: Check specific pattern
- **GIVEN** a `check` parameter
- **WHEN** `ot.security(check="json")` is called
- **THEN** it SHALL return status dict with:
  - `pattern`: the checked pattern
  - `status`: "allowed", "blocked", or "warned"
  - `category`: "builtins", "imports", "calls", or "tool_namespace"
  - `reason`: explanation of why

#### Scenario: Check tool namespace
- **GIVEN** a tool namespace pattern
- **WHEN** `ot.security(check="brave.search")` is called
- **THEN** status SHALL be "allowed"
- **AND** category SHALL be "tool_namespace"
- **AND** reason SHALL indicate auto-allowed

#### Scenario: Check blocked import
- **GIVEN** a blocked import
- **WHEN** `ot.security(check="os")` is called
- **THEN** status SHALL be "blocked"
- **AND** reason SHALL indicate not in allowlist

---

### Requirement: Version

The `ot.version()` function SHALL return the OneTool version string.

#### Scenario: Get version
- **WHEN** `ot.version()` is called
- **THEN** it SHALL return the version string (e.g., "1.0.0")

---

### Requirement: Debug Information

The `ot.debug()` function SHALL provide comprehensive debug information about the OneTool installation.

#### Scenario: Basic debug information
- **GIVEN** OneTool is running
- **WHEN** `ot.debug()` is called
- **THEN** it SHALL return a dict with sections:
  - `version`: Package version info
  - `paths`: Relevant file paths (install, global_dir, cwd, python, config_file, log_dir, stats_file, result_store)
  - `config`: Configuration summary (version, servers, packs_loaded, aliases, snippets)
  - `python`: Python environment (version, implementation, platform, executable)
  - `system`: OS/platform info (platform, machine, user, pid, memory if available)
  - `runtime`: Runtime state (packs_loaded, tools_local, tools_proxied, servers_configured, servers_connected, servers_disconnected, start_time, uptime_seconds)

#### Scenario: Verbose configuration
- **GIVEN** `verbose=True` parameter
- **WHEN** `ot.debug(verbose=True)` is called
- **THEN** config section SHALL include additional fields:
  - `includes`: List of included config files
  - `tools_dir`: Tool directory paths
  - `stats_enabled`: Statistics collection status
  - `log_verbose`: Verbose logging status

#### Scenario: Environment variables
- **GIVEN** `env_vars=True` parameter
- **WHEN** `ot.debug(env_vars=True)` is called
- **THEN** it SHALL include an `env` section with:
  - `ONETOOL_CONFIG`: Config file override
  - `OT_CWD`: Working directory override

#### Scenario: Dependency versions
- **GIVEN** `dependencies=True` parameter
- **WHEN** `ot.debug(dependencies=True)` is called
- **THEN** it SHALL include a `dependencies` section with version strings for:
  - fastmcp
  - pydantic
  - pyyaml
  - loguru
  - requests
  - openai
- **AND** missing packages SHALL show "not installed"

#### Scenario: Module load time tracking
- **GIVEN** OneTool has been running
- **WHEN** `ot.debug()` is called
- **THEN** runtime section SHALL include:
  - `start_time`: ISO 8601 timestamp of when the module was loaded
  - `uptime_seconds`: Time since module load in seconds (rounded to 2 decimals)

#### Scenario: Memory usage (optional)
- **GIVEN** psutil is available
- **WHEN** `ot.debug()` is called
- **THEN** system section SHALL include a `memory` subsection with:
  - `rss_mb`: Resident set size in MB (rounded to 2 decimals)
  - `vms_mb`: Virtual memory size in MB (rounded to 2 decimals)
  - `percent`: Memory usage percentage (rounded to 2 decimals)

#### Scenario: Multi-version identification
- **GIVEN** multiple OneTool versions may be running
- **WHEN** `ot.debug()` is called
- **THEN** the output SHALL uniquely identify the version by:
  - Package version number
  - Global directory path
  - Install path
  - Start time (module load time)
  - Uptime

#### Scenario: Logging
- **GIVEN** `ot.debug()` is called
- **WHEN** LogSpan is created
- **THEN** span name SHALL be `ot.debug`
- **AND** span SHALL include `version` attribute from result

### Requirement: Agent Cheatsheet

The `ot.cheatsheet()` function SHALL return a project-agnostic reference document for AI agents using OneTool.

#### Scenario: Return cheatsheet content
- **GIVEN** the cheatsheet file exists at `~/.onetool/config/cheatsheet.md`
- **WHEN** `ot.cheatsheet()` is called
- **THEN** it SHALL return the full markdown content of the file

#### Scenario: Fallback to package template
- **GIVEN** no user-editable cheatsheet exists at `~/.onetool/config/cheatsheet.md`
- **WHEN** `ot.cheatsheet()` is called
- **THEN** it SHALL fall back to reading from the package's global_templates directory

#### Scenario: User-editable
- **GIVEN** the cheatsheet is copied to `~/.onetool/config/` during init
- **WHEN** a user edits `~/.onetool/config/cheatsheet.md`
- **THEN** subsequent calls to `ot.cheatsheet()` SHALL return the modified content

#### Scenario: Content principles
- **GIVEN** the shipped cheatsheet content
- **THEN** it SHALL use keyword-only argument examples
- **AND** it SHALL NOT reference snippets (tools only)
- **AND** it SHALL NOT include project-specific paths or data
- **AND** every example SHALL be a valid, copy-pasteable function call
