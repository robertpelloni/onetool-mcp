# serve-code-validation Specification

## Purpose

Defines Python code validation for the run() tool. Includes syntax checking via AST parsing, security pattern detection for dangerous calls, and optional ruff linting for style warnings.
## Requirements
### Requirement: Syntax Validation

The system SHALL validate Python syntax before execution using AST parsing.

#### Scenario: Valid syntax
- **GIVEN** syntactically valid Python code
- **WHEN** validate_python_code() is called
- **THEN** it SHALL return ValidationResult with valid=True

#### Scenario: Invalid syntax
- **GIVEN** Python code with syntax errors
- **WHEN** validate_python_code() is called
- **THEN** it SHALL return ValidationResult with valid=False and error containing line number

#### Scenario: Syntax error message
- **GIVEN** code with syntax error on line 5
- **WHEN** validation fails
- **THEN** the error message SHALL include "Syntax error at line 5: {error message}"

### Requirement: Security Pattern Detection

The system SHALL detect and block dangerous code patterns.

#### Scenario: Exec call blocked
- **GIVEN** code containing `exec("code")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error "Dangerous builtin 'exec' is not allowed (matches 'exec')"

#### Scenario: Eval call blocked
- **GIVEN** code containing `eval("expression")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error "Dangerous builtin 'eval' is not allowed (matches 'eval')"

#### Scenario: Dynamic import blocked
- **GIVEN** code containing `__import__("module")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error "Dangerous builtin '__import__' is not allowed (matches '__import__')"

#### Scenario: Compile blocked
- **GIVEN** code containing `compile("code", "", "exec")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error "Dangerous builtin 'compile' is not allowed (matches 'compile')"

#### Scenario: Open blocked
- **GIVEN** code containing `open("file.txt")`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error "Dangerous builtin 'open' is not allowed"
- **RATIONALE** Use file.* tools instead (sandboxed)

#### Scenario: Network imports blocked
- **GIVEN** code containing `import socket` or `import requests`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error

#### Scenario: Filesystem imports blocked
- **GIVEN** code containing `import os` or `import pathlib`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error

#### Scenario: Security check disabled
- **GIVEN** code containing dangerous patterns
- **WHEN** validate_python_code() is called with check_security=False
- **THEN** it SHALL not check for dangerous patterns

### Requirement: AST-Based Function Parsing

The system SHALL parse function calls using AST instead of regex.

#### Scenario: Simple function call
- **GIVEN** code `search(query="test")`
- **WHEN** parse_function_call() is called
- **THEN** it SHALL return ("search", {"query": "test"})

#### Scenario: Nested function call
- **GIVEN** code `to_yaml(search(query="test"))`
- **WHEN** parse_function_call() is called
- **THEN** it SHALL detect this as Python code requiring full execution

#### Scenario: Multiple arguments
- **GIVEN** code `search(query="test", count=5, fresh=True)`
- **WHEN** parse_function_call() is called
- **THEN** it SHALL extract all keyword arguments with correct types

#### Scenario: Invalid function call
- **GIVEN** invalid syntax like `search(query=`
- **WHEN** parse_function_call() is called
- **THEN** it SHALL raise ValueError with clear error message

### Requirement: Optional Ruff Linting

The system SHALL optionally run ruff for style warnings.

#### Scenario: Ruff available
- **GIVEN** ruff is installed and lint_warnings=True
- **WHEN** lint_code() is called
- **THEN** it SHALL return list of warning strings

#### Scenario: Ruff not installed
- **GIVEN** ruff is not installed
- **WHEN** lint_code() is called
- **THEN** it SHALL return empty list (fail silently)

#### Scenario: Ruff timeout
- **GIVEN** ruff takes longer than 5 seconds
- **WHEN** lint_code() is called
- **THEN** it SHALL return empty list (fail silently)

#### Scenario: Warnings non-blocking
- **GIVEN** ruff returns warnings
- **WHEN** validation runs
- **THEN** warnings SHALL be included in ValidationResult but valid SHALL remain True

### Requirement: Validation Result Structure

The system SHALL return structured validation results.

#### Scenario: Result structure
- **GIVEN** any code input
- **WHEN** validate_python_code() is called
- **THEN** it SHALL return ValidationResult with: valid (bool), errors (list[str]), warnings (list[str])

