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
- convert with files at demo/data/files
- db with db at demo/data/db/northwind.db (25MB, download via `just demo::setup`)
- excel with files at demo/data/files
- mem: use `tmp/test/` topic prefix for all writes. Test write, read, list, search, toc, slice, snap/restore, stale/refresh, write_batch, read_batch, slice_batch, stats, export/load, update, delete, decay, context, cache_clear. Clean up with `mem.delete(topic="tmp/", confirm=True)` when done.
- diagram: list_providers, get_template, generate_source, render_diagram, get_playground_url
- scaffold: templates, validate, extensions
- web with a known URL like https://en.wikipedia.org/wiki/Python_(programming_language)
- devtools with a known URL like https://en.wikipedia.org/wiki/Python_(programming_language)
- llm: transform with simple data, transform_file with a file from demo/data/files

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
- timer.start(name="label") - start a named timer
- timer.elapsed(name="label") - get elapsed time
- timer.list() - show all active and stored timers
- timer.clear() - clear all running timers

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

## Hints

OneTool is setup correctly with all dependencies and secrets needed.

### Efficiency tips

1. **Check signatures first**: Before testing a pack, run `ot.tools(pattern="packname", info="full")` to see all parameter names and avoid guessing
2. **Batch similar tools**: Test tools in groups - e.g., all search tools together, all file tools together
3. **Skip task tracking**: Don't create granular tasks for each pack - it adds overhead. Just work through the list sequentially
4. **Use minimal test inputs**: Use small counts (2-3) and simple queries to speed up API calls
5. **Test one tool per pack first**: If the first tool works, others likely will too - focus deeper testing on tools with different signatures

### Parameter naming hints

- **excel tools**: Use `filepath` not `path`, and `sheet_name` not `sheet`
  - Example: `excel.info(filepath="demo/data/files/file_example_XLS_1000.xlsx")` not `excel.info(path="data.xlsx")`
  - Example: `excel.read(filepath="demo/data/files/file_example_XLS_1000.xlsx")` not `excel.read(path="data.xlsx", sheet="Sales")`
  - Use `pattern=` not `search_term=` for excel.search
- **ground tools**: Use `max_sources` not `count` to limit results
  - Example: `ground.search(query="topic", max_sources=5)` not `ground.search(query="topic", count=5)`
- **context7 tools**: Different parameters for search vs doc
  - `context7.search()` uses `query=` (not `library_key=`)
  - `context7.doc()` uses `library_key=` and `topic=`
  - Example: `context7.search(query="react")`
  - Example: `context7.doc(library_key="vercel/next.js", topic="routing")`
- **convert tools**: Use `pattern=` and `output_dir=`, not `filepath=`
  - Example: `convert.excel(pattern="demo/data/files/*.xlsx", output_dir="tmp/")` not `convert.excel(filepath="...")`
- **package tools**: `packages=` requires a list, not a string
  - Example: `package.pypi(packages=["requests", "flask"])` not `package.pypi(packages="requests")`
- **llm tools**: Use `data=` not `input=`
  - Example: `llm.transform(data="text", prompt="...")` not `llm.transform(input="text", ...)`
- **db.schema**: Use `table_names=` as a list
  - Example: `db.schema(db_url="...", table_names=["users"])` not `db.schema(db_url="...", table_names="users")`
- **ripgrep.files**: Use `glob=` or `file_type=`, not `pattern=`
  - Example: `ripgrep.files(path=".", file_type="py")` or `ripgrep.files(path=".", glob="*.md")`
- **ripgrep.search**: Use `limit=` not `max_results=` to limit total results
  - Example: `ripgrep.search(pattern="TODO", path=".", limit=5)`
- **mem tools**: Use `topic=` for identifying memories, `content=` for body text. Use `tmp/test/` prefix for all sanity test topics.
  - Example: `mem.write(topic="tmp/test/sanity", content="test data", category="note")`
  - Example: `mem.read(topic="tmp/test/sanity")` - exact topic match
  - Example: `mem.list(topic="tmp/test/")` - list by topic prefix (use `topic=` not `prefix=`)
  - Example: `mem.search(query="test", limit=5)` - semantic search (requires embeddings enabled)
  - Example: `mem.toc(topic="...")` - get section index
  - Example: `mem.slice(topic="...", sections=[1, 2])` - extract by section number
  - Example: `mem.slice_batch(items=[{"topic": "...", "sections": [1]}])` - batch extraction
  - Example: `mem.stale()` - check for outdated file-backed memories
  - Example: `mem.stats()` - get memory statistics
  - Example: `mem.cache_clear()` - clear result cache
  - Clean up: `mem.delete(topic="tmp/", confirm=True)` after testing
