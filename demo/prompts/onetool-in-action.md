# OneTool in Action


## Compare the Search

```text
Compare OneTool search tools to Claude Code's built-in WebSearch.

Start with `ot.agent_hints()` to learn available tools and calling conventions.

Question: MCP resources vs tools — what's the difference?

Search tools to compare:
- OneTool: brave.search, ground.docs, ground.search, context7.search, context7.doc
- Claude: WebSearch

For MCP-specific questions, also try:
- `context7.doc(library_key="/websites/modelcontextprotocol_io_specification_2025-11-25", topic="resources vs tools")`
- `web.fetch_batch(urls=["https://modelcontextprotocol.info/docs/concepts/resources/", "https://modelcontextprotocol.info/docs/concepts/tools/"])`

Optimise each call for best results (count, format, links).
DO NOT answer the question — just run the searches and compare output.

Report as a markdown table:

| Tool | Speed (1-10) | Quality (1-10) | Best For | Call Used |
```

## Build a Wikipedia Tool

```text
Build a "wiki" tool pack with 3 tools: page, summary, data.

Start with `ot.agent_hints()` then `ot.tools(pattern="scaffold", info="full")`.

Steps:
1. Check tools_dir is configured: `ot.config()`
2. Scaffold: `scaffold.create(name="wiki", scope="global", template="extension")`
3. Implement:
   - `page(slug, size=10)` — fetch https://en.wikipedia.org/wiki/{slug}, truncate to size KB
   - `summary(slug, prompt)` — use `call_tool("llm.transform", ...)` to summarize page content
   - `data(slug)` — fetch JSON from https://en.wikipedia.org/api/rest_v1/page/summary/{slug}
   - Use httpx.Client for HTTP, LogSpan for logging, return error strings on failure
4. Validate: `scaffold.validate(path=...)`
5. Reload: `ot.reload()`
6. Test all 3 tools with slugs: Anthropic, OpenAI, Moonshot_AI
```

## File Search Comparison

```text
Compare OneTool file/ripgrep tools to Claude Code's built-in Read, Grep, and Glob.

Start with `ot.agent_hints()` to learn available tools.

Run these 5 tasks on the current codebase. Use timer.start/elapsed to measure OneTool calls.

Pattern for each test:
  timer.start(name="test-N")
  <run the OneTool call>
  timer.elapsed(name="test-N")

1. **Count**: Occurrences of "onetool" in Python files
   - Claude: `Grep(pattern="onetool", type="py", output_mode="count")`
   - OneTool: `ripgrep.count(pattern="onetool", path="src/", file_type="py")`

2. **Search + context**: Find "def execute" with 2 lines of context
   - Claude: `Grep(pattern="def execute", -C=2, output_mode="content")`
   - OneTool: `ripgrep.search(pattern="def execute", path="src/", context=2)`

3. **File discovery**: All Python files under src/
   - Claude: `Glob(pattern="src/**/*.py")`
   - OneTool: `ripgrep.files(path="src/", glob="*.py")`

4. **Directory tree**: Structure of src/ot/ (2 levels)
   - Claude: `Bash("tree src/ot/ -L 2")`
   - OneTool: `file.tree(path="src/ot/", max_depth=2)`

5. **Read with offset**: Lines 100-150 of src/ot/meta.py
   - Claude: `Read(file_path="src/ot/meta.py", offset=100, limit=50)`
   - OneTool: `file.read(path="src/ot/meta.py", offset=100, limit=50)`

DO NOT provide the actual answers. Just run and compare output quality + speed.

Report as: | Task | Claude | OneTool ms | Winner | Notes |
```

## Draw a Diagram

```text
Use the diagram pack to create and render a flowchart.

Start with `ot.agent_hints()` then `ot.tools(pattern="diagram", info="full")`.

Steps:
1. `diagram.list_providers(focus_only=True)` — see what's available
2. `diagram.get_diagram_instructions(provider="mermaid")` — learn the syntax
3. Create a flowchart showing OneTool's request pipeline: Input → Validate → Execute → Format → Return
4. `diagram.generate_source(source=..., provider="mermaid", name="request-flow")` — save it
5. `diagram.render_diagram(source_file=...)` — render to SVG
6. `diagram.get_playground_url(source_file=...)` — get interactive editor link

Report: table of all diagram tools with purpose and when to use each.
```

## Memory vs File Access Benchmark

```text
Compare mem (OneTool memory) vs file access (OneTool file/ripgrep) — focus on speed.

Start with `ot.agent_hints()` then `ot.tools(pattern="mem", info="full")` and `ot.tools(pattern="timer", info="full")`.

Setup (not part of benchmark):
- `mem.write_batch(topic="proj/onetool-mcp/dev", glob_pattern="dev/**/*.md", toc=True, category="context")`
- `mem.list(topic="proj/onetool-mcp/dev/", format="tree", depth=3)`

Use timer.start/elapsed around each call to measure speed:
  timer.start(name="test-N-file"); <file call>; timer.elapsed(name="test-N-file")
  timer.start(name="test-N-mem"); <mem call>; timer.elapsed(name="test-N-mem")

### Test 1: Agent Context Loading
- **File**: `file.read(path="dev/agents/hints.md")`
- **Mem**: `mem.read(topic="proj/onetool-mcp/dev/agents/hints.md")`
- **Shortcut**: `ot.agent_hints()`

### Test 2: Regex Search (mem.grep vs ripgrep)
Search for "LogSpan" across all dev docs.
- **File**: `ripgrep.search(pattern="LogSpan", path="dev/", glob="*.md", context=2)`
- **Mem**: `mem.grep(pattern="LogSpan", topic="proj/onetool-mcp/dev/", context=2)`

### Test 3: Batch Read (8 arch docs)
- **File**: `file.read(path="dev/project/arch/index.md")` (repeat for each file)
- **Mem**: `mem.read_batch(topic="proj/onetool-mcp/dev/project/arch/")`

### Test 4: Section Extraction (3 sections from 3 docs)
- **File**: 3x `file.read(path="...", offset=X, limit=Y)` — use mem.toc to find line ranges
- **Mem**: `mem.slice_batch(items=[{"topic": "...", "select": "SectionName"}, ...])`

### Test 5: Pattern Search + Context
- **File**: `ripgrep.search(pattern="def \\w+\\(", path="dev/", glob="*.md", context=1)`
- **Mem**: `mem.grep(pattern="def \\w+\\(", topic="proj/onetool-mcp/dev/", context=1)`

After all tests, run `timer.list()` to see all results.

Report to ./tmp/mem-vs-file-{yyyymmdd}.md:

| Test | File ms | Mem ms | Winner | Notes |
```

## Test a Pack

```text
Test an OneTool pack — find defects and suggest improvements.

Start with `ot.agent_hints()` then `ot.tools(pattern="{pack}", info="full")`.

Run each tool in the pack with realistic inputs. Note errors, edge cases, and UX issues.

Write findings to ./plan/fix/{pack}-fix.md

Test this pack:
```
