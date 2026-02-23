# Worktree

Git worktree management for parallel agent tasks. Each task gets an isolated directory — agents never touch the main working copy.

## Highlights

- Trunk-mode only: one main repo, multiple isolated task worktrees
- Safe parallel work: tasks never conflict on the working tree
- Conventional commit support with squash + rebase before push
- Requires `git` and `gh` (GitHub CLI, for PR checkout only)

## Roles

| Role | Description |
|------|-------------|
| `base` | Main repo — no `.gitworktree.json` present |
| `work` | Task worktree — `.gitworktree.json` present |

Most management functions (`add`, `list`, `remove`, `clean`) must run from the **base** role. Worker functions (`commit`, `diff`, `status`, `message`, `log`) run from inside a task worktree.

## Functions

| Function | Description |
|----------|-------------|
| `worktree.init()` | One-time setup: add runtime files to `.gitignore` |
| `worktree.add(id, description, branch)` | Create a new task worktree and return the launch command |
| `worktree.list()` | Show all registered tasks and their state |
| `worktree.info()` | Show current worktree role and context |
| `worktree.checkout(branch, pr)` | Switch worktree to an existing branch or PR |
| `worktree.prepare()` | Re-run setup hooks for the current worktree |
| `worktree.log(id)` | Show commit history and diff stat |
| `worktree.diff(id, stat)` | Show changes since root commit |
| `worktree.status(id)` | Show git status |
| `worktree.message()` | Gather context for writing a conventional commit message |
| `worktree.commit(message)` | Squash, rebase onto main, and push |
| `worktree.mark(id, state)` | Set task state (`active`, `done`, `pending`) |
| `worktree.remove(id)` | Remove a task worktree and unregister it |
| `worktree.clean()` | Tear down all tasks and remove manager state |

## Requires

- `git` installed and available in `PATH`
- `gh` (GitHub CLI) — only needed for `worktree.checkout(pr=...)`
- `filelock` Python package (included in `[dev]` extras)

## Configuration

Add to `onetool.yaml` (or an included file):

```yaml
tools:
  worktree:
    workspace_dir: "../{repo}-work/{task_id}"  # task directory template
    branch_name: "{task_id}"                    # branch name template
    launch_cmd: "cd {workspace_dir} && claude" # command printed after worktree.add()
    prepare:                                    # shell commands run after git worktree add
      - "cp ../{repo}/.env {workspace_dir}/.env"
    commit:
      types: [feat, fix, refactor, docs, test, chore]
      scopes: [tool:worktree, config]           # project-specific scopes
```

Available template variables: `{task_id}`, `{repo}`, `{base_dir}`, `{workspace_dir}`.

## Typical Workflow

### From the base repo (orchestrator agent)

```python
# 1. One-time setup
worktree.init()

# 2. Create a task
worktree.add(id="fix-login", description="Fix session expiry bug")
# Returns launch_cmd — run it to start a worker agent in the new directory

# 3. Check on tasks
worktree.list()

# 4. After the worker is done, remove the worktree
worktree.remove(id="fix-login")
```

### From inside a task worktree (worker agent)

```python
# Check current context
worktree.info()

# Make changes, then build a commit message
worktree.message()

# Squash and push to main
worktree.commit(message="fix(auth): resolve session expiry on timeout")
```

## Examples

```python
# Init (run once per repo)
worktree.init()

# Create a task worktree from a specific base branch
worktree.add(id="change-1", description="Add dark mode", branch="main")

# Check what tasks are active
worktree.list()

# Inside a task worktree: get your context
worktree.info()

# See changes so far
worktree.diff()

# Prepare commit message context
worktree.message()

# Commit and push (squashes all commits, rebases onto main)
worktree.commit(message="feat(ui): add dark mode toggle")

# From base: clean up all finished tasks
worktree.clean()
```

## State Values

| State | Description |
|-------|-------------|
| `active` | Task is in progress |
| `done` | Task committed and pushed |
| `pending` | Task created but not started |
| `committing` | Commit in progress (transient) |
