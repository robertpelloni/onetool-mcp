"""LLM extraction for the ctx pack."""
from __future__ import annotations

from typing import Any

from ot.logging import LogSpan

from .db import _get_connection, get_content

log = LogSpan


def ctx_transform(
    handle: str,
    intent: str,
    *,
    json_mode: bool = False,
    db: Any = None,
) -> dict[str, Any] | str:
    """Use ot_llm to synthesise a focused answer from stored content.

    Args:
        handle: Context store handle
        intent: What to extract / transform (e.g. "how to install")
        json_mode: If True, request JSON output from the model
        db: SQLite connection

    Returns:
        LLM-generated answer as a string, or ``{"error": ...}`` dict on failure.
    """
    with log(span="ctx.transform", handle=handle, json_mode=json_mode or None):
        if db is None:
            db = _get_connection()

        row = db.execute(
            "SELECT handle FROM results WHERE handle=?", (handle,)
        ).fetchone()
        if row is None:
            return {"error": f"Handle not found: {handle}"}

        content = get_content(db, handle)
        if content is None:
            return f"Error: Content not found for handle: {handle}"

        try:
            from ottools.ot_llm import transform as llm_transform
        except ImportError:
            return (
                "Error: ot_llm is not installed. "
                "Install the ot_llm pack and configure base_url and model to use ctx.transform."
            )

        try:
            result = llm_transform(data=content, prompt=intent, json_mode=json_mode)
            return result
        except Exception as e:
            err = str(e)
            if "not configured" in err.lower() or "api_key" in err.lower() or "base_url" in err.lower():
                return (
                    f"Error: ot_llm is not configured. "
                    f"Set ot_llm.base_url, ot_llm.model, and OPENAI_API_KEY in secrets.yaml. "
                    f"Details: {e}"
                )
            return f"Error: ot_llm transform failed: {e}"


__all__ = ["ctx_transform"]