#### Scenario: Multiple errors
- **GIVEN** code with multiple issues
- **WHEN** validate_python_code() is called
- **THEN** all errors SHALL be collected in the errors list

#### Scenario: Mixed errors and warnings
- **GIVEN** code with security issues and style warnings
- **WHEN** validate_python_code() is called
- **THEN** security issues SHALL be in errors, style issues in warnings

### Requirement: Comprehensive Security Blocking

The system SHALL block dangerous builtins, imports, and function calls.

#### Scenario: Dangerous builtins blocked
- **GIVEN** code containing `exec()`, `eval()`, `compile()`, `open()`, `input()`, `breakpoint()`, `globals()`, `locals()`, `__import__()`, or `memoryview()`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error
- **NOTE** `getattr`, `setattr`, `delattr`, `hasattr`, `dir`, `vars`, `type` are allowed for object introspection

#### Scenario: Dangerous imports blocked
- **GIVEN** code containing imports of: os, sys, socket, urllib, http, shutil, glob, tempfile, pickle, marshal, shelve, ctypes, multiprocessing, threading, ssl, asyncio, aiohttp, requests, httpx
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=False with error

#### Scenario: Safe imports allowed
- **GIVEN** code containing `import json` or `import re` or `import math`
- **WHEN** validate_python_code() is called with check_security=True
- **THEN** it SHALL return valid=True (safe modules are not blocked)

### Requirement: Configurable Security Patterns

The system SHALL support configurable security patterns via onetool.yaml.

#### Scenario: Custom blocked patterns
- **GIVEN** configuration with:

  ```yaml
  security:
    blocked:
      - my_dangerous.*
  ```

- **WHEN** code containing `my_dangerous.func()` is validated
- **THEN** it SHALL return valid=False with error
- **AND** built-in default blocked patterns SHALL still apply

#### Scenario: Security disabled
- **GIVEN** configuration with `security.enabled: false`
- **WHEN** code containing dangerous patterns is validated
- **THEN** security checks SHALL be skipped
- **AND** only syntax validation SHALL occur

#### Scenario: Default patterns used
- **GIVEN** no security configuration in onetool.yaml
- **WHEN** code is validated
- **THEN** built-in default patterns SHALL be used

#### Scenario: Additive configuration
- **GIVEN** configuration with only custom patterns
- **WHEN** patterns are loaded
- **THEN** custom patterns SHALL be merged with defaults
- **AND** defaults SHALL NOT be replaced
- **RATIONALE** Prevents accidental removal of critical security patterns

#### Scenario: Allow list exemption
- **GIVEN** configuration with:

  ```yaml
  security:
    allow:
      - os
  ```

- **WHEN** code containing `import os` is validated
- **THEN** it SHALL pass without error (exempted from defaults)
- **RATIONALE** Allows users to selectively enable blocked patterns when needed

### Requirement: Wildcard Pattern Matching

The system SHALL support fnmatch wildcards in security patterns.

#### Scenario: Asterisk wildcard
- **GIVEN** blocked pattern `subprocess.*`
- **WHEN** code containing `subprocess.run()` or `subprocess.Popen()` is validated
- **THEN** both SHALL be blocked

#### Scenario: Question mark wildcard
- **GIVEN** blocked pattern `os.exec?`
- **WHEN** code containing `os.execl()` is validated
- **THEN** it SHALL be blocked
- **AND** `os.execve()` SHALL NOT be blocked (more than one char)

#### Scenario: Exact match fallback
- **GIVEN** blocked pattern `os.system` (no wildcards)
- **WHEN** code containing `os.system()` is validated
- **THEN** exact match SHALL be used (fast path)

#### Scenario: Error message includes pattern
- **GIVEN** code blocked by wildcard pattern `subprocess.*`
- **WHEN** error is reported
- **THEN** message SHALL include both the function name and the matched pattern
- **EXAMPLE** "subprocess.check_output is not allowed (matches 'subprocess.*')"

### Requirement: Allowlist-Based Security Model

The system SHALL use an allowlist-based security model where everything is blocked by default.

