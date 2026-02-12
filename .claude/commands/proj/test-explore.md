---
name: Test Explore
description: Run exploratory tests from tests/explore/
---

Run exploratory test prompts from `tests/explore/`.

## Arguments

Parse the user's input for an optional prompt filename (without .md extension):
- `/test-explore sanity` — run `tests/explore/sanity.md`
- `/test-explore compare-search` — run `tests/explore/compare-search.md`
- `/test-explore test-pack brave,mem,db` — run test-pack with specified packs

If no argument is provided, list available prompts:

```
Available explore prompts:
  sanity          — Full sanity test (packs, snippets, features)
  compare-search  — Compare OneTool vs Claude search tools
  build-tool      — Build a Wikipedia tool pack from scratch
  compare-file    — Compare OneTool vs Claude file operations
  draw-diagram    — Create and render a diagram with the diagram pack
  compare-mem     — Benchmark memory vs file access speed
  test-pack       — Test a pack for defects (takes pack names as args)

Usage: /test-explore <prompt-name> [args]
```

## Execution

1. Read the selected prompt file from `tests/explore/<name>.md`
2. For `sanity`, also check `wip/test-results/sanity-report.yaml` for prior status
3. Follow the instructions in the prompt file
4. For all prompts, explain what you are doing with a short note

## Output Locations

**Issues**: Save defects and problems to `wip/issues/{issue-name}.md`
- Use descriptive kebab-case names (e.g., `mem-export-files.md`, `diagram-template-path-resolution.md`)
- Include issue details, reproduction steps, and expected vs actual behavior

**Test Output**: Save test results and outputs to `wip/test-output/{purpose}.md`
- Use descriptive names matching the test purpose (e.g., `sanity-check.md`, `brave-search-results.md`)
- Include test data, tool outputs, performance metrics, or comparison results

## Error Handling

When errors are encountered, check if they are caused by:
- **Your mistake**: Add a hint to the Hints section of `tests/explore/sanity.md`
- **OneTool defect**: Create `wip/issues/{issue-name}.md` with issue details

## Status Update (sanity only)

After testing each area, update `wip/test-results/sanity-report.yaml`:
- Set `status` to: `pass`, `partial`, or `fail`
- Set `date` to today's date (YYYY-MM-DD)
- Update `checks` list with tools tested
- Add `issues` list if any failures

## Reporting

- Mark issues found as defect
- Mark hints added as hint
- Keep a list of issues and hints, grouped by component
- Show summary table at end with pass/partial/fail counts

**DO NOT MAKE CODE CHANGES** — only create issue files, hint entries, status updates, and test result reports.
