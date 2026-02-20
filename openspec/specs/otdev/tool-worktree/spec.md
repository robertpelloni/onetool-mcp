# tool-worktree Specification

## Purpose

Git worktree management for parallel agent workflows. Enables multiple agents
to work on independent tasks in isolated directories (trunk mode). Each task
gets its own git worktree and branch; agents never touch the main working copy.

Config: `tools.worktree` section in `.onetool/onetool.yaml`.

## Requirements

### Requirement: Initialise repo

`worktree.init()` SHALL add `tasks.json` and `tasks.json.lock` to `.gitignore`
and return `{ ok: true }`.

#### Scenario: First-time init
- **WHEN** `worktree.init()` is called from a git repo root
- **THEN** it SHALL append `tasks.json` and `tasks.json.lock` to `.gitignore` if absent
- **AND** return `{ ok: true }`

#### Scenario: Already initialised
- **WHEN** `.gitignore` already contains `tasks.json` and `tasks.json.lock`
- **THEN** `worktree.init()` SHALL NOT add duplicate entries

#### Scenario: Not a git repo
- **WHEN** `worktree.init()` is called from a directory with no `.git`
- **THEN** it SHALL raise `RuntimeError`

### Requirement: Create task worktree

`worktree.add()` SHALL create a git worktree for a task and return the launch command.

#### Scenario: Add with explicit branch
- **WHEN** `worktree.add(id="change-1", description="Fix login bug", branch="main")` is called
- **THEN** it SHALL run `git fetch origin main`
- **AND** run `git worktree add -b <branch_name> <workspace_dir> origin/main`
- **AND** run prepare hooks from config
- **AND** write `.gitworktree.json` into the task directory
- **AND** register the task in `tasks.json` with `state: active`
- **AND** return `{ task_id, dir, launch_cmd, ot_cmd }`

#### Scenario: Add with default branch
- **WHEN** `worktree.add(id="change-1", description="...")` is called with no `branch`
- **THEN** it SHALL use the current git branch as the base

#### Scenario: Duplicate task ID
- **WHEN** `worktree.add(id="change-1", ...)` is called and task `change-1` already exists
- **THEN** it SHALL raise `ValueError`

### Requirement: Branch name from config template

`worktree.add()` SHALL derive the git branch name from the `branch_name` config template.

#### Scenario: Default branch name equals task ID
- **WHEN** `branch_name` config is `"{task_id}"` (default)
- **THEN** the created git branch SHALL have the same name as the task ID

#### Scenario: Prefixed branch name
- **WHEN** `branch_name` config is `"wt/{task_id}"`
- **AND** `worktree.add(id="change-1", ...)` is called
- **THEN** the created git branch SHALL be named `wt/change-1`
- **AND** the task ID in `tasks.json` SHALL remain `change-1`

### Requirement: Query current context

`worktree.info()` SHALL return the current role and task context.

#### Scenario: Called from base worktree
- **WHEN** `worktree.info()` is called and `.gitworktree.json` is absent in cwd
- **THEN** it SHALL return `{ dir_type: "base", branch, base_dir }`

#### Scenario: Called from work worktree
- **WHEN** `worktree.info()` is called and `.gitworktree.json` is present in cwd
- **THEN** it SHALL return `{ dir_type: "work", task_id, branch, base, root_commit, base_dir }`

### Requirement: Checkout branch or PR

`worktree.checkout()` SHALL reset a work worktree to an existing branch or PR.

#### Scenario: Checkout branch
- **WHEN** `worktree.checkout(branch="feature/auth")` is called from a work worktree
- **THEN** it SHALL run `git fetch origin` and `git reset --hard origin/feature/auth`
- **AND** update `root_commit` in `.gitworktree.json` and `tasks.json`

#### Scenario: Checkout PR
- **WHEN** `worktree.checkout(pr=142)` is called from a work worktree
- **THEN** it SHALL resolve the PR head branch via `gh pr view`
- **AND** proceed as a branch checkout

#### Scenario: Neither branch nor PR
- **WHEN** `worktree.checkout()` is called with no arguments
- **THEN** it SHALL raise `ValueError`

### Requirement: Re-run prepare hooks

`worktree.prepare()` SHALL re-run the config prepare hooks in the current work worktree.

#### Scenario: Re-run hooks
- **WHEN** `worktree.prepare()` is called from a work worktree
- **THEN** it SHALL execute each hook with template variables expanded
- **AND** return `{ ok: true, hooks_run: N }`

### Requirement: Show commit history

`worktree.log()` SHALL show git log and diff stat for a task.

#### Scenario: Current worktree
- **WHEN** `worktree.log()` is called from a work worktree with `root_commit` set
- **THEN** it SHALL show log and diff stat from `root_commit` to `HEAD`

#### Scenario: By task index
- **WHEN** `worktree.log(id=1)` is called
- **THEN** it SHALL show log for the task with `num=1`

#### Scenario: By fuzzy task ID
- **WHEN** `worktree.log(id="bigfix")` is called and a task with id `big-fix` exists
- **THEN** it SHALL match after stripping dashes, underscores, and spaces

### Requirement: Show diff

`worktree.diff()` SHALL show the git diff for a task's changes since its root commit.

#### Scenario: Full diff for current worktree
- **WHEN** `worktree.diff()` is called from a work worktree
- **THEN** it SHALL return `git diff {root_commit}..HEAD`

#### Scenario: Stat summary
- **WHEN** `worktree.diff(stat=True)` is called
- **THEN** it SHALL return `git diff --stat {root_commit}..HEAD`

