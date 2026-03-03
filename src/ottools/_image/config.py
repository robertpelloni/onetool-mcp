"""Configuration for the image pack."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ot.config import get_secret, get_tool_config


class Config(BaseModel):
    """Image pack configuration — discovered by registry."""

    vision_model: str = Field(
        default="",
        description="Vision model to use for ask() and summary() (e.g. openai/gpt-4o-mini)",
    )
    max_edge: int = Field(
        default=1568,
        description="Maximum longest edge in pixels for in-memory model-upload resize",
    )
    session_cache_size: int = Field(
        default=10,
        description="Maximum number of images to keep in the in-memory session LRU cache",
    )
    api_key: str = Field(
        default="",
        description="API key for the vision model (falls back to OPENAI_API_KEY secret)",
    )
    base_url: str = Field(
        default="",
        description="OpenAI-compatible API base URL (falls back to tools.ot_llm.base_url)",
    )


class _LlmConfig(BaseModel):
    """Minimal ot_llm config for base_url fallback."""

    base_url: str = ""


def get_image_config() -> Config:
    """Load image pack configuration with ot_llm fallbacks.

    Reads ``tools.image`` from onetool.yaml. Falls back to OPENAI_API_KEY secret
    for ``api_key`` and ``tools.ot_llm.base_url`` for ``base_url`` when not
    explicitly set in ``tools.image``.

    Returns:
        Fully resolved Config for the image pack.
    """
    config = get_tool_config("ot_image", Config)

    if not config.api_key:
        secret = get_secret("OPENAI_API_KEY")
        if secret:
            config = config.model_copy(update={"api_key": secret})

    if not config.base_url:
        try:
            llm = get_tool_config("ot_llm", _LlmConfig)
            if llm.base_url:
                config = config.model_copy(update={"base_url": llm.base_url})
        except Exception:
            pass

    return config
