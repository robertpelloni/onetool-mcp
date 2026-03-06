"""Constants, types, and shared path utilities for ot.meta."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

# Info level type for discovery functions
InfoLevel = Literal["list", "min", "default", "full"]
ServerInfoLevel = Literal["min", "default", "full", "resources", "prompts"]

# Pack name for dot notation: ot.tools(), ot.packs(), etc.
PACK_NAME = "ot"

# Documentation URL mapping for packs with misaligned slugs
# Short-name aliases for packs with verbose names.
# Injected into the execution namespace so e.g. `wf.fetch()` == `webfetch.fetch()`.
# Packs already short (db, mem, aws, ot) are not listed here.
PACK_SHORT_NAMES: dict[str, str] = {
    "brave": "br",
    "context7": "c7",
    "webfetch": "wf",
    "tavily": "tav",
    "ground": "g",
    "diagram": "diag",
    "package": "pkg",
    "ripgrep": "rg",
    "chrome_util": "chrome",
    "play_util": "play",
    "worktree": "wt",
    "convert": "cv",
    "excel": "xls",
    "file": "f",
    "ot_forge": "forge",
    "ot_llm": "llm",
    "ot_secrets": "sec",
    "ot_timer": "tmr",
    "whiteboard": "wb",
    "ot_context": "ctx",
    "ot_image": "img",
}

DOC_SLUGS: dict[str, str] = {
    "brave": "brave-search",
    "db": "database",
    "ground": "grounding-search",
    "webfetch": "web-fetch",
}

DOC_BASE_URL = "https://onetool.beycom.online/reference/tools/"


def resolve_ot_path(path: str) -> Path:
    """Resolve a path relative to the OT_DIR (config_path.parent).

    Resolution priority:
    1. If absolute or ~ path: use as-is
    2. Resolve relative to config._config_dir

    Args:
        path: Path string (relative, absolute, or with ~)

    Returns:
        Resolved absolute Path
    """
    p = Path(path).expanduser()
    if p.is_absolute():
        return p.resolve()

    from ot.config.loader import get_config

    config_dir = get_config()._config_dir
    return (config_dir / p).resolve()
