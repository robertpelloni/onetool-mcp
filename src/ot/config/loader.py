"""YAML configuration loading for OneTool V2 (global-only).

Loads onetool.yaml with tool discovery patterns and settings from global config only.

Example onetool.yaml:

    version: 1

    include:
      - prompts.yaml    # prompts: section
      - snippets.yaml   # snippets: section

    env:
      HOME: /home/user
      LANG: en_US.UTF-8

    tools_dir:
      - tools/*.py

    transform:
      model: anthropic/claude-3-5-haiku
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any, TypeVar

import yaml
from loguru import logger
from pydantic import BaseModel

from ot.config.models import OneToolConfig
from ot.config.secrets import expand_secrets

# Current config schema version
CURRENT_CONFIG_VERSION = 1

# Maximum include depth to prevent infinite loops
MAX_INCLUDE_DEPTH = 5

T = TypeVar("T", bound=BaseModel)


class ConfigNotFoundError(Exception):
    """Raised when configuration file is not found and no fallback is available.

    This error indicates that OneTool has not been initialized. Users should run
    `onetool init` to create the global configuration directory.
    """


def _resolve_config_path(config_path: Path | str | None) -> Path | None:
    """Resolve config path from explicit path, env var, or global location only.

    Resolution order:
    1. Explicit config_path if provided
    2. ONETOOL_CONFIG env var
    3. ~/.onetool/config/onetool.yaml (global only)
    4. None (config not found)

    Args:
        config_path: Explicit path to config file (may be None).

    Returns:
        Resolved Path or None if no config file found.
    """
    if config_path is not None:
        return Path(config_path)

    env_config = os.getenv("ONETOOL_CONFIG")
    if env_config:
        return Path(env_config)

    # Global-only: no project config resolution
    from ot.paths import CONFIG_SUBDIR, get_global_dir

    global_config = (get_global_dir() / CONFIG_SUBDIR / "onetool.yaml")
    if global_config.exists():
        return global_config

    return None


def _load_yaml_file(config_path: Path) -> dict[str, Any]:
    """Load and parse YAML file with error handling.

    Args:
        config_path: Path to YAML file.

    Returns:
        Parsed YAML data as dict.

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If YAML is invalid or file can't be read.
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    try:
        with config_path.open() as f:
            raw_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in {config_path}: {e}") from e
    except OSError as e:
        raise ValueError(f"Error reading {config_path}: {e}") from e

    return raw_data if raw_data is not None else {}


