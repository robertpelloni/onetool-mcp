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

## Expected behaviors (not bugs)

- `brave.summarize` is no longer in the pack (removed)
- `file.write` blocks paths outside allowed directories - this is security working correctly
- `llm.transform` returns error if `transform.base_url` not configured
- `code.search` returns error if project not indexed with ChunkHound
- `github` pack unavailable if proxy disconnected
- `wiki` pack may not be available in all configurations

## Test URLs

🔹 **web.fetch**: Use `https://en.wikipedia.org` or `https://en.wikipedia.org/wiki/OpenAI` - NOT example.com as it does not exist

## Test data notes

🔹 **demo/db/northwind.db**: File may be empty (0 bytes) - create a test db in scratchpad instead
🔹 **File access**: OneTool sandboxes file access - paths outside cwd may be blocked

## Quick smoke test order

Test these first for fast coverage (one tool from each category):
1. `brave.search(query="test", count=2)` - web search
2. `ripgrep.search(pattern="TODO", path=".", limit=3)` - file search
3. `ot.health()` - introspection
4. `$pkg_pypi packages="requests"` - snippets
5. `file.tree(path=".", max_depth=1)` - filesystem

If all pass, the core infrastructure is working.
