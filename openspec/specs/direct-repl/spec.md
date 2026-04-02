# direct-repl Specification

## Purpose

Defines the `onetool direct repl` command for interactive tool execution with persistent in-process state. The REPL runs in-process so module-level pack state persists across commands within a session.

---

## Requirements

### Requirement: direct repl command

The system SHALL provide `onetool direct repl` for interactive tool execution with persistent in-process state.

Flags:
- `--config`/`-c` — path to `onetool.yaml`; required
- `--secrets`/`-s` — path to secrets file; optional

The REPL runs in-process (not via the execution server) so module-level pack state (e.g. whiteboard board state) persists across lines within a session.

#### Scenario: Start REPL

- **WHEN** `onetool direct repl -c onetool.yaml` is run in a TTY
- **THEN** a prompt (`>>> `) SHALL appear and accept tool commands
- **AND** tool loading SHALL complete before the first prompt is shown

#### Scenario: Execute a command

- **WHEN** a command is entered at the `>>> ` prompt
- **THEN** a spinner (`running...`) SHALL be shown during execution
- **AND** the result SHALL be printed below the prompt when done
- **AND** the next prompt SHALL appear

#### Scenario: Readline history

- **WHEN** the REPL is active
- **THEN** up/down arrow keys SHALL navigate command history
- **AND** history SHALL persist to `~/.onetool/repl_history` across sessions

#### Scenario: Tab completion on pack names

- **WHEN** the user types a partial pack name (e.g. `wb.`) and presses Tab
- **THEN** the available tool names for that pack SHALL be shown as completions

#### Scenario: Special commands in completions

- **WHEN** the user presses Tab at an empty prompt
- **THEN** `:quit`, `exit()`, `quit()`, and `:help` SHALL appear in completions

#### Scenario: Exit with Ctrl+D or :quit

- **WHEN** the user presses Ctrl+D or enters `:quit`
- **THEN** the REPL SHALL exit cleanly with code 0

#### Scenario: Exit with exit() or quit()

- **WHEN** the user enters `exit()` or `quit()`
- **THEN** the REPL SHALL exit cleanly with code 0

#### Scenario: :help prints tool list

- **WHEN** the user enters `:help`
- **THEN** available packs and tools SHALL be printed
- **AND** the REPL SHALL continue to the next prompt (not exit)

#### Scenario: Execution error does not exit REPL

- **WHEN** a command raises an execution error
- **THEN** the error message SHALL be printed
- **AND** the REPL SHALL continue to the next prompt (not exit)

#### Scenario: KeyboardInterrupt cancels command

- **WHEN** the user presses Ctrl+C during execution
- **THEN** the current execution SHALL be cancelled
- **AND** the REPL SHALL return to the prompt without exiting

#### Scenario: Multi-line input — open brackets

- **WHEN** a line has unclosed parentheses, brackets, or braces
- **THEN** a continuation prompt (`... `) SHALL appear instead of submitting
- **AND** the accumulated lines SHALL be submitted as one command when the expression is complete

#### Scenario: Multi-line input — block statements

- **WHEN** a line ends with `:` (e.g. `for x in items:`)
- **THEN** a continuation prompt SHALL appear for the block body
- **AND** an empty line SHALL terminate the block and submit for execution

#### Scenario: Syntax error clears buffer

- **WHEN** accumulated lines contain a syntax error (detected via compile)
- **THEN** the error SHALL be printed
- **AND** the buffer SHALL be cleared for fresh input

#### Scenario: Non-TTY stdin raises error

- **WHEN** `onetool direct repl` is run with stdin not a TTY (e.g. piped input)
- **THEN** the command SHALL exit with: `"REPL requires an interactive terminal. Use 'onetool direct run -' for non-interactive input."`
