"""Secrets loading for OneTool V2 (global-only).

Loads secrets from secrets.yaml (gitignored) separate from committed configuration.
Secrets are passed to workers via JSON-RPC, not exposed as environment variables.

The secrets file path is resolved in order:
1. Explicit path passed to load_secrets()
2. OT_SECRETS_FILE environment variable
3. Global location: ~/.onetool/config/secrets.yaml

Example secrets.yaml:

    BRAVE_API_KEY: "your-brave-api-key"
    OPENAI_API_KEY: "sk-..."
    DATABASE_URL: "postgresql://..."
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml
from loguru import logger

# Single global secrets cache
_secrets: dict[str, str] | None = None


def load_secrets(secrets_path: Path | str | None = None) -> dict[str, str]:
    """Load secrets from YAML file.

    Args:
        secrets_path: Path to secrets file. If None or doesn't exist,
            returns empty dict (no secrets).

    Returns:
        Dictionary of secret name -> value

    Raises:
        ValueError: If YAML is invalid
    """
    if secrets_path is None:
        logger.debug("No secrets path provided")
        return {}

    secrets_path = Path(secrets_path)

    if not secrets_path.exists():
        logger.debug(f"Secrets file not found: {secrets_path}")
        return {}

    logger.debug(f"Loading secrets from {secrets_path}")

    try:
        with secrets_path.open() as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in secrets file {secrets_path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Error reading secrets file {secrets_path}: {e}") from e

    if raw_data is None:
        return {}

    if not isinstance(raw_data, dict):
        raise ValueError(
            f"Secrets file {secrets_path} must be a YAML mapping, not {type(raw_data).__name__}"
        )

    # Values are literal - no env var expansion
    secrets: dict[str, str] = {}
    for key, value in raw_data.items():
        if not isinstance(key, str):
            logger.warning(f"Ignoring non-string secret key: {key}")
            continue

        if value is None:
            continue

        # Store as literal string - no ${VAR} expansion
        secrets[key] = str(value)

    logger.info(f"Loaded {len(secrets)} secrets")
    return secrets


def _load_from_default_location() -> dict[str, str]:
    """Load secrets from global location only.

    Location: ~/.onetool/config/secrets.yaml

    Returns:
        Dictionary of secret name -> value (empty if no secrets found)
    """
    from ot.paths import CONFIG_SUBDIR, get_global_dir

    secrets_path = get_global_dir() / CONFIG_SUBDIR / "secrets.yaml"

    if secrets_path.exists():
        try:
            return load_secrets(secrets_path)
        except ValueError as e:
            logger.debug(f"Error loading secrets from {secrets_path}: {e}")

    return {}


def get_secrets(
    secrets_path: Path | str | None = None, reload: bool = False
) -> dict[str, str]:
    """Get or load the cached secrets.

    Resolution order (first match wins):
    1. Explicit secrets_path argument
    2. OT_SECRETS_FILE environment variable
    3. Global location (~/.onetool/config/secrets.yaml)

    Args:
        secrets_path: Path to secrets file (only used on first load or reload).
        reload: Force reload secrets from disk.

    Returns:
        Dictionary of secret name -> value
    """
    global _secrets

    if _secrets is None or reload:
        # Resolution chain: explicit > env var > global default
        if secrets_path is None:
            # Check OT_SECRETS_FILE env var first (highest priority after explicit path)
            env_path = os.getenv("OT_SECRETS_FILE")
            if env_path:
                secrets_path = env_path

        # Try global default location if still no path
        if secrets_path is None:
            loaded = _load_from_default_location()
            if loaded:
                _secrets = loaded
                return _secrets

        _secrets = load_secrets(secrets_path)

    return _secrets


def get_secret(name: str) -> str | None:
    """Get a single secret value by name.

    Args:
        name: Secret name (e.g., "BRAVE_API_KEY")

    Returns:
        Secret value, or None if not found
    """
    return get_secrets().get(name)


def expand_secrets(value: str) -> str:
    """Expand ${VAR} patterns using secrets.yaml ONLY.

    Use this for configuration values that MUST be in secrets.yaml.
    This enforces that sensitive values are stored in the gitignored secrets file,
    not in environment variables that might leak into logs or process lists.

    Supports ${VAR_NAME} and ${VAR_NAME:-default} syntax.

    When to use:
        - Config file values (URLs, API keys, database connections)
        - Anywhere secrets should be explicit and fail loudly if missing
        - Subprocess environment variables (after root env + server env merge)

    Args:
        value: String potentially containing ${VAR} patterns.

    Returns:
        String with variables expanded from secrets.

    Raises:
        ValueError: If variable not found in secrets and no default provided.
    """
    pattern = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")
    missing_vars: list[str] = []

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default_value = match.group(2)
        # Read from secrets only - no os.environ
        secret_value = get_secret(var_name)
        if secret_value is not None:
            return secret_value
        if default_value is not None:
            return default_value
        missing_vars.append(var_name)
        return match.group(0)

    result = pattern.sub(replace, value)

    if missing_vars:
        raise ValueError(
            f"Missing variables in secrets.yaml: {', '.join(missing_vars)}. "
            f"Add them to ~/.onetool/config/secrets.yaml or use ${{VAR:-default}} syntax."
        )

    return result


def reset() -> None:
    """Clear secrets cache for reload.

    Use this as part of the config reload flow to force secrets to be
    reloaded from disk on next access.
    """
    global _secrets
    _secrets = None
