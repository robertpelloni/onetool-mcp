"""Vision model calls for the image pack.

Uses the OpenAI-compatible messages API with base64 image content blocks.
Supports single questions, batched numbered questions, and structured summary
extraction.
"""

from __future__ import annotations

import base64
import json
import re
from typing import TYPE_CHECKING

from openai import OpenAI

from .config import get_image_api_key

if TYPE_CHECKING:
    from .config import Config

# Cached client — recreated only when api_key or base_url changes
_client: OpenAI | None = None
_client_key: tuple[str, str] = ("", "")


def _get_client(config: Config) -> OpenAI:
    global _client, _client_key
    api_key = get_image_api_key() or ""
    key = (api_key, config.base_url)
    if _client is None or _client_key != key:
        _client = OpenAI(api_key=api_key, base_url=config.base_url or None)
        _client_key = key
    return _client


_SUMMARY_PROMPT = """\
You are an OCR and image analysis engine. Return ONLY valid JSON with exactly these keys:
{
  "type": "<one of: screenshot, diagram, photo, chart, code, ui, other>",
  "mode": "<one of: dark, light, unknown>",
  "colours": ["<2-5 dominant colour names>"],
  "description": "<one sentence describing the overall purpose or subject>",
  "content": "<full structured markdown OCR — see rules below>"
}

Rules for the 'content' field:
- Extract ALL visible text verbatim. Do not paraphrase or summarise.
- Use ## for top-level visual sections, ### for subsections, matching visual hierarchy.
- Wrap code in triple-backtick blocks with language hint.
- Render tables as markdown tables.
- Render lists as markdown lists, preserving numbering or bullets.
- Mark buttons and badges as **[Label]**, input fields as _[placeholder]_.
- Include a ## Interactive Controls section at the end: a markdown table with columns Label | Type | Location.
- Skip purely decorative elements (icons without labels, background imagery)."""


def call_vision(model_bytes: bytes, prompt: str, config: Config) -> str:
    """Send image bytes and a text prompt to the configured vision model.

    Args:
        model_bytes: PNG bytes ready for upload (should already be resized).
        prompt: Text prompt to accompany the image.
        config: Image pack config (must have ``model``).

    Returns:
        Model response text, or an error string starting with ``"Error:"`` if
        the model is not configured or the API call fails.
    """
    if not config.model:
        return (
            "Error: ot_image.model not configured — "
            "set tools.ot_image.model in onetool.yaml"
        )
    if not get_image_api_key():
        return (
            "Error: image API key not configured — "
            "set OPENAI_API_KEY in secrets.yaml"
        )

    b64 = base64.b64encode(model_bytes).decode()

    try:
        client = _get_client(config)
        response = client.chat.completions.create(
            model=config.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            temperature=0.1,
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        error_msg = str(e)
        if "api_key" in error_msg.lower() or "sk-" in error_msg:
            error_msg = "Authentication error — check OPENAI_API_KEY in secrets.yaml"
        return f"Error: {error_msg}"


def ask_questions(model_bytes: bytes, questions: list[str], config: Config) -> list[str]:
    """Send one or more questions to the vision model in a single call.

    Formats multiple questions as a numbered list and parses the numbered
    response back into individual answers.

    Args:
        model_bytes: PNG bytes ready for upload.
        questions: One or more question strings.
        config: Image pack config.

    Returns:
        List of answer strings in the same order as ``questions``.
        Returns a single-element list with an error string if the call fails.
    """
    if len(questions) == 1:
        prompt = questions[0]
    else:
        numbered = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions))
        prompt = (
            "Answer each of the following questions about the image.\n"
            "Start each answer with only its question number followed by a period and space "
            f"(e.g. '1. your answer'). Do not use headings or bold formatting.\n"
            f"Questions:\n{numbered}"
        )

    result = call_vision(model_bytes, prompt, config)
    if result.startswith("Error:"):
        return [result]

    if len(questions) == 1:
        return [result.strip()]

    # Parse numbered answers from response
    answers: list[str] = []
    current_lines: list[str] = []

    _num_pat = re.compile(r"^\s*(?:[#*]+\s*)?(\d+)[.)]\s*(?:[#*]*\s*)?")
    for line in result.strip().split("\n"):
        m = _num_pat.match(line)
        if m and 1 <= int(m.group(1)) <= len(questions):
            if current_lines:
                answers.append("\n".join(current_lines).strip())
            current_lines = [_num_pat.sub("", line, count=1)]
        else:
            current_lines.append(line)

    if current_lines:
        answers.append("\n".join(current_lines).strip())

    # Pad if parsing missed answers
    while len(answers) < len(questions):
        answers.append("")

    return answers[: len(questions)]


def extract_summary(model_bytes: bytes, config: Config) -> dict[str, object] | str:
    """Extract a structured summary of the image via the vision model.

    Calls the vision model with a structured extraction prompt and parses the
    JSON response. The result is suitable for caching in ``meta.json``.

    Args:
        model_bytes: PNG bytes ready for upload.
        config: Image pack config.

    Returns:
        Summary dict with keys ``type``, ``mode``, ``colours``, ``description``,
        ``content`` (full structured markdown OCR of all visible text).
        Returns an error string if the model is not configured or the response
        cannot be parsed.
    """
    result = call_vision(model_bytes, _SUMMARY_PROMPT, config)
    if result.startswith("Error:"):
        return result

    text = result.strip()
    # Strip markdown code fences if present
    text = re.sub(r"^```[a-z]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text.strip())

    data: dict[str, object] = {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
            except json.JSONDecodeError:
                return "Error: Could not parse vision model response as JSON"
        else:
            return "Error: Could not parse vision model response as JSON"

    # Fill missing required keys with safe defaults
    if "colours" not in data:
        data["colours"] = []
    for key in ("mode", "type", "description", "content"):
        if key not in data:
            data[key] = ""

    # Normalise mode to allowed values
    if data.get("mode") not in ("dark", "light", "unknown"):
        data["mode"] = "unknown"

    return {k: data[k] for k in ("type", "mode", "colours", "description", "content")}
