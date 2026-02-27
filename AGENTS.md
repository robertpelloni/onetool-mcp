READ CLAUDE.md for full instructions!!

## Slash Commands
The following project slash commands are available from `.claude/commands/p/*.md`.

### Available slash commands
- `p:consult`: Interactive consultation mode for research and Q&A. Can save findings on explicit request. (file: `/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp-a1/.claude/commands/p/consult.md`)
- `p:fix`: Plan and apply a focused change across code, tests, specs, and docs in one pass. (file: `/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp-a1/.claude/commands/p/fix.md`)
- `p:issue`: Write a local issue file to `wip/issues/` describing a bug or task. (file: `/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp-a1/.claude/commands/p/issue.md`)
- `p:prime`: Load project context from `dev/agents/hints.md`. (file: `/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp-a1/.claude/commands/p/prime.md`)
- `p:review-py`: Comprehensive review for Python projects covering code quality, tests, documentation, and spec alignment. (file: `/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp-a1/.claude/commands/p/review-py.md`)
- `p:stage`: Stage files for a logical change and suggest a conventional commit message. (file: `/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp-a1/.claude/commands/p/stage.md`)
- `p:test-explore`: Run exploratory tests from `tests/explore/`. (file: `/Users/gavin/01-work-thor/projects/group-hobby/onetool-mcp-a1/.claude/commands/p/test-explore.md`)

### How to use slash commands
- Discovery: The list above is the set of project slash commands available in this repo.
- Trigger rules: If the user names a slash command explicitly (for example `/p:stage` or `p:stage`), you should follow the command file for that turn.
- Loading: Read only the specific command file you need before executing the workflow.
- Fallback: If a named command file is missing or unreadable, say so briefly and continue with the closest manual workflow.
