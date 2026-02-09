# Sanity Test Hints

OneTool is setup correctly with all dependencies and secrets needed.

## Efficiency tips

1. **Check signatures first**: Before testing a pack, run `ot.tools(pattern="packname", info="full")` to see all parameter names and avoid guessing
2. **Batch similar tools**: Test tools in groups - e.g., all search tools together, all file tools together
3. **Skip task tracking**: Don't create granular tasks for each pack - it adds overhead. Just work through the list sequentially
4. **Use minimal test inputs**: Use small counts (2-3) and simple queries to speed up API calls
5. **Test one tool per pack first**: If the first tool works, others likely will too - focus deeper testing on tools with different signatures

## Parameter naming hints

🔹 **excel tools**: Use `filepath` not `path`, and `sheet_name` not `sheet`

- Example: `excel.info(filepath="data.xlsx")` not `excel.info(path="data.xlsx")`
- Example: `excel.read(filepath="data.xlsx", sheet_name="Sales")` not `excel.read(path="data.xlsx", sheet="Sales")`
- Use `pattern=` not `search_term=` for excel.search

🔹 **ground tools**: Use `max_sources` not `count` to limit results

- Example: `ground.search(query="topic", max_sources=5)` not `ground.search(query="topic", count=5)`

🔹 **context7 tools**: Different parameters for search vs doc

- `context7.search()` uses `query=` (not `library_key=`)
- `context7.doc()` uses `library_key=` and `topic=`
- Example: `context7.search(query="react")`
- Example: `context7.doc(library_key="vercel/next.js", topic="routing")`

🔹 **convert tools**: Use `pattern=` and `output_dir=`, not `filepath=`

- Example: `convert.excel(pattern="data/*.xlsx", output_dir="output/")` not `convert.excel(filepath="...")`

🔹 **package tools**: `packages=` requires a list, not a string

- Example: `package.pypi(packages=["requests", "flask"])` not `package.pypi(packages="requests")`

🔹 **llm tools**: Use `data=` not `input=`

- Example: `llm.transform(data="text", prompt="...")` not `llm.transform(input="text", ...)`

🔹 **db.schema**: Use `table_names=` as a list

- Example: `db.schema(db_url="...", table_names=["users"])` not `db.schema(db_url="...", table_names="users")`

🔹 **ripgrep.files**: Use `glob=` or `file_type=`, not `pattern=`

- Example: `ripgrep.files(path=".", file_type="py")` or `ripgrep.files(path=".", glob="*.md")`

🔹 **ripgrep.search**: Use `limit=` not `max_results=` to limit total results

- Example: `ripgrep.search(pattern="TODO", path=".", limit=5)`

🔹 **mem tools**: Use `topic=` for identifying memories, `content=` for body text

- Example: `mem.write(topic="test/sanity", content="test data", category="note")`
- Example: `mem.read(topic="test/sanity")` - exact topic match
- Example: `mem.list(topic="test/")` - list by topic prefix (use `topic=` not `prefix=`)
- Example: `mem.search(query="test", limit=5)` - semantic search (requires embeddings enabled)
- Example: `mem.toc(topic="...")` - get section index
- Example: `mem.slice(topic="...", sections=[1, 2])` - extract by section number
- Example: `mem.slice_batch(items=[{"topic": "...", "sections": [1]}])` - batch extraction
- Example: `mem.stale()` - check for outdated file-backed memories
- Example: `mem.stats()` - get memory statistics
- Example: `mem.cache_clear()` - clear result cache
- Use `mem.delete(topic="test/")` to clean up test memories after testing

🔹 **diagram tools**: Use `provider=` (not `diagram_type=`) and `source=` for rendering

- Example: `diagram.list_providers()` - see available providers
- Example: `diagram.get_template(name="flowchart")` - get a template
- Example: `diagram.generate_source(provider="mermaid", source="graph TD; A-->B", name="test", output_dir="output/")`
- Example: `diagram.render_diagram(provider="mermaid", source="graph TD; A-->B", name="test")`

