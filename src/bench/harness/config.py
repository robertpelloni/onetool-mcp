"""YAML configuration loading for harness scenarios and tasks.

Loads ot-dev.yaml with test scenarios and harness configuration.
Supports variable expansion from secrets.yaml in the format ${VAR_NAME}.

Example ot-dev.yaml:

    defaults:
      model: openai/gpt-5-mini
      timeout: 120

    servers:
      onetool:
        type: stdio
        command: uv
        args: ["run", "onetool"]

    scenarios:
      - name: Basic Tests
        tasks:
          - name: hello world
            prompt: Say hello
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel, Field, field_validator

from ot.config.secrets import expand_vars

if TYPE_CHECKING:
    from pathlib import Path


def _expand_vars_in_dict(data: Any, skip_keys: set[str] | None = None) -> Any:
    """Recursively expand ${VAR} patterns in a dict/list structure."""
    if skip_keys is None:
        skip_keys = {"env"}
    if isinstance(data, dict):
        return {
            k: v if k in skip_keys else _expand_vars_in_dict(v, skip_keys)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_expand_vars_in_dict(v, skip_keys) for v in data]
    if isinstance(data, str):
        return expand_vars(data)
    return data


class ServerConfig(BaseModel):
    """Configuration for an MCP server connection."""

    type: Literal["http", "stdio"] = Field(description="Server connection type")
    url: str | None = Field(default=None, description="URL for HTTP servers")
    headers: dict[str, str] = Field(
        default_factory=dict, description="Headers for HTTP servers"
    )
    command: str | None = Field(default=None, description="Command for stdio servers")
    args: list[str] = Field(
        default_factory=list, description="Arguments for stdio command"
    )
    env: dict[str, str] = Field(
        default_factory=dict, description="Environment variables for stdio servers"
    )
    timeout: int | None = Field(
        default=None, description="Connection timeout in seconds (overrides default)"
    )

    @field_validator("url", "command", mode="before")
    @classmethod
    def expand_vars_validator(cls, v: str | None) -> str | None:
        """Expand variables in URL and command."""
        if v is None:
            return None
        return expand_vars(v)


class EvaluateConfig(BaseModel):
    """Configuration for evaluation (LLM or deterministic)."""

    # For deterministic checks - can be string, list, dict, number, bool
    expected: str | list[Any] | dict[str, Any] | int | float | bool | None = Field(
        default=None,
        description="Expected value(s) for deterministic evaluation",
    )

    # For regex pattern matching
    regex: str | None = Field(
        default=None,
        description="Regex pattern to match against response",
    )
    expect_match: bool = Field(
        default=True,
        description="If True, regex must match. If False, regex must NOT match.",
    )

    # For error tests - when True, test expects an error response
    # If LLM "fixes" the code and it succeeds, that's a failure
    expect_error: bool = Field(
        default=False,
        description="When True, test expects error/failure. Success without error pattern is a failure.",
    )

    # For LLM-as-judge evaluation
    prompt: str | None = Field(
        default=None,
        description="Evaluation prompt template with {response} and {expected}",
    )
    model: str | None = Field(
        default=None,
        description="Model to use for LLM evaluation (required if using LLM-as-judge)",
    )


class TaskConfig(BaseModel):
    """Configuration for a single task (direct or harness).

    Task types:
        - direct: Direct MCP tool invocation without LLM
        - harness: LLM benchmark with optional MCP servers (default)
    """

    name: str = Field(description="Task name")
    type: Literal["direct", "harness"] = Field(
        default="harness",
        description="Task type: 'direct' for MCP tool call, 'harness' for LLM benchmark",
    )

    # Common fields
    server: str | list[str] | None = Field(
        default=None, description="Server name(s) from servers - single or list"
    )
    timeout: int | None = Field(default=None, description="Timeout in seconds")
    tags: list[str] = Field(
        default_factory=list, description="Tags for filtering tasks"
    )

    # Harness-specific fields (type: harness)
    prompt: str | None = Field(
        default=None, description="Prompt to send to LLM (required for harness type)"
    )
    model: str | None = Field(default=None, description="Model override (harness only)")
    evaluate: str | EvaluateConfig | None = Field(
        default=None,
        description="Evaluation config (harness only)",
    )

    # Direct-specific fields (type: direct)
    tool: str | None = Field(
        default=None, description="Tool name to call (required for direct type)"
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict, description="Tool arguments (direct only)"
    )

    @field_validator("tags", mode="before")
    @classmethod
    def tags_default_empty(cls, v: list[str] | None) -> list[str]:
        """Convert None to empty list for tags."""
        return v if v is not None else []

    def model_post_init(self, __context: Any) -> None:
        """Validate type-specific required fields."""
        if self.type == "direct":
            if not self.tool:
                raise ValueError(
                    f"Task '{self.name}': type 'direct' requires 'tool' field"
                )
            if not self.server:
                raise ValueError(
                    f"Task '{self.name}': type 'direct' requires 'server' field"
                )
        elif self.type == "harness":
            if not self.prompt:
                raise ValueError(
                    f"Task '{self.name}': type 'harness' requires 'prompt' field"
                )


class ScenarioConfig(BaseModel):
    """Configuration for a benchmark scenario."""

    name: str = Field(description="Scenario name")
    description: str = Field(default="", description="Scenario description")
    tasks: list[TaskConfig] = Field(description="List of tasks in the scenario")


class DefaultsConfig(BaseModel):
    """Default configuration values."""

    timeout: int = Field(default=120, description="Default timeout in seconds")
    model: str = Field(default="openai/gpt-5-mini", description="Default model")
    system_prompt: str | None = Field(
        default=None, description="System prompt to prepend to all tasks"
    )


class HarnessConfig(BaseModel):
    """Root configuration for harness YAML files."""

    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    servers: dict[str, ServerConfig] = Field(default_factory=dict)
    evaluators: dict[str, EvaluateConfig] = Field(
        default_factory=dict,
        description="Named evaluators that can be referenced by tasks",
    )
    evaluate: EvaluateConfig | None = Field(
        default=None,
        description="Legacy: default evaluator (deprecated, use evaluators)",
    )
    scenarios: list[ScenarioConfig] = Field(default_factory=list)


def _convert_legacy_tools_config(data: dict[str, Any]) -> dict[str, Any]:
    """Convert legacy tools config to unified format.

    Legacy tools configs have tasks with 'tool' field but no 'type' field.
    This adds 'type: direct' to such tasks.

    Args:
        data: Parsed YAML data.

    Returns:
        Data with legacy tasks converted to unified format.
    """
    scenarios = data.get("scenarios", [])
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        tasks = scenario.get("tasks", [])
        for task in tasks:
            if not isinstance(task, dict):
                continue
            # If task has 'tool' but no 'type', it's a legacy direct task
            if "tool" in task and "type" not in task:
                task["type"] = "direct"
    return data


def load_config(path: Path) -> HarnessConfig:
    """Load and validate a YAML configuration file.

    Supports both unified configs (with explicit type field) and
    legacy configs (auto-detects direct vs harness based on content).

    Args:
        path: Path to the YAML file.

    Returns:
        Validated HarnessConfig.

    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the YAML is invalid.
    """
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with path.open() as f:
        raw_data = yaml.safe_load(f)

    if raw_data is None:
        raw_data = {}

    # Expand variables
    data = _expand_vars_in_dict(raw_data)

    # Convert legacy tools config format if needed
    data = _convert_legacy_tools_config(data)

    return HarnessConfig.model_validate(data)
