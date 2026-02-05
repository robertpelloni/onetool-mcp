---
name: Sanity
description: Run OneTool sanity tests to verify packs, snippets, and features
---

Execute sanity tests from `tests/sanity/test_sanity.md`.

## Arguments

Parse the user's input for these optional arguments:
- `retest=<area>` - Retest a specific area (e.g., `retest=brave`, `retest=snippets`, `retest=features`)
- `retest=all` - Run full test suite
- `retest=failed` - Retest only areas with status "partial" or "fail"

If no argument provided, check `wip/test-results/sanity-report.yaml` and suggest retesting failed/partial areas.

## Setup

1. Read `wip/test-results/sanity-report.yaml` to see current test status
2. Read `tests/sanity/test_sanity-hints.md` for efficiency tips
3. Read `tests/sanity/test_sanity.md` for test definitions
4. For all prompts, explain what you are doing with 💭

## Execution

Based on the `retest` argument:
- **Specific pack** (e.g., `retest=brave`): Test only that pack's tools
- **`retest=snippets`**: Test all snippets
- **`retest=features`**: Test all feature categories
- **`retest=failed`**: Test areas with status "partial" or "fail"
- **`retest=all`** or no argument on first run: Full test suite

## Error Handling

When errors are encountered, check if they are caused by:
- **Your mistake**: Add a hint to `tests/sanity/test_sanity-hints.md` to avoid in future
- **OneTool defect**: Create `wip/issues/{issue-name}.md` with issue details

## Status Update

After testing each area, update `wip/test-results/sanity-report.yaml`:
- Set `status` to: `pass`, `partial`, or `fail`
- Set `date` to today's date (YYYY-MM-DD)
- Update `checks` list with tools tested
- Add `issues` list if any failures
- Add `notes` with any relevant context

Example update for a pack:
```yaml
brave:
  status: pass
  date: 2026-02-01
  checks:
    - search
    - news
```

## Reporting

- Mark issues found as 🪲
- Mark hints added as 🔹
- Keep a list of issues and hints, grouped by component
- Show summary table at end with pass/partial/fail counts
- All test tracking and results are stored in `wip/test-results/sanity-report.yaml`

**DO NOT MAKE CODE CHANGES** - only create issue files, hint entries, status updates, and test result reports.