🔹 **scaffold tools**: Use `template=` and `name=` for creating extensions

- Example: `scaffold.templates()` - list available templates
- Example: `scaffold.extensions()` - list loaded extensions

🔹 **Snippets use abbreviated parameter names** (by design):

- `$rg` and `$rg_count` use `p=` for pattern (not `pattern=`)
- `$brv`, `$g`, and `$gh` use `q=` for query (not `query=`)
- `$c7` and `$c7_eg` use `lib=` for library_key and `q=` for topic
- `$pkg_pypi` and `$pkg_npm` use `packages=` (comma-separated string, not list)
- `$web` uses `u=` for URLs (pipe-separated for batch)
- Example: `$rg p="TODO" ft="py"` not `$rg pattern="TODO" file_type="py"`

🔹 **db tools**: Use SQLite URL format `sqlite:///path/to/db`

- Example: `db.tables(db_url="sqlite:///demo/db/northwind.db")`
- Example: `db.query(sql="SELECT * FROM users", db_url="sqlite:///data.db")`
- Not just the file path alone

🔹 **web.fetch**: Use `max_length=` not `max_chars=` to limit output

- Example: `web.fetch(url="...", max_length=500)`

## Expected behaviors (not bugs)

- `file.write` blocks paths outside allowed directories - this is security working correctly
- `ot.security()` shows allowed builtins, imports, and call rules - this is informational
- `mem.search` requires embeddings enabled in config (`tools.mem.embeddings_enabled: true`)
- `diagram.render_diagram` requires a Kroki server (self-hosted or public) to be configured

## Test URLs

🔹 **web.fetch & devtools.navigate_page**: Use `https://en.wikipedia.org/wiki/Python_(programming_language)` or similar - NOT example.com (doesn't resolve) or `https://en.wikipedia.org` (has captcha)

## Test data notes

🔹 **demo/db/northwind.db**: Valid SQLite database (25MB) with 13 tables for testing

🔹 **demo/data/**: Contains test files for convert and excel packs:
- `file_example_XLS_1000.xlsx` and `sample_sales.xlsx` - Excel files
- `file_example_1MB.docx` - Word document
- `file_example_PPT_1MB.pptx` - PowerPoint presentation
- `attention-paper.pdf` and `gpt3-paper.pdf` - PDF documents

🔹 **File access**: OneTool sandboxes file access - paths outside cwd may be blocked

## MCP Server notes

🔹 **devtools** (26 tools): Browser automation via Chrome DevTools Protocol

- Automatically launches browser on first tool use
- Use specific Wikipedia article URLs for testing (e.g., `/wiki/Python_(programming_language)`)
- Key tools: list_pages, navigate_page, take_snapshot, wait_for, list_console_messages
- `devtools.wait_for()` requires `text=` parameter (not `selector=`). Example: `devtools.wait_for(text="Python")`

🔹 **github** (37 tools): GitHub API integration

- Requires authentication via MCP proxy
- Key tools: search_repositories, get_me, list_commits, get_file_contents
- Works with both personal and organizational repositories

## Quick smoke test order

Test these first for fast coverage (one tool from each category):

1. `brave.search(query="test", count=2)` - web search
2. `ripgrep.search(pattern="TODO", path=".", limit=3)` - file search
3. `ot.health()` - introspection
4. `$pkg_pypi packages="requests"` - snippets
5. `file.tree(path=".", max_depth=1)` - filesystem
6. `mem.write(topic="test/smoke", content="hello")` then `mem.read(topic="test/smoke")` then `mem.delete(prefix="test/")` - memory
7. `db.tables(db_url="demo/db/northwind.db")` - database
8. `ground.search(query="test", max_sources=2)` - grounded search

If all pass, the core infrastructure is working.

## Cleanup after testing

- Delete test memories: `mem.delete(prefix="test/")`
- Remove any generated files (diagrams, snapshots, converted output)
