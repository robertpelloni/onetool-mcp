---
name: Check Dev Docs
description: Verify implementation against dev docs in mem (token-optimised)
category: onetool
tags: [verify, docs, review, mem]
---

## Purpose

Verify that recent code changes (source, tests, specs) follow project conventions by checking against dev docs stored in mem under `proj/onetool-mcp/docs-dev/`.

Uses `mem.toc()`, `mem.search()`, and `mem.slice()` to minimise token usage — never do a full `mem.read()` unless the memory is small enough that slicing would cost more.

## Assumptions

- **Memory is up to date.** The docs in mem reflect the current state of the source files. Do not check for staleness — just trust the stored content.
- **TOC line numbers match source file line numbers.** If you need to cross-reference the original file (e.g., to check surrounding context), the line numbers from `mem.toc()` and `mem.slice()` correspond directly to the source file lines. You can use `Read` with `offset` to jump to the same line in the original file.

## Input

Accepts a description of what was changed, or inspects recent uncommitted changes via `git diff`.

## Strategy

### Step 0: Size-aware approach

Use `mem.list(format="tree", topic="proj/onetool-mcp/docs-dev/")` for a quick overview of available docs, or `mem.list(topic="proj/onetool-mcp/docs-dev/")` to see all docs with their `len=` (content length in chars).

**Size thresholds:**

| Size | Approach |
|------|----------|
| < 800 chars | Just `mem.read()` — cheaper than toc + slice overhead |
| 800-3000 chars | `mem.toc()` then `mem.slice()` targeted sections |
| > 3000 chars | `mem.toc()` then `mem.slice()` — never full-read |

Apply this per-doc when deciding how to fetch content in later steps.

### Step 1: Identify what to check

Determine which convention areas are relevant to the changes:

| Change type | Relevant docs |
|-------------|---------------|
| New/modified tool | `code/creating-tools.md`, `code/tool-configuration.md` |
| Tests added/changed | `code/testing.md` |
| Spec updated | `code/spec-format.md` |
| Config changes | `arch/configuration.md`, `code/configuration.md` |
| Logging added | `code/logging.md` |
| Python style | `code/python-style.md` |
| Git/commit | `code/commits-git.md` |

Only check the docs relevant to the change — skip the rest.

### Step 2: TOC scan (cheap, skip for small docs)

For each relevant doc above the size threshold, fetch the table of contents:

```
mem.toc(topic="proj/onetool-mcp/docs-dev/code/testing.md")
```

Review the section list. Identify 1-3 sections most relevant to the change.

For small docs (< 800 chars), skip the TOC and go straight to `mem.read()`.

### Step 3: Targeted slice (precise)

Read only the sections you need:

```
mem.slice(topic="proj/onetool-mcp/docs-dev/code/testing.md", select="Required Markers")
mem.slice(topic="proj/onetool-mcp/docs-dev/code/creating-tools.md", select="Checklist")
```

Use heading names or section numbers from the TOC. Prefer heading names for clarity.

For line-range access when sections are large:

```
mem.slice(topic="proj/onetool-mcp/docs-dev/code/creating-tools.md", select=":30")
```

Since TOC line numbers match source file lines, you can also cross-reference:

```
# If mem.toc() shows "## Testing" at lines 45-80, you can read the original file at those lines:
Read file="docs-dev/code/creating-tools.md" offset=45 limit=35
```

### Step 4: Pattern search (when unsure which doc)

If you're not sure which doc covers a convention, search:

```
mem.search(query="keyword-only args", mode="pattern", topic="proj/onetool-mcp/docs-dev/", extract=200)
```

Use `mode="pattern"` (LIKE match) — it's fast and doesn't need embeddings. Keep `extract` small (100-200) to preview matches before deciding whether to slice.

### Step 5: Report findings

For each convention area checked, report:

```
## Conventions Check

### Tool structure (creating-tools.md)
- [x] keyword-only args on all functions
- [x] Google-style docstrings
- [x] Added to __all__
- [ ] Missing: LogSpan wrapper (if applicable)

### Tests (testing.md)
- [x] @pytest.mark.unit + @pytest.mark.tools markers
- [x] Tests in correct directory

### Spec (spec-format.md)
- [x] WHEN/THEN format
- [x] SHALL for normative requirements
- [x] At least one scenario per requirement
```

Flag any violations. If everything passes, confirm with a brief summary.

## Rules

- **Size-aware reads** — full-read small docs, toc+slice large ones
- **Batch TOC calls** — fetch all relevant TOCs in one parallel tool call
- **Batch slice calls** — fetch all needed sections in one parallel tool call
- **Skip irrelevant docs** — only check what the change touches
- **Pattern search as fallback** — only when you can't map the change to a known doc
- **Trust the memory** — don't check staleness, assume docs are current
