# Agent Navigation

Quick reference files for AI agents working on OneTool.

---

## Start Here

**Load this first:** [hints.md](hints.md)

This single-page reference provides:
- Common commands
- Project structure overview
- Critical coding rules
- Quick problem-solving guide
- Pointers to detailed docs

---

## When Hints Isn't Enough

### Need More Detail?

Use `mem.search(query="your topic")` to search all dev docs semantically.

**Examples:**
```python
mem.search(query="create tool pack")
mem.search(query="testing markers")
mem.search(query="git workflow")
mem.search(query="OneTool architecture")
```

### Need Full Project Structure?

See [project-map.md](project-map.md) for:
- Complete source code organization
- All tool packs and their functions
- Configuration file reference
- Test directory structure

### Need Detailed Guides?

Browse the dev docs:
- **OneTool-specific:** `dev/project/arch/`, `dev/project/guides/`
- **Generic practices:** `dev/practices/`
- **Full index:** `dev/index.md`

---

## File Guide

| File | Lines | Load When | Purpose |
|------|-------|-----------|---------|
| [hints.md](hints.md) | ~150 | Always | Single-page quick reference |
| [project-map.md](project-map.md) | ~100 | Need structure | Detailed project layout |
| [index.md](index.md) | ~50 | Getting oriented | This file - how to use agents/ |

---

## Why This Folder Exists

**Problem:** Agents need quick context without loading entire docs.

**Solution:** Navigation layer that provides:
1. **Minimal context** - Hints file covers 80% of tasks
2. **Smart pointers** - Links to detailed docs when needed
3. **Search integration** - Use mem.search() for deep dives

**Design principle:** Load `hints.md` first, use mem.search() for details, browse `dev/` for deep understanding.

---

**Related:**
- Main dev docs index: `dev/index.md`
- CLAUDE.md: Instructions for Claude Code
- README.md: Project overview for users
