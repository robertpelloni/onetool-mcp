"""Message publishing via ot.notify()."""

from __future__ import annotations

import asyncio
import fnmatch
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import aiofiles
import yaml

from ot.config import get_config
from ot.logging import LogSpan
from ot.meta._constants import resolve_ot_path

if TYPE_CHECKING:
    from pathlib import Path

log = LogSpan

_background_tasks: set[asyncio.Task[None]] = set()


def _resolve_path(path: str) -> Path:
    """Resolve a topic file path relative to OT_DIR (.onetool/).

    Uses SDK resolve_ot_path() for consistent path resolution.

    Path resolution for topic files follows OT_DIR conventions:
        - Relative paths: resolved relative to OT_DIR (.onetool/)
        - Absolute paths: used as-is
        - ~ paths: expanded to home directory
        - Prefixed paths (CWD/, GLOBAL/, OT_DIR/): resolved to respective dirs

    Note: ${VAR} patterns are NOT expanded here. Use ~/path instead of
    ${HOME}/path. Secrets (e.g., ${API_KEY}) are expanded during config
    loading, not path resolution.

    Args:
        path: Path string from topic config.

    Returns:
        Resolved absolute Path.
    """
    return resolve_ot_path(path)


def _match_topic_to_file(topic: str) -> Path | None:
    """Match topic to file path using first matching pattern.

    Paths in topic config are resolved relative to OT_DIR (.onetool/).
    See _resolve_path() for full path resolution behaviour.

    Args:
        topic: Topic string to match (e.g., "status:scan").

    Returns:
        Resolved file path for matching topic, or None if no match.
    """
    cfg = get_config()
    msg_config = cfg.tools.msg

    for topic_config in msg_config.topics:
        topic_pattern = topic_config.pattern
        file_path = topic_config.file

        if fnmatch.fnmatch(topic, topic_pattern):
            return _resolve_path(file_path)

    return None


async def _write_to_file(file_path: Path, doc: dict[str, Any]) -> None:
    """Write message document to file asynchronously."""
    with log(span="ot.write", file=str(file_path), topic=doc.get("topic")) as s:
        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(file_path, "a") as f:
                await f.write("---\n")
                await f.write(
                    yaml.safe_dump(doc, default_flow_style=False, allow_unicode=True)
                )
            s.add("written", True)
        except Exception as e:
            s.add("error", str(e))


def notify(*, topic: str, message: str) -> str:
    """Publish a message to the matching topic file.

    Routes the message to a YAML file based on topic pattern matching
    configured in onetool.yaml. The write happens asynchronously.

    Args:
        topic: Topic string for routing (e.g., "status:scan", "notes")
        message: Message content (text, can be multiline)

    Returns:
        "OK: <topic> -> <file>" if routed, "OK: no matching topic" if no match

    Example:
        ot.notify(topic="notes", message="Remember to review PR #123")
    """
    with log(span="ot.notify", topic=topic) as s:
        file_path = _match_topic_to_file(topic)

        if file_path is None:
            s.add("matched", False)
            return "SKIP: no matching topic"

        doc = {
            "ts": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "topic": topic,
            "message": message,
        }

        try:
            loop = asyncio.get_running_loop()
            task = loop.create_task(_write_to_file(file_path, doc))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
        except RuntimeError:
            asyncio.run(_write_to_file(file_path, doc))

        s.add("matched", True)
        s.add("file", str(file_path))
        return f"OK: {topic} -> {file_path}"
