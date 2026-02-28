#!/usr/bin/env python3
"""Sync generated documentation blocks from source-of-truth data.

Current generated blocks:
- PACK_SUMMARY: from prompts.yaml -> docs/llms.txt
- WB_HELP_SUMMARY: from src/otdev/tools/excalidraw.py -> docs/reference/tools/whiteboard.md
"""

from __future__ import annotations

from dataclasses import dataclass
import inspect
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
PROMPTS = ROOT / "src/ot/config/global_templates/prompts.yaml"

DOC_MAP = {
    "ot": "ot.md",
    "ot_forge": "forge.md",
    "ot_llm": "llm.md",
    "ot_secrets": "secrets.md",
    "ot_timer": "timer.md",
    "brave": "brave.md",
    "convert": "convert.md",
    "excel": "excel.md",
    "file": "file.md",
    "ground": "ground.md",
    "mem": "mem.md",
    "aws": "aws.md",
    "chrome_util": "chrome-util.md",
    "context7": "context7.md",
    "db": "db.md",
    "diagram": "diagram.md",
    "package": "package.md",
    "play_util": "play-util.md",
    "ripgrep": "ripgrep.md",
    "whiteboard": "whiteboard.md",
    "webfetch": "webfetch.md",
    "worktree": "worktree.md",
}

EXTRA_MAP = {
    "ot": "core",
    "ot_forge": "core",
    "ot_llm": "core",
    "ot_secrets": "core",
    "ot_timer": "core",
    "brave": "[util]",
    "convert": "[util]",
    "excel": "[util]",
    "file": "[util]",
    "ground": "[util]",
    "mem": "[util]",
    "aws": "[dev]",
    "chrome_util": "[dev]",
    "context7": "[dev]",
    "db": "[dev]",
    "diagram": "[dev]",
    "package": "[dev]",
    "play_util": "[dev]",
    "ripgrep": "[dev]",
    "whiteboard": "[dev]",
    "webfetch": "[dev]",
    "worktree": "[dev]",
}


@dataclass(frozen=True)
class BlockTarget:
    path: Path
    include_docs: bool = False


def _replace_block(path: Path, marker_name: str, block: str) -> None:
    begin = f"<!-- BEGIN GENERATED:{marker_name} -->"
    end = f"<!-- END GENERATED:{marker_name} -->"

    text = path.read_text(encoding="utf-8")
    marker = re.compile(
        rf"{re.escape(begin)}[\s\S]*?{re.escape(end)}",
        re.MULTILINE,
    )
    repl = f"{begin}\n{block}\n{end}"

    if marker.search(text):
        text = marker.sub(repl, text, count=1)
    else:
        text = text.rstrip() + "\n\n" + repl + "\n"

    path.write_text(text, encoding="utf-8")


def _load_pack_descriptions() -> list[tuple[str, str]]:
    data = yaml.safe_load(PROMPTS.read_text(encoding="utf-8")) or {}
    packs = ((data.get("prompts") or {}).get("packs") or {})
    if not isinstance(packs, dict):
        raise ValueError("prompts.packs must be a mapping")

    out: list[tuple[str, str]] = []
    for name, desc in packs.items():
        if not isinstance(name, str):
            continue
        text = str(desc).strip().replace("\n", " ")
        text = re.sub(r"\s+", " ", text)
        out.append((name, text))
    return out


def _render_pack_table(packs: list[tuple[str, str]], *, include_docs: bool) -> str:
    lines = [
        "| Pack | Extra | Description" + (" | Docs |" if include_docs else " |"),
        "|---|---|---" + ("|---|" if include_docs else "|"),
    ]
    for name, desc in packs:
        extra = EXTRA_MAP.get(name, "-")
        if include_docs and name in DOC_MAP:
            doc = f"[link](./{DOC_MAP[name]})"
            lines.append(f"| `{name}` | `{extra}` | {desc} | {doc} |")
        elif include_docs:
            lines.append(f"| `{name}` | `{extra}` | {desc} | - |")
        else:
            lines.append(f"| `{name}` | `{extra}` | {desc} |")
    return "\n".join(lines)


def _render_wb_help_table() -> str:
    src = ROOT / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from otdev.tools import excalidraw as whiteboard

    lines = [
        "| Function | Summary |",
        "|---|---|",
    ]
    for name in whiteboard.__all__:
        fn = getattr(whiteboard, name)
        sig = inspect.signature(fn, eval_str=True)
        doc = (inspect.getdoc(fn) or "").splitlines()[0].strip()
        lines.append(f"| `whiteboard.{name}{sig}` | {doc} |")
    return "\n".join(lines)


def sync_all() -> None:
    packs = _load_pack_descriptions()

    # PACK_SUMMARY block (agent-facing summary in llms.txt only)
    _replace_block(
        ROOT / "docs/llms.txt",
        "PACK_SUMMARY",
        _render_pack_table(packs, include_docs=False),
    )

    # WB_HELP_SUMMARY block
    _replace_block(
        ROOT / "docs/reference/tools/whiteboard.md",
        "WB_HELP_SUMMARY",
        _render_wb_help_table(),
    )


def main() -> int:
    sync_all()
    print("synced generated docs blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
