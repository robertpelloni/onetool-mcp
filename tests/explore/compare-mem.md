# Memory vs File Access Benchmark

Compare mem (OneTool memory) vs file access (OneTool file/ripgrep) — focus on speed.

Start with `ot.help()` then `ot.tools(pattern="mem", info="core")` and `ot.tools(pattern="timer", info="core")`.

Setup (not part of benchmark):
- `mem.write_batch(topic="proj/onetool-mcp/dev", glob_pattern="dev/**/*.md", toc=True, category="context")`
- `mem.list(topic="proj/onetool-mcp/dev/", format="tree", depth=3)`

Use timer.start/elapsed around each call to measure speed:
  timer.start(name="test-N-file"); <file call>; timer.elapsed(name="test-N-file")
  timer.start(name="test-N-mem"); <mem call>; timer.elapsed(name="test-N-mem")

### Test 1: Agent Context Loading
- **File**: `file.read(path="dev/agents/hints.md")`
- **Mem**: `mem.read(topic="proj/onetool-mcp/dev/agents/hints.md")`
- **File direct**: `file.read(path="dev/agents/hints.md")`

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
