# tool-timer Specification

## Purpose
Provide named stopwatch timers that persist across multiple tool calls, useful for profiling workflows, benchmarking API responses, or capturing lap times during multi-step operations.
## Requirements
### Requirement: Timer Pack Registration

The timer pack SHALL be registered as `timer` with functions `start`, `elapsed`, `list`, and `clear` exposed in `__all__`.

#### Scenario: Pack discovery
- **WHEN** calling `ot.tools(pattern="timer")`
- **THEN** four tools are listed: `timer.start`, `timer.elapsed`, `timer.list`, `timer.clear`

---

### Requirement: Start Function

The `timer.start` function SHALL record a named time bookmark using `time.perf_counter()` for elapsed calculation and `datetime.now(UTC)` for display context.

#### Scenario: Basic start
- **WHEN** calling `timer.start(name="build")`
- **THEN** a confirmation string is returned containing the timer name and ISO 8601 timestamp

#### Scenario: Default name
- **WHEN** calling `timer.start()` without a name argument
- **THEN** the timer is stored under the name `"_default"`

#### Scenario: Overwrite existing
- **WHEN** calling `timer.start(name="x")` twice
- **THEN** the second call silently overwrites the first bookmark with no error

---

### Requirement: Elapsed Function

The `timer.elapsed` function SHALL compute elapsed time from a named start bookmark using `perf_counter()` delta.

#### Scenario: Basic elapsed
- **WHEN** `timer.start(name="t1")` has been called
- **AND** `timer.elapsed(name="t1")` is called
- **THEN** a dict is returned with keys `name`, `elapsed_seconds` (float, rounded to 6 decimal places), `elapsed_formatted` (human-readable string), and `started_at` (ISO 8601 string)

#### Scenario: Default name
- **WHEN** calling `timer.elapsed()` without a name argument
- **THEN** the function reads the `"_default"` start bookmark

#### Scenario: Unknown name
- **WHEN** calling `timer.elapsed(name="nonexistent")`
- **AND** no start bookmark exists for `"nonexistent"`
- **THEN** an error string is returned (not an exception) containing guidance to call `timer.start` first

#### Scenario: Store result
- **WHEN** calling `timer.elapsed(name="t1", store_as="phase_a")`
- **THEN** the elapsed result is saved under key `"phase_a"` in internal storage
- **AND** the result dict has `name` set to the timer name `"t1"`

#### Scenario: Lap pattern
- **WHEN** `timer.start(name="clock")` is called once
- **AND** `timer.elapsed(name="clock", store_as="lap1")` is called
- **AND** `timer.elapsed(name="clock", store_as="lap2")` is called later
- **THEN** `lap2.elapsed_seconds >= lap1.elapsed_seconds` (cumulative from start)

---

### Requirement: List Function

The `timer.list` function SHALL return all stored elapsed results and currently active timers.

#### Scenario: Stored results
- **WHEN** multiple elapsed results have been stored via `store_as`
- **THEN** `timer.list()` returns a dict with `stored` (dict of store_as key → result dict) and `active` (dict of timer name → `{started_at}`)

#### Scenario: Empty
- **WHEN** nothing has been stored and no timers are active
- **THEN** `timer.list()` returns `{"stored": {}, "active": {}}`

---

### Requirement: Clear Function

The `timer.clear` function SHALL remove all start bookmarks but preserve stored results.

#### Scenario: Clears starts
- **WHEN** `timer.start(name="x")` has been called
- **AND** `timer.clear()` is called
- **THEN** `timer.elapsed(name="x")` returns an error string (bookmark removed)
- **AND** a dict is returned: `{"status": "cleared", "timers_removed": N}`

#### Scenario: Preserves stored
- **WHEN** `timer.elapsed(name="x", store_as="saved")` has been called
- **AND** `timer.clear()` is called
- **THEN** `timer.list()` still contains the `"saved"` entry

#### Scenario: Nothing to clear
- **WHEN** no start bookmarks exist
- **AND** `timer.clear()` is called
- **THEN** `{"status": "cleared", "timers_removed": 0}` is returned

---

### Requirement: Error Handling Convention

The timer pack SHALL return error strings instead of raising exceptions, following OneTool tool conventions.

#### Scenario: Error format
- **WHEN** any function encounters an error condition
- **THEN** it returns a string starting with `"Error:"` describing the issue and suggesting corrective action

