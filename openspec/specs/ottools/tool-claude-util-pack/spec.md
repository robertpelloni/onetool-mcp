# Spec: claude_util Pack

## Purpose

Provides Claude Code session utilities, including retrieving the active conversation UUID and measuring token/cost usage over a span of work via `ccusage`.

Pack name: `claude_util`; short alias: `cld`.

---

## Requirements

### Requirement: Pack registration
The `claude_util` pack SHALL be registered with short alias `cld` in `PACK_SHORT_NAMES` and discoverable via `ot.packs()` and `ot.tools(pattern="claude_util")`.

#### Scenario: Pack is discoverable
- **WHEN** a user calls `ot.packs(pattern="claude_util")`
- **THEN** the response includes an entry with `name="claude_util"` and `short="cld"`

#### Scenario: Tools are callable via short alias
- **WHEN** a user calls `cld.session_id()`
- **THEN** it executes identically to `claude_util.session_id()`

---

### Requirement: session_id returns current Claude Code conversation UUID
`claude_util.session_id()` SHALL return the UUID of the active Claude Code conversation by inspecting the most recently modified `*.jsonl` file in `~/.claude/projects/<project-slug>/`.

#### Scenario: Active session found
- **WHEN** `session_id()` is called during an active Claude Code session
- **THEN** it returns the UUID string (e.g. `"cac49288-0e20-4190-9008-25551a9b3569"`)

#### Scenario: No session directory found
- **WHEN** `session_id()` is called and no matching project directory exists under `~/.claude/projects/`
- **THEN** it returns an error string beginning with `"Error:"`

#### Scenario: No JSONL files found
- **WHEN** the project directory exists but contains no `*.jsonl` files
- **THEN** it returns an error string beginning with `"Error:"`

---

### Requirement: start_usage captures a token/cost baseline
`claude_util.start_usage(*, name="_default")` SHALL call `ccusage session --id <uuid> --json`, store the result as a baseline snapshot in ctx under source `"cld_baseline_<name>"`, and return a confirmation dict with the session UUID and snapshot timestamp.

Multiple independent baselines may coexist by passing different `name` values.

#### Scenario: Successful baseline capture
- **WHEN** `start_usage()` is called with ccusage available on PATH
- **THEN** it returns a dict with keys `session_id`, `snapshot_at`, `total_tokens`, `total_cost_usd`

#### Scenario: ccusage not on PATH
- **WHEN** `start_usage()` is called and `ccusage` is not found on PATH
- **THEN** it returns an error string beginning with `"Error: ccusage not found"`

#### Scenario: Baseline stored in ctx with namespaced source
- **WHEN** `start_usage(name="A-1")` succeeds
- **THEN** a baseline is stored in ctx with source `"cld_baseline_A-1"` and retrievable by `elapsed_usage(name="A-1")`

#### Scenario: Default name uses "_default" namespace
- **WHEN** `start_usage()` is called without a `name` argument
- **THEN** the baseline is stored under source `"cld_baseline__default"`

---

### Requirement: elapsed_usage returns delta against baseline
`claude_util.elapsed_usage(*, name="_default")` SHALL retrieve the stored baseline matching `name`, call `ccusage session --id <uuid> --json` again, compute the delta, delete the baseline from ctx, and return a structured report.

#### Scenario: Successful delta report
- **WHEN** `elapsed_usage()` is called after a successful `start_usage()`
- **THEN** it returns a dict containing `session_id`, `delta_tokens`, `delta_cost_usd`, `delta_output_tokens`, `delta_cache_read_tokens`, `delta_cache_create_tokens`, `elapsed_seconds`

#### Scenario: No baseline found
- **WHEN** `elapsed_usage(name="A-1")` is called without a prior `start_usage(name="A-1")`
- **THEN** it returns an error string beginning with `"Error: no baseline found for name='A-1'. Call start_usage(name='A-1') first."`

#### Scenario: Baseline is cleaned up
- **WHEN** `elapsed_usage()` completes successfully
- **THEN** the ctx entry for `"cld_baseline__default"` is deleted

#### Scenario: Named recorders are independent
- **WHEN** `start_usage(name="X")` and `start_usage(name="Y")` are both called
- **THEN** `elapsed_usage(name="X")` returns only the delta for recorder `"X"` and does not affect recorder `"Y"`

---

### Requirement: ccusage dependency is checked at call time
If `ccusage` is not available on PATH, `start_usage()` and `elapsed_usage()` SHALL return a clear error string rather than raising an exception.

#### Scenario: Missing ccusage
- **WHEN** any tool requiring ccusage is called and `ccusage` is not on PATH
- **THEN** the tool returns `"Error: ccusage not found. Install with: npm install -g ccusage"`
