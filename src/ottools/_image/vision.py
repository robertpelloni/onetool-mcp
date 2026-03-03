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

if TYPE_CHECKING:
    from .config import Config

# Cached client — recreated only when api_key or base_url changes
_client: OpenAI | None = None
_client_key: tuple[str, str] = ("", "")


def _get_client(config: Config) -> OpenAI:
    global _client, _client_key
    key = (config.api_key, config.base_url)
    if _client is None or _client_key != key:
        _client = OpenAI(api_key=config.api_key, base_url=config.base_url or None)
        _client_key = key
    return _client


_SUMMARY_PROMPT = """\
Analyse this image and return ONLY valid JSON with exactly these keys:
{
  "text": "<all visible text in the image, or empty string if none>",
  "mode": "<one of: dark, light, unknown>",
  "type": "<content type: screenshot, diagram, photo, chart, code, ui, other>",
  "colours": ["<list of dominant colour names>"],
  "shapes": ["<list of notable shapes or UI elements>"],
  "description": "<one sentence describing what the image shows>"
}"""


def call_vision(model_bytes: bytes, prompt: str, config: Config) -> str:
    """Send image bytes and a text prompt to the configured vision model.

    Args:
        model_bytes: PNG bytes ready for upload (should already be resized).
        prompt: Text prompt to accompany the image.
        config: Image pack config (must have ``vision_model`` and ``api_key``).

    Returns:
        Model response text, or an error string starting with ``"Error:"`` if
        the model is not configured or the API call fails.
    """
    if not config.vision_model:
        return (
            "Error: ot_image.vision_model not configured — "
            "set tools.ot_image.vision_model in onetool.yaml"
        )
    if not config.api_key:
        return (
            "Error: image API key not configured — "
            "set OPENAI_API_KEY in secrets.yaml"
        )

    b64 = base64.b64encode(model_bytes).decode()

    try:
        client = _get_client(config)
        response = client.chat.completions.create(
            model=config.vision_model,
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
            "Answer each of the following questions about the image. "
            f"Number your answers to match:\n{numbered}"
        )

    result = call_vision(model_bytes, prompt, config)
    if result.startswith("Error:"):
        return [result]

    if len(questions) == 1:
        return [result.strip()]

    # Parse numbered answers from response
    answers: list[str] = []
    current_lines: list[str] = []

    for line in result.strip().split("\n"):
        m = re.match(r"^\s*(\d+)\.\s*", line)
        if m and 1 <= int(m.group(1)) <= len(questions):
            if current_lines:
                answers.append("\n".join(current_lines).strip())
            current_lines = [re.sub(r"^\s*\d+\.\s*", "", line)]
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
        Summary dict with keys ``text``, ``mode``, ``type``, ``colours``,
        ``shapes``, ``description``. Returns an error string if the model is
        not configured or the response cannot be parsed.
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
    for key in ("colours", "shapes"):
        if key not in data:
            data[key] = []
    for key in ("text", "mode", "type", "description"):
        if key not in data:
            data[key] = ""

    # Normalise mode to allowed values
    if data.get("mode") not in ("dark", "light", "unknown"):
        data["mode"] = "unknown"

    # Ensure text is never null
    if not data.get("text"):
        data["text"] = ""

    return {k: data[k] for k in ("text", "mode", "type", "colours", "shapes", "description")}
