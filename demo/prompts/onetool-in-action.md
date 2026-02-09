# OneTool in Action


## Compare the Search

```
Title: Compare the Search
Explain each step so it is easy to follow what you did and why. Use 🧿 to highlight these explanations.

Use onetool ot.help() with info="full" to understand how best to use onetool tools. 
I want to compare onetool tools and snippets to Claude Code's built-in search.
Optimise calls to get the best results. Tweak onetool tool parameters for better output: increase count, adjust return format, include links, etc.

Test both tools and relevant snippets to answer the questions below.
Compare and score them (out of 10) based on quality.

Result MUST be in a markdown table with columns:
Tool | Speed | Quality | Recommended For | Call/Snippet
Call/Snippet should have all parameters for both Claude and OneTool.

Run searches sequentially.
DO NOT actually provide the answer for the question.

Tools and snippets to use:
- OneTool Tools: brave.search, ground.docs, ground.search, context7
- OneTool Snippets: $brv, $brv_research, $c7, $g, $g_reddit
- Claude: WebSearch

For MCP questions, use library="/websites/modelcontextprotocol_io_specification_2025-11-25" with $c7

Also test batch_fetch with these URLs for comparison:
- https://modelcontextprotocol.info/docs/concepts/resources/
- https://modelcontextprotocol.info/docs/concepts/tools/

Question:
- MCP resources vs tools?

Provide a simple summary table of the tools at the end

Finally, list all Claude and onetool commands used.
```

## Build a Wikipedia Tool

```
Title: Build a Wikipedia Tool
Explain each step so it is easy to follow what you did and why. Use 🧿 to highlight these explanations.

- Learn onetool with `ot.help(info="full")` and `scaffold.templates()`
- Verify tools_dir is configured using `ot.config()`. If not, add `tools/**/*.py` to the config.
- Scaffold a "wiki" pack using `scaffold.create(name="wiki", scope="global", template="extension")`
- Hint: Check `ot.tools(pattern="...", info="full")` for the correct parameter names

- Implement these tools:
  - `page(slug, size=10)` - Fetch HTML from https://en.wikipedia.org/wiki/{slug}, truncate to size KB
  - `summary(slug, prompt)` - Use call_tool("llm.transform", ...) to summarize page content
  - `data(slug)` - Fetch JSON from https://en.wikipedia.org/api/rest_v1/page/summary/{slug}

- Implementation notes:
  - Use `from ot.logging import LogSpan` for structured logging
  - Use `from ot.tools import call_tool` for llm.transform only
  - Use httpx.Client for HTTP requests (bundled, no deps needed)
  - Return error strings/dicts on failure (no raise)

- Validate with `scaffold.validate(path=...)` and show the output as markdown

- Reload with `ot.reload()` before testing the new tool

- Test all three tools with slugs: Anthropic, OpenAI, Moonshot_AI

Finally, list all onetool commands used.
```

## File me away

```
Title: Compare File Search & Read Tools
Explain each step so it is easy to follow what you did and why. Use 🧿 to highlight these explanations.

Use onetool ot.help() with info="full" to understand how best to use onetool tools.
I want to compare onetool file/ripgrep tools to Claude Code's built-in Read, Grep, and Glob tools.
Optimise calls to get the best results. Tweak onetool tool parameters for better output: adjust context lines, file types, output format, etc.

Test both tools for each task below.
Compare and score them (out of 10) based on quality.

Result MUST be in a markdown table with columns:
Task | Claude Speed | Claude | OneTool | Recommended For | Call/Snippet
Call/Snippet should have all parameters for both Claude and OneTool.

Run searches sequentially. DO NOT provide the actual answer for each task.

Tools to use:
- OneTool: ripgrep.search, ripgrep.count, ripgrep.files, file.read, file.tree
- Claude: Read, Grep (with output_mode variants), Glob, Bash (for tree)

Use the current codebase (onetool-mcp) for all tests.

## File Search Tasks

1. **Pattern Count**: Count occurrences of "onetool" in Python files
   - Claude: Grep with output_mode="count"
   - OneTool: ripgrep.count

2. **Pattern Search with Context**: Find all uses of "def execute" with 2 lines of context
   - Claude: Grep with -C=2, output_mode="content"
   - OneTool: ripgrep.search with context

3. **File Discovery**: Find all Python files in src/ directory
   - Claude: Glob with pattern="src/**/*.py"
   - OneTool: ripgrep.files with file_type filter

4. **Directory Tree**: Show directory structure of src/ot/ (max 2 levels deep)
   - Claude: Bash with tree command (or ls -R if tree unavailable)
   - OneTool: file.tree with max_depth

5. **File Read**: Read the first 30 lines of src/ot/meta.py
   - Claude: Read tool with limit
   - OneTool: file.read with limit

6. **Offset Read**: Read lines 100-150 of src/ot/meta.py
   - Claude: Read with offset and limit
   - OneTool: file.read with offset and limit

7. **Batch File Read**: Read the first 20 lines of these 3 files in one operation:
   - src/ot/__init__.py
   - src/ot/server.py
   - src/ot/paths.py
   - Claude: Multiple Read calls (parallel if possible)
   - OneTool: file.read called 3 times (or explore batch options)

## Comparison Questions
- Which provides better context formatting?
- Which handles glob patterns more intuitively?
- Which is better for batch operations?
- How do offset semantics differ between tools?

Finally, list all Claude and OneTool commands used with full parameters.
```


