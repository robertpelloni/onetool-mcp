# Proposal: remove-bundled-defaults

## Summary

Remove hidden bundled defaults and require explicit `onetool init` for first-run configuration. On first run without config, prompt user interactively to initialize. Add config version migration detection.

## Motivation

Currently, OneTool silently falls back to bundled defaults in `src/ot/config/defaults/` when no user config exists. This creates transparency and security concerns:

1. **Hidden behavior**: Users don't see what security rules govern their code execution
2. **Non-auditable**: Security allowlists are buried in the package, not in visible config files
3. **Silent changes**: Package updates can silently change security behavior
4. **No upgrade path**: No mechanism to detect stale configs or offer migrations

The quickstart already instructs users to run `onetool init`. Making this required (with interactive prompt) is minimal friction while providing:

- Full transparency - users see exactly what config governs their tool
- Auditability - security rules in `~/.onetool/config/security.yaml`
- Graceful upgrades - version check enables future migration support

## Scope

### In Scope

- Remove fallback to bundled defaults in config loader
- Add first-run detection with interactive init prompt
- Add config version migration detection (warn on outdated, fail on future)
- Keep bundled defaults as source for `onetool init` to copy from
- Update spec to reflect new behavior

### Out of Scope

- Automatic config migrations (warn only, manual reset)
- Project-level init (already has `inherit: none` pattern)

## Approach

### First-Run Flow

```
$ onetool
OneTool is not initialized.
Initialize now? [Y/n]: y
Creating ~/.onetool/
  ✓ config/
  ✓ logs/
  ✓ stats/
  ✓ tools/
  ✓ config/onetool.yaml
  ✓ config/security.yaml
  ✓ config/snippets.yaml
  ✓ config/servers.yaml
  ✓ config/secrets.yaml
[Server starts normally]
```

If user declines:
```
Initialize now? [Y/n]: n
Run 'onetool init' when ready.
[Exit with code 1]
```

Non-interactive (CI/piped input):
```
$ echo "test" | onetool
OneTool not initialized. Run: onetool init
[Exit with code 1]
```

### Config Version Migration

Configs already have a `version: 1` field. This change adds detection:

```
$ onetool
Config version 1 is outdated (current: 2).
Run 'onetool init reset' to update config templates.
[Server starts with warning]
```

Future incompatible config:
```
$ onetool
Config version 3 requires OneTool >= X.Y.Z (you have A.B.C).
[Exit with code 1]
```

### Config Resolution (New)

```
1. ONETOOL_CONFIG env var (explicit path)
2. cwd/.onetool/config/onetool.yaml (project)
3. ~/.onetool/config/onetool.yaml (global) ← REQUIRED
4. [REMOVED: bundled defaults fallback]
```

### Bundled Defaults Role (New)

Bundled defaults in `src/ot/config/defaults/` become:
- Source files for `onetool init` to copy
- Include resolution fallback (security.yaml, snippets.yaml, etc.)
- NOT loaded directly as config

### Test Strategy

Tests already use `tests/.onetool/config/onetool.yaml` with `inherit: none`. This isolates them from the change. No test changes required.

## Impact

| Component | Change |
|-----------|--------|
| `src/ot/config/loader.py` | Remove bundled fallback, add version migration warning |
| `src/onetool/cli.py` | Add first-run detection and interactive init prompt |
| `openspec/specs/serve-configuration/spec.md` | Update scenarios, add first-run and migration requirements |

## Alternatives Considered

1. **Keep bundled defaults, warn on first run**: Less friction but still hides config
2. **Auto-init silently**: Cleaner but user doesn't know what happened
3. **Fail hard without init**: Worse UX than interactive prompt
4. **Automatic migrations**: Too complex for v1, warn-only is safer

## Decision

Proceed with interactive first-run init and version migration warnings. Balances transparency with usability while enabling future migration support.
