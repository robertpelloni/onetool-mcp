# Telemetry

OneTool fires a single anonymous GET request to a [Scarf](https://scarf.sh) pixel on each server start. This gives the project basic usage visibility — how many machines are running OneTool, on which platforms, and which versions — without tracking individual users or their work.

## What is collected

| Field | Value |
|-------|-------|
| `e`   | Event type: `install`, `upgrade`, or `start` |
| `v`   | OneTool version (e.g. `1.2.3`) |
| `os`  | Operating system (e.g. `Darwin`, `Linux`, `Windows`) |
| `py`  | Python major.minor version (e.g. `3.11`) |
| `v_from` | Previous version — only on `upgrade` events |
| `v_to`   | New version — only on `upgrade` events |

## What is NOT collected

- User identity, account names, or any personal data
- Tool call contents, prompts, or AI responses
- File paths, config values, or secrets
- IP address (Scarf does not store raw IPs)
- Any persistent identifier

## How opt-out works

**Via config file** (`onetool.yaml`):

```yaml
telemetry:
  enabled: false
```

**Via environment variable:**

```bash
export DO_NOT_TRACK=1
# or
export SCARF_NO_ANALYTICS=1
```

When either env var is set to a non-empty, non-zero value, no request is made.

## Marker file

OneTool writes `~/.onetool_telemetry` containing the current version string to distinguish `install`, `upgrade`, and `start` events. This file is local to your machine and never transmitted except as the `v_from` field on upgrades.