#### Scenario: By task id or index
- **WHEN** `worktree.diff(id=1)` or `worktree.diff(id="fix-login")` is called
- **THEN** it SHALL resolve the task directory and show its diff

### Requirement: Show git status

`worktree.status()` SHALL show `git status --short` for a task.

#### Scenario: Current worktree
- **WHEN** `worktree.status()` is called from a work worktree
- **THEN** it SHALL return the output of `git status --short`

#### Scenario: By task id or index
- **WHEN** `worktree.status(id=2)` is called
- **THEN** it SHALL run `git status --short` in that task's directory

### Requirement: List all tasks

`worktree.list()` SHALL show all registered tasks.

#### Scenario: Tasks present
- **WHEN** `worktree.list()` is called from the base worktree
- **THEN** it SHALL return all tasks with `num`, `id`, `description`, `state`, `base`, `root_commit`, `dir`

#### Scenario: No tasks
- **WHEN** `tasks.json` is absent or empty
- **THEN** `worktree.list()` SHALL return `{ tasks: [] }`

### Requirement: Commit and push

`worktree.commit()` SHALL squash, rebase, conflict-check, and push to the base branch.

#### Scenario: Clean commit
- **WHEN** `worktree.commit(message="Fix login")` is called from a work worktree
- **THEN** it SHALL soft-reset to `root_commit`, create a single squashed commit
- **AND** fetch origin and rebase onto `origin/{base}`
- **AND** push to `origin HEAD:{base}`
- **AND** set task state to `done`
- **AND** return `{ commit, pushed: true }`

#### Scenario: Conflict after rebase
- **WHEN** conflicting changes exist on the base branch
- **THEN** `worktree.commit()` SHALL abort and set task state back to `active`
- **AND** raise `RuntimeError` with a message to resolve conflicts

### Requirement: Remove task worktree

`worktree.remove()` SHALL remove a task worktree, delete its branch, and unregister it.

#### Scenario: Remove by index
- **WHEN** `worktree.remove(id=1)` is called from the base worktree
- **THEN** it SHALL run `git worktree remove --force`
- **AND** delete the local branch
- **AND** remove the task from `tasks.json`

#### Scenario: Remove active task
- **WHEN** a task with `state: active` is removed
- **THEN** it SHALL still be removed
- **AND** the return dict SHALL include a warning string for the removed active task

#### Scenario: Unknown task
- **WHEN** `worktree.remove(id="unknown")` is called and no matching task exists
- **THEN** it SHALL raise `KeyError`

### Requirement: Generate commit message context

`worktree.message()` SHALL collect git context and commit conventions for the
calling agent to compose a conventional commit message.

#### Scenario: Called from work worktree
- **WHEN** `worktree.message()` is called from a work worktree with changes since `root_commit`
- **THEN** it SHALL return a formatted string containing:
  - `git status --short` output (changed files)
  - `git diff --stat {root_commit}..HEAD` (diff summary)
  - `git log --oneline {root_commit}..HEAD` (commits in range)
  - Conventional commit format rules from config (types and scopes)

#### Scenario: No scopes configured
- **WHEN** `commit.scopes` is empty in config
- **THEN** `worktree.message()` SHALL omit the scopes line from the conventions block

#### Scenario: Called from base worktree
- **WHEN** `worktree.message()` is called and `.gitworktree.json` is absent
- **THEN** it SHALL raise `RuntimeError`

### Requirement: Update task state

`worktree.mark()` SHALL update a task's state in `tasks.json`.

The `id` parameter accepts a task index (1-based integer), exact task ID
(case-insensitive string), or fuzzy match (strips spaces, dashes, underscores),
consistent with `worktree.log()`, `worktree.diff()`, `worktree.status()`, and
`worktree.remove()`.

#### Scenario: Mark done
- **WHEN** `worktree.mark(id="change-1", state="done")` is called
- **THEN** it SHALL update the state in `tasks.json`
- **AND** return `{ task_id, state }`

#### Scenario: Mark by index
- **WHEN** `worktree.mark(id=1, state="done")` is called
- **THEN** it SHALL resolve the task with `num=1` and update its state

### Requirement: Tear down all tasks

`worktree.clean()` SHALL remove all task worktrees and manager state.

#### Scenario: Clean with no active tasks
- **WHEN** `worktree.clean()` is called and all tasks are in `done` state
- **THEN** it SHALL remove all worktrees, branches, `tasks.json`, and gitignore entries
- **AND** return `{ removed: [...], warnings: [] }`

#### Scenario: Clean with active tasks
- **WHEN** some tasks are in `active` or `committing` state
- **THEN** `worktree.clean()` SHALL still proceed
- **AND** include active task IDs in the `warnings` list

### Requirement: Config — workspace directory template

The `workspace_dir` config field SHALL be a template string supporting
`{task_id}`, `{base_dir}`, `{workspace_dir}`, and `{repo}` variables.

#### Scenario: Default template
- **WHEN** `workspace_dir` is `"../{repo}-work/{task_id}"` (default)
- **AND** `worktree.add(id="change-1", ...)` is called in repo `myapp`
- **THEN** the worktree SHALL be created at `../myapp-work/change-1`

### Requirement: Config — commit conventions

The `commit:` config block SHALL declare `types` and `scopes` for use by
`worktree.message()`.

#### Scenario: Default types
- **WHEN** no `commit:` block is present in config
- **THEN** `worktree.message()` SHALL use the default type list:
  `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, `chore`, `style`, `revert`

#### Scenario: Custom scopes
- **WHEN** `commit.scopes` is set to `["tool:worktree", "config"]`
- **THEN** `worktree.message()` SHALL include those scopes in the conventions block
