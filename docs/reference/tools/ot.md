# ot.* Internal Tools

**Introspect. Configure. Manage. OneTool from the inside.**

Internal tools for OneTool introspection and management.

## Highlights

- List and filter available tools and packs
- Check system health and API connectivity
- Access configuration, aliases, and snippets
- Publish messages to configured topics

## Functions

| Function | Description |
|----------|-------------|
| `ot.help(query, info)` | Unified help - search tools, packs, servers, snippets, aliases |
| `ot.tools(pattern, info)` | List tools, filter by pattern |
| `ot.packs(pattern, info)` | List packs (local + MCP), filter by pattern |
| `ot.servers(pattern, info)` | List MCP proxy servers, filter by pattern |
| `ot.aliases(pattern, info)` | List aliases, filter by pattern |
| `ot.snippets(pattern, info)` | List snippets, filter by pattern |
| `ot.config()` | Show aliases, snippets, and server names |
| `ot.health()` | Check tool dependencies and API connectivity |
| `ot.stats(period, tool, output)` | Get runtime usage statistics |
| `ot.notify(topic, message)` | Publish message to configured topic |
| `ot.reload()` | Force configuration reload |

## Info Levels

All discovery functions (`help`, `tools`, `packs`, `aliases`, `snippets`) support an `info` parameter:

| Level | Description |
|-------|-------------|
| `list` | Names only (minimal context) |
| `min` | Name + short description (default) |
| `full` | Complete details |

## ot.help()

Unified help entry point - search across tools, packs, servers, snippets, and aliases.

```python
# General help overview
ot.help()

# Exact tool lookup
ot.help(query="brave.search")

# Exact pack lookup
ot.help(query="firecrawl")

# Exact server lookup (MCP proxy servers)
ot.help(query="devtools")
ot.help(query="github")

# Snippet lookup (prefix with $)
ot.help(query="$b_q")

# Alias lookup
ot.help(query="ws")

# Fuzzy search across all types
ot.help(query="web fetch")
ot.help(query="search", info="list")
```

**Behaviour:**

- No query: Returns general help overview with discovery commands and examples
- Exact server match: Returns server help with type, status, instructions, and tool list
- Exact tool match (contains `.`): Returns detailed tool help with signature, args, returns, example
- Exact pack match: Returns pack help with instructions and tool list
- Snippet match (starts with `$`): Returns snippet definition with params and body
- Alias match: Returns alias mapping and target description
- Fuzzy matches: Groups results by type (Tools, Packs, Snippets, Aliases)
- No matches: Suggests using `ot.tools()`, `ot.packs()`, `ot.servers()`, etc. to browse

The `info` parameter controls detail level for all search results.

**Documentation URLs:**

Help output includes documentation URLs for tools and packs:
`https://onetool.beycom.online/reference/tools/{pack}/`

## ot.tools()

List all available tools with signatures, filter by pattern.

```python
# List all tools (default: info="min")
ot.tools()

# Filter by name pattern (substring match)
ot.tools(pattern="search")

# Filter by pack (use trailing dot)
ot.tools(pattern="brave.")

# Names only
ot.tools(info="list")

# Full details (signature, args, returns, example)
ot.tools(pattern="brave.search", info="full")
```

Returns a list of tool names (info="list") or tool dicts.

## ot.packs()

List all packs (local and MCP), filter by pattern.

```python
# List all packs (default: info="min")
ot.packs()

# Filter by pattern
ot.packs(pattern="brav")

# Names only
ot.packs(info="list")

# Full details (type, instructions, tool list)
ot.packs(pattern="brave", info="full")

# MCP server packs show source="mcp"
ot.packs(pattern="devtools")
```

Returns a list of pack names (info="list") or pack summaries/details. MCP proxy servers appear as packs with `source: "mcp"`.

## ot.servers()

List configured MCP proxy servers with connection status.

```python
# List all servers (default: info="min")
ot.servers()

# Filter by pattern
ot.servers(pattern="git")

# Names only
ot.servers(info="list")

# Full details (type, status, instructions, tools)
ot.servers(pattern="devtools", info="full")
```

Returns server configuration including:

- `name` - Server name from config
- `type` - Connection type (stdio or http)
- `enabled` - Whether server is enabled
- `status` - Connection status (connected/disconnected)
- `tool_count` - Number of tools available

With `info="full"`, also shows:

- Server instructions (if configured)
- List of available tools (if connected)
- URL or command details

## ot.aliases()

List aliases, filter by pattern.

```python
# List all aliases (default: info="min")
ot.aliases()

# Filter by pattern (matches alias name or target)
ot.aliases(pattern="search")

# Names only
ot.aliases(info="list")

# Structured output
ot.aliases(info="full")
```

Aliases are defined in config:

```yaml
alias:
  ws: brave.search
  ns: brave.news
  wf: web.fetch
```

## ot.snippets()

List snippets, filter by pattern.

```python
# List all snippets (default: info="min")
ot.snippets()

# Filter by pattern (matches name or description)
ot.snippets(pattern="search")

# Names only
ot.snippets(info="list")

# Full definition (params, body, example)
ot.snippets(pattern="multi_search", info="full")
```

Snippets are defined in config:

```yaml
snippets:
  multi_search:
    description: Search multiple queries
    params:
      queries: { required: true }
    body: |
      results = []
      for q in {{ queries }}:
          results.append(brave.search(query=q))
      "\n---\n".join(results)
```

## ot.config()

Show key configuration values including aliases, snippets, and servers.

```python
ot.config()
```

Returns JSON with:
- `aliases` - configured command aliases
- `snippets` - available snippet templates
- `servers` - configured MCP server names

## ot.health()

Check system health and API connectivity.

```python
ot.health()
```

Returns status of:
- OneTool version and Python version
- Registry status and tool count
- Proxy status and server connections

## ot.stats()

Get runtime statistics for OneTool usage.

```python
# All-time stats
ot.stats()

# Filter by time period
ot.stats(period="day")
ot.stats(period="week")

# Filter by tool
ot.stats(tool="brave.search")

# Generate HTML report
ot.stats(output="stats.html")
```

Returns JSON with:
- `total_calls` - Total number of tool calls
- `success_rate` - Percentage of successful calls
- `context_saved` - Estimated context tokens saved
- `time_saved_ms` - Estimated time saved in milliseconds
- `tools` - Per-tool breakdown

## ot.notify()

Publish a message to a configured topic.

```python
ot.notify(topic="notes", message="Remember to review PR #123")
```

Configure topics in `onetool.yaml`:

```yaml
tools:
  msg:
    topics:
      - pattern: "notes"
        file: .notes/inbox.md
      - pattern: "ideas"
        file: .notes/ideas.md
```

## ot.reload()

Force reload of all configuration.

```python
ot.reload()
```

Clears cached configuration and reloads from disk. Use after modifying config files during a session.

## Source

OneTool internal implementation