#### Scenario: Allowlist philosophy
- **GIVEN** the security model
- **WHEN** code is validated
- **THEN** only explicitly allowed builtins, imports, and calls SHALL pass
- **AND** everything else SHALL be blocked by default
- **RATIONALE** Industry best practice - "block everything, explicitly allow what's safe"

#### Scenario: Builtins allowlist
- **GIVEN** security.yaml with `builtins.allow: [str, int, len, ...]`
- **WHEN** code uses allowed builtins
- **THEN** validation SHALL pass
- **AND** unlisted builtins SHALL be blocked

#### Scenario: Imports allowlist
- **GIVEN** security.yaml with `imports.allow: [json, re, math, ...]`
- **WHEN** code imports allowed modules
- **THEN** validation SHALL pass
- **AND** unlisted imports SHALL be blocked

#### Scenario: Imports warn list
- **GIVEN** security.yaml with `imports.warn: [yaml]`
- **WHEN** code imports warned modules
- **THEN** validation SHALL pass with warning
- **AND** warning SHALL indicate potential unsafe operations

#### Scenario: Calls blocklist
- **GIVEN** security.yaml with `calls.block: [pickle.*, yaml.load]`
- **WHEN** code uses blocked calls
- **THEN** validation SHALL fail with error
- **EVEN IF the module part is in allowed imports

#### Scenario: Tool namespaces auto-allowed
- **GIVEN** registered tool packs (ot, brave, file, web, etc.)
- **WHEN** code calls tool functions (e.g., `brave.search()`, `file.read()`)
- **THEN** validation SHALL pass without explicit allowlist entry
- **RATIONALE** Tool namespaces are the point of OneTool

#### Scenario: User-defined functions allowed
- **GIVEN** code defines a function `def foo(): pass`
- **WHEN** that function is called later in the code
- **THEN** validation SHALL pass
- **RATIONALE** User-defined functions are not dangerous builtins

#### Scenario: Method calls on variables allowed
- **GIVEN** code with `results = []; results.append(x)`
- **WHEN** the code is validated
- **THEN** validation SHALL pass
- **RATIONALE** Cannot statically determine if variable is dangerous

#### Scenario: External config file
- **GIVEN** security.yaml in bundled defaults
- **WHEN** config is loaded
- **THEN** security rules SHALL be visible and auditable
- **AND** users CAN customize via project/global security.yaml

### Requirement: Security Introspection Tool

The system SHALL provide ot.security() for agents to query security rules.

#### Scenario: Security summary
- **GIVEN** no arguments to ot.security()
- **WHEN** called
- **THEN** it SHALL return summary of all security categories
- **INCLUDING** builtins count, imports count, blocked calls, tool namespaces

#### Scenario: Check specific pattern
- **GIVEN** `ot.security(check="os")`
- **WHEN** called
- **THEN** it SHALL return status (allowed/blocked/warned), category, and reason
- **EXAMPLE** `{"pattern": "os", "status": "blocked", "category": "builtins", "reason": "Not in any allowlist"}`

#### Scenario: Check tool namespace
- **GIVEN** `ot.security(check="brave.search")`
- **WHEN** called
- **THEN** it SHALL return allowed status with reason "Tool namespace auto-allowed"

#### Scenario: Check allowed module call
- **GIVEN** `ot.security(check="json.loads")`
- **WHEN** called
- **THEN** it SHALL return allowed status with reason "Module 'json' is in allowed imports"

### Requirement: Magic Variables (Dunders)

The system SHALL support configurable magic variables.

#### Scenario: Allowed dunders
- **GIVEN** security.yaml with `dunders.allow: [__format__, __sanitize__]`
- **WHEN** code assigns to these variables
- **THEN** validation SHALL pass

#### Scenario: Blocked dunders
- **GIVEN** code assigns to `__class__` or `__dict__`
- **WHEN** validation runs
- **THEN** validation SHALL fail with error
- **RATIONALE** Prevents namespace manipulation attacks

### Requirement: Compact Array Format

The system SHALL support grouped arrays in security.yaml for readability.

#### Scenario: Nested arrays flattened
- **GIVEN** security.yaml with:
  ```yaml
  builtins:
    allow:
      - [str, int, float]
      - [list, dict, set]
      - print
  ```
- **WHEN** config is loaded
- **THEN** nested arrays SHALL be flattened to single list
- **AND** single items SHALL be preserved

