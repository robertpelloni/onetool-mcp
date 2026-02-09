# Sanity Tests

## Test Tools

```markdown
Title: Test Tools

Explain each step so it is easy to follow what you did and why. Use 💭 to highlight these explanations.
Learn OneTool with `ot.help(info="full")` as well as the docs at ./docs. If it helps, look at the source code.
Do sanity testing and find issues.

Test out the following packs:
Packs: brave, context7, convert, db, devtools, diagram, excel, file, github, ground, llm, mem, ot, package, ripgrep, scaffold, web

When testing:
- convert with files at demo/data
- db with db at demo/db/northwind.db
- excel with files at demo/data
- mem: write, read, list, search, toc, slice, snap/restore, stale/refresh, write_batch, read_batch, slice_batch, stats, export/load, update, delete, decay, context, cache_clear
- diagram: list_providers, get_template, generate_source, render_diagram, get_playground_url
- scaffold: templates, validate, extensions
- web with a known URL like https://en.wikipedia.org/wiki/Python_(programming_language)
- devtools with a known URL like https://en.wikipedia.org/wiki/Python_(programming_language)
- llm: transform with simple data, transform_file with a demo file

```

```markdown
Title: Snippets

Explain each step so it is easy to follow what you did and why. Use 💭 to highlight these explanations.
Learn OneTool with `ot.help(info="full")` as well as the docs at ./docs. If it helps, look at the source code.
Do sanity testing and find issues.

Test the following snippets:

Search snippets:
- $brv q="test query"
- $brv_research q="topic"
- $g q="test query"
- $g_reddit q="topic"
- $gh q="onetool"

Documentation snippets:
- $c7_lib q="react"
- $c7 lib="facebook/react" q="hooks"
- $c7_eg lib="facebook/react" q="useState"

Package snippets:
- $pkg
- $pkg_pypi packages="requests"
- $pkg_npm packages="react"
- $pkg_model q="claude"

File/code snippets:
- $rg p="TODO"
- $rg_count p="import" ft="py"
- $web u="https://en.wikipedia.org/wiki/Python_(programming_language)"
- $web_summary u="https://en.wikipedia.org/wiki/Python_(programming_language)"
- $web_data u="https://en.wikipedia.org/wiki/Python_(programming_language)" schema="section headings"

System snippets:
- $ot_status
- $ot_reload
- $ot_notify msg="sanity test"

```

```markdown
Title: Features

Explain each step so it is easy to follow what you did and why. Use 💭 to highlight these explanations.
Learn OneTool with `ot.help(info="full")` as well as the docs at ./docs. If it helps, look at the source code.
Do sanity testing and find issues.

Introspection & Discovery
- ot.help() - general help overview
- ot.help(query="...") - exact lookup (tool, pack, snippet, alias)
- ot.help(query="...", info="list|min|full") - info levels
- ot.tools() - list all tools
- ot.tools(pattern="...") - filter by pattern/prefix
- ot.packs() - list all packs
- ot.packs(pattern="...") - filter by pattern
- ot.aliases() - list configured aliases
- ot.snippets() - list configured snippets
- ot.servers() - list MCP proxy servers
- ot.servers(pattern="...") - filter by pattern
- ot.config() - show config (aliases, snippets, servers)
- ot.health() - system health check
- ot.debug() - comprehensive debug info
- ot.version() - version string

Parameter Prefixes
- Short prefixes work: ot.tools(p="brave", i="full") equivalent to ot.tools(pattern="brave", info="full")

Trigger Prefixes (invocation styles)
- __ot - short form
- __onetool__run - full explicit call
- __onetool - full name, default tool
- mcp__onetool__run - explicit MCP call

Invocation Styles
- Simple call: __ot func(arg=val)
- Inline backticks: __ot `func(arg=val)`
- Code fence: multi-line Python blocks

Snippet Expansion
- $snippet_name param=value expands server-side

Output Format Control
- __format__ = "yml_h"; ... controls serialization

Output Sanitization
- __sanitize__ = True|False controls external content sanitization
- External content wrapped in boundary tags

Code Execution
- Multi-line code blocks with variables
- Loops and list comprehensions
- Chained operations
- Last expression returned as result

Security - AST Validation
- ot.security() - view security rules
- ot.security(check="pattern") - check specific pattern
- Blocked builtins rejected (exec, eval, compile, etc.)
- Warned imports logged (yaml)
- Tool namespaces whitelisted
- Special dunders: __format__, __sanitize__

Statistics
- ot.stats() - runtime statistics
- ot.stats(period="day|week") - filtered by period
- ot.stats(info="list|min|full") - info levels

Large Output Handling
- ot.result() - query stored large output with pagination

Timing
- ot.timed(expr) - execute a function and return result with timing info

Notifications
- ot.notify(topic="...", message="...") - publish messages to topic files

Configuration
- ot.reload() - force config reload

```

## Tear-Down

```markdown
Title: Tear-Down

Provide a summary of the issues found, grouped by component.
Include:
- Pack/tool issues (wrong params, errors, unexpected output)
- Snippet issues (expansion failures, wrong defaults)
- Feature issues (broken introspection, security gaps, format issues)
- Any missing functionality or documentation gaps
```
