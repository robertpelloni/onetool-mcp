# Direct Usage Guide

The `onetool direct` subcommand group lets you run tools directly from the shell without an AI model in the loop. Useful for scripts, automation, and interactive exploration.

---

## In-process execution (no server)

The simplest mode: load config, execute one tool call, print the result, exit. Packs are initialised fresh on every invocation — suitable for one-off calls.

```bash
onetool direct run -c .onetool/onetool.yaml "ot.debug()"
onetool direct run -c .onetool/onetool.yaml "ot.version()"
onetool direct run -c .onetool/onetool.yaml "brave.search(query='latest AI news')"
```

**Format options** (`--format` / `-f`):

```bash
# Default: human-readable JSON
onetool direct run -c onetool.yaml "ot.packs()"

# Compact JSON (for parsing in scripts)
onetool direct run -c onetool.yaml "ot.packs()" --format json

# Raw string (no serialisation)
onetool direct run -c onetool.yaml "ot.version()" --format raw

# YAML
onetool direct run -c onetool.yaml "ot.packs()" --format yml
```

**Multi-line scripts** from a `.py` file or stdin:

```bash
onetool direct run -c onetool.yaml report.py
echo "ot.version()" | onetool direct run -c onetool.yaml -
```

---

## Execution host (persistent state)

**Why use host mode?**

| | In-process | Execution host |
|---|---|---|
| **Performance** | Packs re-initialised on every call | Loaded once at startup — negligible per-call overhead |
| **State persistence** | Starts fresh each call | Module-level state survives (whiteboard canvas, DB connections, caches) |
| **Config** | `--config` required every call | Host owns the config; callers omit `--config` |
| **Best for** | One-off calls | AI agents, scripts making many sequential calls |

**When NOT to use host mode:** one-off calls (in-process is simpler), or environments where a persistent background process is undesirable (CI, containers).

Add `direct.host: enable` to `onetool.yaml` to auto-start the host on first use — no manual `direct start` needed.

---

Starting an execution host keeps tool state alive between calls — tool packs stay loaded and module-level state (e.g. whiteboard sessions) persists across multiple `direct run` invocations.

```bash
# Start the execution host (output goes to ~/.onetool/direct-server-8765.log)
onetool direct start -c .onetool/onetool.yaml

# Confirm it's running
onetool direct status

# Run tools — no --config needed (routes to host automatically)
onetool direct run "wb.draw(dsl='box A')"
onetool direct run "wb.draw(dsl='box B; A -> B')"   # board state persists!

# Check the logs if something looks wrong
onetool direct logs

# Restart after config changes
onetool direct restart

# Stop
onetool direct stop
```

**Wait until ready** (useful in scripts):

```bash
onetool direct start -c .onetool/onetool.yaml --wait
onetool direct run "ot.version()"  # safe to call immediately after
```

**Multiple hosts** on different ports:

```bash
onetool direct start -c project-a.yaml            # port 8765
onetool direct start -c project-b.yaml --port 9000

onetool direct status --port 8765
onetool direct status --port 9000

onetool direct stop --port 9000
```

---

## Interactive REPL

The REPL runs in-process — great for exploration and multi-step workflows.

```bash
onetool direct repl -c .onetool/onetool.yaml
```

```
OneTool REPL — type :quit or press Ctrl+D to exit
>>> brave.search(query='AI news 2026')
{"results": [...]}
>>> for r in _:
...     print(r['title'])
...
AI Safety Update — April 2026
...
>>> :quit
```

**Key bindings:**

| Action | Key |
|--------|-----|
| Submit line | Enter |
| Tab complete | Tab |
| Previous command | ↑ |
| Next command | ↓ |
| Cancel current input | Ctrl+C |
| Exit | Ctrl+D or `:quit` |

**Multi-line input:** open brackets or block statements (`for x in y:`) show a `... ` continuation prompt. An empty line submits a block.

**Help:** type `:help` to list available packs and tools.

---

## Discovering tools

```bash
# List all tools (one per line, pipe-friendly)
onetool direct list
onetool direct list brave
onetool direct list | fzf              # interactive picker

# Full signatures
onetool direct list --info full

# Search by intent
onetool direct search "web search"
onetool direct search "convert pdf"

# Detailed help for a specific tool
onetool direct help brave.search
onetool direct help "web search"       # fuzzy match
```

---

## Agent scripting

Use `--format json` + exit codes for reliable automation:

```bash
# Run a tool and capture the JSON output
RESULT=$(onetool direct run "brave.search(query='AI')" --format json 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "$RESULT" | jq '.results[0].title'
fi

# Feed tool output to an AI pipeline (enable sanitization)
onetool direct run -c onetool.yaml "webfetch.fetch(url='...')" --sanitize --format raw | ai-pipeline
```

**For AI agents calling onetool direct:**

1. Start the execution host once: `onetool direct start -c onetool.yaml --wait`
2. Run tools without `--config` (host handles state): `onetool direct run "pack.tool(...)"`
3. Use `--format json` for machine-readable results
4. Exit code 0 = success, 1 = tool error, 2 = config error