## Draw me a diagram

```
Title: Draw me a diagram
Explain each step so it is easy to follow what you did and why. Use 🧿 to highlight these explanations.

- Learn onetool with `ot.help(info="full")` and `ot.tools(pattern="diagram", info="full")`

## Discovery Phase

1. **List Providers**: Use `diagram.list_providers(focus_only=True)` to see supported diagram types
2. **Get Instructions**: Use `diagram.get_diagram_instructions(provider="mermaid")` for syntax guidance
3. **Check Policy**: Use `diagram.get_diagram_policy()` to understand usage rules
4. **Check Config**: Use `diagram.get_output_config()` for output settings

## Creation Phase

5. **Generate Source**: Create a flowchart showing the OneTool diagram workflow itself:
   - Use `diagram.generate_source()` to save and validate the source
   - The diagram should show: Discovery → Creation → Render phases
   - Include these tools: list_providers, get_instructions, generate_source, render_diagram, batch_render

6. **Get Playground URL**: Use `diagram.get_playground_url()` for interactive editing

## Render Phase

7. **Render Diagram**: Use `diagram.render_diagram(source_file=...)` to render the saved source
8. **Verify Output**: Confirm SVG was generated and note the file path

## Comparison Table

Create a table showing diagram pack capabilities:

Columns:
Tool | Purpose | Key Parameters | When to Use

Tools to cover:
- diagram.list_providers
- diagram.get_diagram_instructions
- diagram.get_diagram_policy
- diagram.get_output_config
- diagram.generate_source
- diagram.get_playground_url
- diagram.render_diagram
- diagram.batch_render
- diagram.render_directory
- diagram.get_render_status
- diagram.get_template

Finally, list all onetool commands used with full parameters.
```

## Memory vs File Access Benchmark

