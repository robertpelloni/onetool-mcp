"""Centralized configuration for OneTool V2 (global-only).

This module provides a single source of truth for all configuration settings
via YAML configuration for tool discovery and settings.

Key changes from V1:
- Global-only configuration (no project configs or inheritance)
- Root-level env: section for subprocess environment variables
- No expand_subprocess_env() - use expand_secrets() instead
- Defaults embedded in Pydantic models (no template files)
- Depth-limited includes (no circular detection)

Usage:
    from ot.config import get_config, load_config

    config = get_config()
    print(config.log_level)
    print(config.tools_dir)

    # For tools to access their configuration:
    from ot.config import get_tool_config

    class Config(BaseModel):
        timeout: float = 60.0

    config = get_tool_config("brave", Config)

    # For secrets expansion:
    from ot.config import expand_secrets

    api_url = expand_secrets("https://api.example.com?key=${API_KEY}")
"""

from ot.config.loader import (
    ConfigNotFoundError,
    get_config,
    get_tool_config,
    is_log_verbose,
    load_config,
)
from ot.config.loader import (
    reset as reset_config,
)
from ot.config.models import (
    McpServerConfig,
    OneToolConfig,
    SecurityConfig,
    SnippetDef,
    SnippetParam,
)
from ot.config.secrets import (
    expand_secrets,
    get_secret,
    get_secrets,
    load_secrets,
)
from ot.config.secrets import (
    reset as reset_secrets,
)


def reset() -> None:
    """Clear all config and secrets caches for reload.

    This is a convenience function that resets both config and secrets caches.
    Use this as part of the reload flow (called from ot.reload()).
    """
    reset_config()
    reset_secrets()


__all__ = [
    "ConfigNotFoundError",
    "McpServerConfig",
    "OneToolConfig",
    "SecurityConfig",
    "SnippetDef",
    "SnippetParam",
    "expand_secrets",
    "get_config",
    "get_secret",
    "get_secrets",
    "get_tool_config",
    "is_log_verbose",
    "load_config",
    "load_secrets",
    "reset",
]