- **diagram tools**: Use `provider=` (not `diagram_type=`) and `source=` for rendering
  - Example: `diagram.list_providers()` - see available providers
  - Example: `diagram.get_template(name="flowchart")` - get a template
  - Example: `diagram.generate_source(provider="mermaid", source="graph TD; A-->B", name="test", output_dir="output/")`
  - Example: `diagram.render_diagram(provider="mermaid", source="graph TD; A-->B", name="test")`
- **scaffold tools**: Use `template=` and `name=` for creating extensions
  - Example: `scaffold.templates()` - list available templates
  - Example: `scaffold.extensions()` - list loaded extensions
- **Snippets use abbreviated parameter names** (by design):
  - `$rg` and `$rg_count` use `p=` for pattern (not `pattern=`)
  - `$brv`, `$g`, and `$gh` use `q=` for query (not `query=`)
  - `$c7` and `$c7_eg` use `lib=` for library_key and `q=` for topic
  - `$pkg_pypi` and `$pkg_npm` use `packages=` (comma-separated string, not list)
  - `$web` uses `u=` for URLs (pipe-separated for batch)
  - Example: `$rg p="TODO" ft="py"` not `$rg pattern="TODO" file_type="py"`
- **db tools**: Use SQLite URL format `sqlite:///path/to/db`
  - Example: `db.tables(db_url="sqlite:///demo/data/db/northwind.db")`
  - Example: `db.query(sql="SELECT * FROM Customers LIMIT 3", db_url="sqlite:///demo/data/db/northwind.db")`
  - Not just the file path alone
- **web.fetch**: Use `max_length=` not `max_chars=` to limit output
  - Example: `web.fetch(url="...", max_length=500)`

### Expected behaviors (not bugs)

- `file.write` blocks paths outside allowed directories - this is security working correctly
- `ot.security()` shows allowed builtins, imports, and call rules - this is informational
- `mem.search` requires embeddings enabled in config (`tools.mem.embeddings_enabled: true`)
- `diagram.render_diagram` requires a Kroki server (self-hosted or public) to be configured

### Test URLs

- **web.fetch & devtools.navigate_page**: Use `https://en.wikipedia.org/wiki/Python_(programming_language)` or similar - NOT example.com (doesn't resolve) or `https://en.wikipedia.org` (has captcha)

### Test data notes

All test data lives under `demo/data/`:
- **demo/data/db/northwind.db**: SQLite database (25MB) with 13 tables — download via `just demo::setup`, gitignored
- **demo/data/files/**: Checked-in sample files for excel, convert, and llm testing:
  - `file_example_XLS_1000.xlsx` — Excel workbook
  - `file_example_1MB.docx` — Word document
  - `file_example_PDF_1MB.pdf` — PDF document
  - `file_example_PPT_1MB.pptx` — PowerPoint presentation
- File access: OneTool sandboxes file access — paths outside cwd may be blocked

### MCP Server notes

- **devtools** (26 tools): Browser automation via Chrome DevTools Protocol
  - Automatically launches browser on first tool use
  - Use specific Wikipedia article URLs for testing (e.g., `/wiki/Python_(programming_language)`)
  - Key tools: list_pages, navigate_page, take_snapshot, wait_for, list_console_messages
  - `devtools.wait_for()` requires `text=` parameter (not `selector=`). Example: `devtools.wait_for(text="Python")`
- **github** (37 tools): GitHub API integration
  - Requires authentication via MCP proxy
  - Key tools: search_repositories, get_me, list_commits, get_file_contents
  - Works with both personal and organizational repositories

### Quick smoke test order

Test these first for fast coverage (one tool from each category):

1. `brave.search(query="test", count=2)` - web search
2. `ripgrep.search(pattern="TODO", path=".", limit=3)` - file search
3. `ot.health()` - introspection
4. `$pkg_pypi packages="requests"` - snippets
5. `file.tree(path=".", max_depth=1)` - filesystem
6. `mem.write(topic="tmp/test/smoke", content="hello")` then `mem.read(topic="tmp/test/smoke")` then `mem.delete(topic="tmp/", confirm=True)` - memory
7. `db.tables(db_url="sqlite:///demo/data/db/northwind.db")` - database
8. `ground.search(query="test", max_sources=2)` - grounded search

If all pass, the core infrastructure is working.

### Cleanup after testing

- Delete test memories: `mem.delete(topic="tmp/", confirm=True)`
- Remove any generated files (diagrams, snapshots, converted output)
