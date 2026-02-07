# Stage Changes for Commit

Stage files for a logical change and suggest a conventional commit message.

## Behavior

1. **Analyze Changed Files**
   - Run `git status --short` to see all changes
   - Run `git diff --cached` for staged changes (if any)
   - Run `git diff` for unstaged changes
   - Identify the primary change type and scope

2. **Stage Related Files**
   - Ask user which files to stage (if not already specified)
   - Stage files with `git add <files>`
   - Confirm staging with `git status --short`

3. **Suggest Commit Message**
   - Analyze the staged changes
   - Use type/scope of the MOST IMPORTANT change
   - List all changes in description (most important first)
   - Generate a conventional commit message:
     ```
     <type>(scope): <description>
     Ref: #123
     ```
   - Description: 50-72 chars ideal, can be longer if needed
   - Multiple changes: separate with semicolons
   - Second line for issue reference only (if applicable)

## Commit Message Format

### Type (required)
- `feat` - New feature or capability
- `fix` - Bug fix
- `refactor` - Code restructuring without behavior change
- `perf` - Performance improvement
- `docs` - Documentation changes
- `test` - Test additions or changes
- `build` - Build system or dependency changes
- `ci` - CI/CD pipeline changes
- `chore` - Maintenance tasks (cleanup, formatting, etc.)
- `style` - Code style/formatting (no logic change)
- `revert` - Revert a previous commit

### Scope (optional but recommended)

**Core Systems:**
- `config` - Configuration system (loader, models, secrets)
- `cli` - Command-line interface (onetool, bench CLIs)
- `serve` - MCP server functionality
- `proxy` - MCP proxy/client functionality
- `security` - Security validation and policies
- `stats` - Statistics collection and reporting
- `logging` - Logging infrastructure

**Tool Packs** (use format `tool:name`):
- `tool:brave` - Brave search
- `tool:code` - Code search
- `tool:context7` - Context7 documentation
- `tool:convert` - Document conversion
- `tool:db` - Database operations
- `tool:diagram` - Diagram generation
- `tool:excel` - Excel operations
- `tool:file` - File operations
- `tool:ground` - Grounding search
- `tool:llm` - LLM transform
- `tool:ot` - Meta/introspection tools
- `tool:package` - Package info
- `tool:ripgrep` - Code search
- `tool:scaffold` - Tool scaffolding
- `tool:web` - Web fetch

**Benchmark:**
- `bench` - Benchmark harness
- `bench:config` - Benchmark configuration
- `bench:harness` - Benchmark execution
- `bench:metrics` - Metrics collection
- `bench:tui` - Terminal UI

**Other:**
- `deps` - Dependency updates
- `release` - Release preparation
- `demo` - Demo/example code
- `dx` - Developer experience

### Description (required)
- Use imperative mood: "add feature" not "added feature"
- Start with lowercase
- No period at the end
- Keep concise: 50-72 chars ideal, longer OK if needed
- Be specific and descriptive

### Issue Reference (optional)
- Add `Ref: #123` on second line if there's an issue
- Use singular "Ref" not "Refs"

## Examples

### Single Change ✅
```
feat(tool:brave): add news search endpoint
fix(config): resolve include paths from ot_dir not config_dir
refactor(config): remove project-level configuration support
perf(tool:ripgrep): reduce token usage by 50%
```

### Multiple Changes (most important first) ✅
```
feat(config): add compact array format; update security template; fix tests
fix(tool:brave): prevent racing; add retry logic; improve error handling
refactor(config): simplify loader; remove inheritance; flatten includes
docs: update readme; fix typos in contributing guide; add examples
```

### With Issue Reference ✅
```
fix(tool:brave): prevent racing of requests; add retry logic
Ref: #123
```

### Bad Examples ❌
```
❌ Added news search and fixed a bug
   (past tense, no scope/type)

❌ feat(tool:brave): Add news search endpoint.
   (capitalized, has period)

❌ fix: bug fixes
   (too vague)

❌ Refs: #123
   (use "Ref" not "Refs")
```

## Usage

Simply call `/proj:stage` and the agent will:
1. Show you the current git status
2. Analyze the changes
3. Ask which files you want to stage (or stage all related files)
4. Stage the files
5. Suggest a conventional commit message based on the changes

The agent will NOT commit - it only stages and suggests. You can then:
- Accept the suggested message and commit manually
- Modify the message and commit
- Use `/commit` slash command with the suggested message
- Continue making changes before committing

## Notes

- **DO NOT commit** - this command only stages
- Focus on logical, atomic changes
- One change type per commit (don't mix feat + fix)
- If changes span multiple areas, consider multiple commits
- Breaking changes should include migration notes in body