def _expand_secrets_recursive(data: Any) -> Any:
    """Recursively expand ${VAR} from secrets.yaml in config data.

    Args:
        data: Config data (dict, list, or scalar).

    Returns:
        Data with secrets expanded.
    """
    if isinstance(data, dict):
        return {k: _expand_secrets_recursive(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_expand_secrets_recursive(v) for v in data]
    elif isinstance(data, str):
        return expand_secrets(data)
    return data


def _flatten_arrays_recursive(data: Any) -> Any:
    """Recursively flatten nested arrays in config data (compact array format).

    Converts [[a, b], c, [d, e]] to [a, b, c, d, e].
    This allows compact array notation in YAML config files.

    Args:
        data: Config data (dict, list, or scalar).

    Returns:
        Data with nested arrays flattened.
    """
    if isinstance(data, dict):
        return {k: _flatten_arrays_recursive(v) for k, v in data.items()}
    elif isinstance(data, list):
        flattened = []
        for item in data:
            if isinstance(item, list):
                # Recursively flatten nested list and extend
                flattened.extend(_flatten_arrays_recursive(item))
            else:
                # Non-list items are appended as-is (but recursively processed)
                flattened.append(_flatten_arrays_recursive(item))
        return flattened
    return data


def _validate_version(data: dict[str, Any]) -> None:
    """Validate config version and set default if missing.

    Args:
        data: Config data dict (modified in place).

    Raises:
        ValueError: If version is unsupported.
    """
    config_version = data.get("version")
    if config_version is None:
        data["version"] = 1
        config_version = 1

    if config_version > CURRENT_CONFIG_VERSION:
        raise ValueError(
            f"Config version {config_version} is not supported. "
            f"Maximum supported version is {CURRENT_CONFIG_VERSION}. "
            f"Please upgrade OneTool: uv tool upgrade onetool"
        )


def _resolve_include_path(include_path_str: str, ot_dir: Path) -> Path | None:
    """Resolve an include path relative to OT_DIR (.onetool/).

    Supports:
    - Absolute paths (used as-is)
    - ~ expansion (expands to home directory)
    - Relative paths (resolved relative to OT_DIR)

    Args:
        include_path_str: Path string from include directive
        ot_dir: The .onetool/ directory (OT_DIR)

    Returns:
        Resolved Path if found, None otherwise
    """
    # Expand ~ first
    include_path = Path(include_path_str).expanduser()

    # Absolute paths are used as-is
    if include_path.is_absolute():
        if include_path.exists():
            logger.debug(f"Include resolved (absolute): {include_path}")
            return include_path
        return None

    # Relative paths: resolve from OT_DIR
    resolved = (ot_dir / include_path).resolve()
    if resolved.exists():
        logger.debug(f"Include resolved (ot_dir): {resolved}")
        return resolved

    logger.warning(f"Include file not found: {include_path_str}")
    return None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merge two dictionaries, with override values taking precedence.

    - Nested dicts are recursively merged
    - Non-dict values (lists, scalars) are replaced entirely
    - Keys in override not in base are added
    - None values in override are skipped (won't override existing values)

    Args:
        base: Base dictionary (inputs not mutated)
        override: Override dictionary (inputs not mutated, values take precedence)

    Returns:
        New merged dictionary
    """
    result = base.copy()

    for key, override_value in override.items():
        # Skip None values - they shouldn't override existing values
        # This handles YAML files with keys but no values (e.g., "security:" with comments)
        if override_value is None:
            continue

        if key in result:
            base_value = result[key]
            # Only deep merge if both are dicts
            if isinstance(base_value, dict) and isinstance(override_value, dict):
                result[key] = _deep_merge(base_value, override_value)
            else:
                # Replace entirely (lists, scalars, or type mismatch)
                result[key] = override_value
        else:
            # New key from override
            result[key] = override_value

    return result


def _process_includes(
    data: dict[str, Any], ot_dir: Path, depth: int = 0
) -> dict[str, Any]:
    """Load and merge files from 'include:' list into config data.

    Files are merged left-to-right (later files override earlier).
    Inline content in the main file overrides everything.

    Include resolution is single-tier (no fallback), relative to OT_DIR (.onetool/).

    Args:
        data: Config data dict containing optional 'include' key
        ot_dir: The .onetool/ directory (OT_DIR) for resolving relative paths
        depth: Current recursion depth (for limiting nested includes)

    Returns:
        Merged config data with includes processed

    Raises:
        ValueError: If include depth exceeds MAX_INCLUDE_DEPTH
    """
    if depth > MAX_INCLUDE_DEPTH:
        raise ValueError(
            f"Include depth exceeded maximum ({MAX_INCLUDE_DEPTH}). "
            f"Check for circular includes or deeply nested include chains."
        )

    include_list = data.get("include", [])
    if not include_list:
        return data

    # Start with empty base for merging included files
    merged: dict[str, Any] = {}

    for include_path_str in include_list:
        # Resolve include path (single-tier, no fallback)
        include_path = _resolve_include_path(include_path_str, ot_dir)

        if include_path is None:
            # Warning already logged in _resolve_include_path
            continue

        try:
            with include_path.open() as f:
                include_data = yaml.safe_load(f)

            if not include_data or not isinstance(include_data, dict):
                logger.debug(f"Empty or non-dict include file: {include_path}")
                continue

            # Recursively process nested includes (same ot_dir for all nested includes)
            include_data = _process_includes(include_data, ot_dir, depth + 1)

            # Merge this include file (later overrides earlier)
            merged = _deep_merge(merged, include_data)

            logger.debug(f"Merged include file: {include_path}")

        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in include file {include_path}: {e}")
        except OSError as e:
            logger.error(f"Error reading include file {include_path}: {e}")

    # Main file content (minus 'include' key) overrides everything
    main_content = {k: v for k, v in data.items() if k != "include"}
    result = _deep_merge(merged, main_content)

    # Preserve the include list for reference (but it's already processed)
    result["include"] = include_list

    return result


def load_config(config_path: Path | str | None = None) -> OneToolConfig:
    """Load OneTool configuration from YAML file (global-only).

    Resolution order (when config_path is None):
        1. ONETOOL_CONFIG env var
        2. ~/.onetool/config/onetool.yaml (global config only)
        3. ConfigNotFoundError (requires 'onetool init')

    No project-level configuration or inheritance is supported in V2.

    Example config::

        # ~/.onetool/config/onetool.yaml
        version: 1

        env:
          HOME: /home/user
          LANG: en_US.UTF-8

        tools_dir:
          - tools/*.py

    Args:
        config_path: Path to config file (overrides resolution)

    Returns:
        Validated OneToolConfig

    Raises:
        ConfigNotFoundError: If no config found and OneTool not initialized
        FileNotFoundError: If explicit config path doesn't exist
        ValueError: If YAML is invalid or validation fails
    """
    resolved_path = _resolve_config_path(config_path)

    if resolved_path is None:
        raise ConfigNotFoundError(
            "No configuration file found. Run 'onetool init' to initialize."
        )

    logger.debug(f"Loading config from {resolved_path}")

    raw_data = _load_yaml_file(resolved_path)
    expanded_data = _expand_secrets_recursive(raw_data)

    # Process includes before validation (merges external files)
    # Resolve includes from OT_DIR (.onetool/), not config_dir (.onetool/config/)
    config_dir = resolved_path.parent.resolve()
    ot_dir = config_dir.parent  # Go up from config/ to .onetool/
    merged_data = _process_includes(expanded_data, ot_dir)

    # Flatten nested arrays (compact array format support)
    flattened_data = _flatten_arrays_recursive(merged_data)

    _validate_version(flattened_data)

    try:
        config = OneToolConfig.model_validate(flattened_data)
    except Exception as e:
        raise ValueError(f"Invalid configuration in {resolved_path}: {e}") from e

    config._config_dir = config_dir

    logger.info(f"Config loaded: version {config.version}")

    return config


# Global config instance (singleton pattern)
# Thread-safety: Protected by _config_lock for safe concurrent access.
_config: OneToolConfig | None = None
_config_lock = threading.Lock()


def get_config(
    config_path: Path | str | None = None, reload: bool = False
) -> OneToolConfig:
    """Get or load the global configuration (singleton pattern).

    Returns a cached config instance. On first call, loads config from disk.
    Subsequent calls return the cached instance unless reload=True.

    Thread-safety: Protected by lock for safe concurrent access.

    Args:
        config_path: Path to config file (only used on first load or reload).
            Ignored after config is cached unless reload=True.
        reload: Force reload configuration from disk. Use sparingly - primarily
            intended for testing. In production, restart the process to reload.

    Returns:
        OneToolConfig instance (same instance on subsequent calls)
    """
    global _config

    with _config_lock:
        if _config is None or reload:
            _config = load_config(config_path)
        return _config


def is_log_verbose() -> bool:
    """Check if verbose logging is enabled.

    Verbose mode disables log truncation, showing full values.
    Enabled by:
    - OT_LOG_VERBOSE=true environment variable (highest priority)
    - log_verbose: true in config file

    Returns:
        True if verbose logging is enabled
    """
    # Environment variable takes priority
    env_verbose = os.getenv("OT_LOG_VERBOSE", "").lower()
    if env_verbose in ("true", "1", "yes"):
        return True
    if env_verbose in ("false", "0", "no"):
        return False

    # Fall back to config (thread-safe read)
    with _config_lock:
        if _config is not None:
            return _config.log_verbose

    return False


def get_tool_config(pack: str, schema: type[T] | None = None) -> T | dict[str, Any]:
    """Get configuration for a tool pack.

    Args:
        pack: Pack name (e.g., "brave", "ground", "context7")
        schema: Optional Pydantic model class to validate and return typed config.
                If provided, returns an instance of the schema with merged values.
                If None, returns raw config dict.

    Returns:
        If schema provided: Instance of schema with config values merged
        If no schema: Dict with raw config values (empty dict if not configured)

    Example:
        # With schema (recommended for type safety)
        class Config(BaseModel):
            timeout: float = 60.0

        config = get_tool_config("brave", Config)
        print(config.timeout)  # typed as float

        # Without schema (raw dict)
        raw = get_tool_config("brave")
        print(raw.get("timeout", 60.0))
    """
    # Get raw config values for this pack
    raw_config = _get_raw_config(pack)

    if schema is None:
        return raw_config

    # Validate and return typed config instance
    try:
        return schema.model_validate(raw_config)
    except Exception:
        # If validation fails, return defaults from schema
        return schema()


def _get_raw_config(pack: str) -> dict[str, Any]:
    """Get raw config dict for a pack from loaded configuration.

    This function handles both typed tools.X fields and extra fields
    allowed via model_config. It supports:
    1. Typed tools.X fields (e.g., tools.stats)
    2. Extra fields for tool packs (e.g., tools.brave)

    Args:
        pack: Pack name (e.g., "brave", "ground")

    Returns:
        Raw config dict for the pack, or empty dict if not configured
    """
    try:
        config = get_config()
    except Exception:
        # Config not loaded yet - return empty dict
        return {}

    # Get the tools section
    tools = config.tools

    # First check for typed attribute (e.g., tools.stats)
    if hasattr(tools, pack):
        pack_config = getattr(tools, pack)
        if hasattr(pack_config, "model_dump"):
            result: dict[str, Any] = pack_config.model_dump()
            return result
        # Handle raw dict from extra fields
        if isinstance(pack_config, dict):
            return pack_config
        return {}

    # Check model_extra for dynamically allowed fields
    if hasattr(tools, "model_extra") and tools.model_extra:
        extra = tools.model_extra
        if pack in extra:
            pack_data = extra[pack]
            if isinstance(pack_data, dict):
                return pack_data
            return {}

    return {}


def reset() -> None:
    """Clear config cache for reload.

    Use this as part of the config reload flow to force config to be
    reloaded from disk on next access.
    """
    global _config
    with _config_lock:
        _config = None