```text
Title: Memory vs File Access Performance Comparison
Explain each step so it is easy to follow what you did and why. Use 🧿 to highlight these explanations.

## Reference: Hints & Gotchas

Read these before starting. They apply across all phases.

**Mem basics:**
- Files must be pre-loaded into mem before benchmarking (use mem.write_batch)
- Memory topics use full path patterns: dev/project/arch/index.md → proj/onetool-mcp/dev/project/arch/index.md
- toc=True when writing is CRITICAL — without it, section slicing won't work
- Section names are case-sensitive — use exact headings from mem.toc output
- mem.read (single) vs mem.read_batch (multiple) vs mem.slice_batch (sections)
- mem.read mode parameter: "content" (default, content only), "toc" (section index), "meta" (metadata only), "all"
- meta=True adds a metadata header — omit it for content-only comparison (fairer token count)
- extract parameter on mem.search provides inline snippets immediately

**File basics:**
- Read tool needs absolute paths: `/Users/.../dev/project/guides/creating-tools.md`
- Use Glob to find absolute paths: `Glob(pattern="dev/project/guides/*.md")`
- Call multiple Read tools in parallel for fair batch comparison
- Grep gives line matches only — full context requires additional Read calls

**Fair comparison rules:**
- Don't compare Grep (files only) to mem.search (with content) — match capability levels
- Load files once before benchmarking; loading cost is not part of the benchmark
- Record actual token counts — do not pre-judge results

## Phase 1: Discovery (No Token Tracking)

1. **Learn OneTool & Mem API**
   - `ot.help(info="full")` and `ot.tools(pattern="mem", info="full")`

2. **Explore Mem State**
   - `mem.stats()` — current memory state
   - `mem.list(format="tree", depth=3)` — indexed content
   - `mem.toc(topic="...")` — section structure of key documents
   - If dev/ docs aren't loaded: `mem.write_batch(topic="proj/onetool-mcp/dev", glob_pattern="dev/**/*.md", toc=True)`

3. **Identify Test Files**
   - Check what dev/ documentation exists in mem vs filesystem
   - Pick representative files: single doc (~9KB), batch (8 arch docs ~19KB), sections from 3+ docs, cross-doc search

## Phase 2: Setup

4. **Load Target Files into Mem** (one-time, not part of benchmark)
   - `mem.write_batch(topic="proj/onetool-mcp/dev", glob_pattern="dev/**/*.md", toc=True, category="context")`
   - Verify: `mem.list(topic="proj/onetool-mcp/dev/", format="tree", depth=5, limit=100)`

5. **Prepare Baseline File Paths**
   - Note absolute paths, file sizes, and line counts: `Bash("wc -l dev/**/*.md")`

## Phase 3: Performance Benchmark (TRACK TOKENS FROM HERE)

Record starting token count before beginning tests.

### Test 1: Single Document Access
- **File**: Read tool on full document
- **Mem**: `mem.read(topic="proj/onetool-mcp/dev/project/guides/creating-tools.md")`
- Record: tokens used, perceived speed, content received

### Test 2: Batch Document Access (8 arch docs)
- **File**: 8 parallel Read calls for dev/project/arch/*.md
- **Mem**: `mem.read_batch(topic="proj/onetool-mcp/dev/project/arch/", limit=10)`
- Record: tokens used, perceived speed, number of docs retrieved

### Test 3: Targeted Section Extraction (3 sections from 3 docs)
- **File**: Read full files with offset/limit, manually locate sections (use mem.toc to find line numbers)
- **Mem**: `mem.slice_batch(items=[{"topic": "...", "select": "SectionName"}, ...])`
- Record: tokens used, precision of extraction

### Test 4: Search + Extract
- **File**: `Grep(pattern="LogSpan", path="dev/", glob="*.md", output_mode="content", head_limit=10)` + Read calls for context
- **Mem**: `mem.search(query="LogSpan", mode="pattern", topic="proj/onetool-mcp/dev/", limit=5, extract=500)`
- Record: tokens used, relevance of results, steps required

### Test 5: Load, Use, Delete Lifecycle
- Load: `mem.write(topic="temp/test/demo", file="demo/prompts/onetool-in-action.md", toc=True, category="note")`
- Use: `mem.read(topic="temp/test/demo")` and `mem.slice(topic="temp/test/demo", select="...")`
- Cleanup: `mem.delete(topic="temp/", confirm=True)`
- Compare to: Read tool on same file
- Record: tokens saved across multiple accesses

## Phase 4: Analysis & Report

6. **Calculate Metrics**
   - Token efficiency: (file_tokens - mem_tokens) / file_tokens * 100
   - Speed perception: subjective 1-5 rating
   - Use case fit: when to use each method

7. **Write Report to ./tmp/mem-vs-file-{yyyymmdd}.md**

   ```markdown
   # Memory vs File Access Comparison

   ## Executive Summary
   - Winner by token efficiency: [File|Mem]
   - Winner by speed: [File|Mem]
   - Overall recommendation: [contextual]

   ## Results

   | Use Case | File Method | File Tokens | File Calls | Mem Method | Mem Tokens | Mem Calls | Savings |
   |----------|------------|-------------|-----------|------------|------------|-----------|---------|
   | Single document | Read | ? | 1 | mem.read | ? | 1 | ?% |
   | Batch (8 docs) | 8× Read | ? | 8 | mem.read_batch | ? | 1 | ?% |
   | Section extraction | 3× Read + offsets | ? | 3 | mem.slice_batch | ? | 1 | ?% |
   | Search + context | Grep + Read(s) | ? | 2+ | mem.search | ? | 1 | ?% |
   | Load/use/delete | Read | ? | 1 | mem lifecycle | ? | 3 | ?% |

   Each row compares File vs Memory for the SAME task. Fill with actual measured values.

   ## Use Case Recommendations
   ### Use File Access When: ...
   ### Use Mem Access When: ...

   ## Detailed Test Results
   [Per-test observations and commands used]

   ## Commands Reference
   [All commands used, grouped by File vs Mem]
   ```

```

## Test a Pack

```text
Explain each step so it is easy to follow what you did and why. Use 🧿 to highlight these explanations.
Learn onetool with `ot.help(info="full")`
Find defect and suggest improvements.

Write the improvements and defects to ./plan/fix/{pack}-fix.md

Test out the following pack:

```
