# Tasks: remove-bundled-defaults

## Implementation Tasks

- [x] **Task 1: Add first-run detection to CLI**
  - File: `src/onetool/cli.py`
  - Add `_check_first_run()` function that checks if `~/.onetool/config/onetool.yaml` exists
  - Check if stdin is a TTY for interactive vs non-interactive mode
  - Call from `serve()` callback before server starts
  - If missing and TTY: prompt "OneTool is not initialized. Initialize now? [Y/n]"
  - If missing and not TTY: print error and exit(1)
  - On "y": call `ensure_global_dir()` and continue
  - On "n": print "Run 'onetool init' when ready." and exit(1)

- [x] **Task 2: Remove bundled fallback from config loader**
  - File: `src/ot/config/loader.py`
  - Modify `load_config()`: when `resolved_path` is None, raise `ConfigNotFoundError`
  - Modify `_load_base_config()`: for `inherit: global`, if global config missing, return empty dict
  - Remove `inherit: bundled` mode - only `global` and `none` supported
  - Add custom exception class `ConfigNotFoundError` for clean handling in CLI
  - Update `_deep_merge()` to skip None values from override dict

- [x] **Task 3: Consolidate defaults/ into global_templates/**
  - Removed `src/ot/config/defaults/` directory entirely
  - All templates now in `src/ot/config/global_templates/`
  - Updated `pyproject.toml` ruff/mypy exclude paths
  - Updated `src/ot/prompts.py` to use `get_global_templates_dir()`
  - Updated `src/ot_tools/scaffold.py` to use `get_global_templates_dir()`

- [x] **Task 4: Make security configuration explicit**
  - Created full `src/ot/config/global_templates/security.yaml` with complete allowlist
  - Created `tests/.onetool/config/security.yaml` with test-specific settings
  - Updated `tests/.onetool/config/onetool.yaml` to include `config/security.yaml`
  - Security is no longer inherited - users must have explicit security.yaml

- [x] **Task 5: Update include resolution to two-tier only**
  - File: `src/ot/config/loader.py`
  - `_resolve_include_path()` uses two-tier fallback: ot_dir -> global
  - No bundled fallback for includes (removed)
  - Include paths are relative to OT_DIR (.onetool/), not config_dir

- [x] **Task 6: Add config version migration detection**
  - File: `src/ot/config/loader.py`
  - In `_validate_version()`, compare `version` against `CURRENT_CONFIG_VERSION`
  - If version < current: log warning with migration hint
  - If version > current: raise error with minimum version message

- [x] **Task 7: Update tests**
  - Updated `test_dynamic_attribute_builtins_blocked` -> `test_dynamic_attribute_builtins_allowed`
  - Updated `test_include_two_tier_fallback` to use correct directory structure
  - All 1243 tests pass

- [x] **Task 8: Update comments and documentation**
  - Updated `src/ot/paths.py` comment about bundled defaults
  - Updated `src/ot/config/global_templates/onetool.yaml` comment

## Validation

- [x] All existing tests pass (1243 passed, 1 skipped)
- [x] Linting passes (`just lint`)
- [x] Full check passes (`just check`)
- [ ] Manual test: fresh environment without `~/.onetool/` triggers init prompt
- [ ] Manual test: declining init exits cleanly with helpful message
- [ ] Manual test: accepting init creates config and starts server
- [ ] Manual test: non-interactive mode (piped input) fails gracefully
- [ ] Manual test: outdated config version shows migration warning
- [ ] Manual test: future config version fails with clear error

## Dependencies

None - self-contained change.

## Notes

- Tests isolated via `tests/.onetool/config/onetool.yaml` with `inherit: none`
- `inherit: bundled` mode removed - only `global` and `none` supported
- Config version is currently 1; migration mechanism ready for future version bumps
- No automatic migrations implemented - just detection and user guidance
- `_deep_merge()` skips None values (handles YAML keys with no values)
- Security configuration is now explicit - must be included via `include: [config/security.yaml]`
