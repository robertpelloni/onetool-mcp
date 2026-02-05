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

🔹 **context7 tools**: Use `library_key=` not `library=`

- Example: `context7.doc(library_key="vercel/next.js", topic="routing")` not `context7.doc(library="...")`

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

🔹 **Snippets use abbreviated parameter names** (by design):

- `$rg` and `$rg_count` use `p=` for pattern (not `pattern=`)
- `$brv`, `$g`, and `$gh` use `q=` for query (not `query=`)
- Example: `$rg p="TODO" ft="py"` not `$rg pattern="TODO" file_type="py"`

## Expected behaviors (not bugs)

- `file.write` blocks paths outside allowed directories - this is security working correctly

## Test URLs

🔹 **web.fetch & devtools.navigate_page**: Use `https://en.wikipedia.org/wiki/Python_(programming_language)` or similar - NOT example.com (doesn't resolve) or `https://en.wikipedia.org` (has captcha)

## Test data notes

🔹 **demo/db/northwind.db**: Valid SQLite database (25MB) with 13 tables for testing

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

If all pass, the core infrastructure is working.