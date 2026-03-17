"""AWS MCP server management — credential management, identity, discovery, and server lifecycle.

Provides the ``aws`` tool pack for managing the official awslabs/mcp servers
with role-based activation, credential pre-flight, SSO login, MFA sessions,
and profile switching.

Quick start::

    aws.check()                         # Verify credentials
    aws.start_packs(role="finops")     # Activate cost/billing servers
    aws.start_packs(pack=["iam"])      # Activate specific servers
    aws.roles()                         # See all available roles
    aws.packs()                         # List active AWS servers

Credential setup::

    aws.profiles()                      # List configured profiles
    aws.login(profile="prod-sso")       # SSO login
    aws.mfa(profile="prod", token="123456")  # MFA session
    aws.use(profile="prod", region="us-east-1")  # Switch profile
"""

from __future__ import annotations

# Pack for dot notation: aws.check(), aws.start_packs(), etc.
pack = "aws"

__all__ = [
    "arn",
    "attributes",
    "check",
    "login",
    "mfa",
    "packs",
    "profile",
    "profiles",
    "refresh_packs",
    "regions",
    "roles",
    "services",
    "start_packs",
    "stop_packs",
    "use",
    "values",
    "whoami",
]

__ot_requires__ = {
    "lib": [("boto3", "pip install 'onetool-mcp[dev]'")],  # >=1.42.54
}

import configparser
import json
import os
import subprocess
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger
from otpack import LogSpan, get_tool_config
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Default server list — curated awslabs/mcp servers
# ---------------------------------------------------------------------------
# ServerDef.package: uvx package name (e.g. "awslabs.iam-mcp-server") or
#                    https:// URL for HTTP servers.
# ServerDef.doc:     None  = auto-derive from package name (awslabs.* only)
#                    ""    = no docs page exists
#                    "url" = explicit override
# ServerDef.core:    True  = recommended starting point (★ in aws.packs())
#
# Users can extend or override this via tools.aws.servers in onetool.yaml.
# To start a server not in this registry: aws.start_packs(pack="awslabs.foo-mcp-server")
# ---------------------------------------------------------------------------

_DOC_BASE = "https://awslabs.github.io/mcp/servers/"


@dataclass
class ServerDef:
    """Definition of a single awslabs MCP server."""

    package: str
    """uvx package name (e.g. ``awslabs.iam-mcp-server``) or ``https://`` URL."""

    doc: str | None = dataclass_field(default=None)
    """Doc URL override. ``None`` = auto-derive; ``""`` = no page; URL = explicit."""

    support_plan: str | None = dataclass_field(default=None)
    """Minimum AWS Support plan required to use this server.
    ``None`` = no plan required; ``"business"`` = Business or Enterprise."""

    core: bool = dataclass_field(default=False)
    """Whether this is a recommended core server (highlighted in discovery)."""


def _resolve_doc_url(defn: ServerDef) -> str | None:
    """Return the documentation URL for a server, or None if unavailable.

    Args:
        defn: Server definition.

    Returns:
        Full docs URL, or None if no page exists.
    """
    if defn.doc is not None:
        return defn.doc or None  # "" → None
    if defn.package.startswith("awslabs."):
        slug = defn.package[len("awslabs."):]
        return f"{_DOC_BASE}{slug}"
    return None


# Servers whose tools carry a name prefix that callers should be able to omit.
# e.g. aws-know exposes aws_search_documentation — with this declared,
# know.search_documentation() resolves correctly without pack_proxy needing
# to know about any specific server.
_TOOL_PREFIXES: dict[str, str] = {
    "know": "aws_",
}

_DEFAULT_SERVERS: dict[str, ServerDef] = {
    # Core / General Purpose  (★ = core)
    "api": ServerDef("awslabs.aws-api-mcp-server", core=True),
    "core": ServerDef("awslabs.core-mcp-server", core=True),
    "doc": ServerDef("awslabs.aws-documentation-mcp-server"),
    "diagram": ServerDef("awslabs.aws-diagram-mcp-server"),
    "support": ServerDef("awslabs.aws-support-mcp-server", support_plan="business"),
    # Knowledge (HTTP — no credentials required; doc slug differs from URL)
    "know": ServerDef(
        "https://knowledge-mcp.global.api.aws",
        doc=f"{_DOC_BASE}aws-knowledge-mcp-server",
        core=True,
    ),
    # Security & Identity
    "iam": ServerDef("awslabs.iam-mcp-server", core=True),
    "cloudtrail": ServerDef("awslabs.cloudtrail-mcp-server", core=True),
    "well-arch": ServerDef("awslabs.well-architected-security-mcp-server", support_plan="business"),
    # Cost & Billing
    "cost": ServerDef("awslabs.cost-explorer-mcp-server"),
    "billing": ServerDef("awslabs.billing-cost-management-mcp-server"),
    "pricing": ServerDef("awslabs.aws-pricing-mcp-server"),
    # Compute
    "ecs": ServerDef("awslabs.ecs-mcp-server"),
    "eks": ServerDef("awslabs.eks-mcp-server"),
    "lambda": ServerDef("awslabs.lambda-tool-mcp-server"),
    "lambda-handler": ServerDef("awslabs.mcp-lambda-handler", doc=""),  # no docs page
    "sfn": ServerDef("awslabs.stepfunctions-tool-mcp-server"),
    "serverless": ServerDef("awslabs.aws-serverless-mcp-server"),
    # Databases
    "dynamodb": ServerDef("awslabs.dynamodb-mcp-server"),
    "documentdb": ServerDef("awslabs.documentdb-mcp-server"),
    "mysql": ServerDef("awslabs.mysql-mcp-server"),
    "postgres": ServerDef("awslabs.postgres-mcp-server"),
    "redshift": ServerDef("awslabs.redshift-mcp-server"),
    "neptune": ServerDef("awslabs.amazon-neptune-mcp-server"),
    # Cache
    "elasticache": ServerDef("awslabs.elasticache-mcp-server"),
    "memcached": ServerDef("awslabs.memcached-mcp-server"),
    "valkey": ServerDef("awslabs.valkey-mcp-server"),
    # Storage
    "s3-tables": ServerDef("awslabs.s3-tables-mcp-server"),
    # Monitoring & Observability
    "cloudwatch": ServerDef("awslabs.cloudwatch-mcp-server"),
    "appsignals": ServerDef("awslabs.cloudwatch-applicationsignals-mcp-server"),
    "cloudwatch-appsignals": ServerDef("awslabs.cloudwatch-appsignals-mcp-server"),
    "prometheus": ServerDef("awslabs.prometheus-mcp-server"),
    # Networking
    "network": ServerDef("awslabs.aws-network-mcp-server"),
    "location": ServerDef("awslabs.aws-location-mcp-server"),
    # Messaging
    "sns-sqs": ServerDef("awslabs.amazon-sns-sqs-mcp-server"),
    "mq": ServerDef("awslabs.amazon-mq-mcp-server"),
    "msk": ServerDef("awslabs.aws-msk-mcp-server"),
    # Infrastructure as Code
    "cdk": ServerDef("awslabs.cdk-mcp-server"),
    "cfn": ServerDef("awslabs.cfn-mcp-server"),
    "terraform": ServerDef("awslabs.terraform-mcp-server"),
    "iac": ServerDef("awslabs.aws-iac-mcp-server"),
    # AI / Bedrock
    "agentcore": ServerDef("awslabs.amazon-bedrock-agentcore-mcp-server"),
    "bedrock-kb": ServerDef("awslabs.bedrock-kb-retrieval-mcp-server"),
    "bedrock-import": ServerDef("awslabs.aws-bedrock-custom-model-import-mcp-server"),
    "bedrock-da": ServerDef("awslabs.aws-bedrock-data-automation-mcp-server"),
    "canvas": ServerDef("awslabs.nova-canvas-mcp-server"),
    "qbusiness": ServerDef("awslabs.amazon-qbusiness-anonymous-mcp-server"),
    "kendra": ServerDef("awslabs.amazon-kendra-index-mcp-server"),
    # ML / SageMaker
    "sagemaker": ServerDef("awslabs.sagemaker-ai-mcp-server"),
    "spark-debug": ServerDef("awslabs.sagemaker-unified-studio-spark-troubleshooting-mcp-server"),
    "spark-upgrade": ServerDef("awslabs.sagemaker-unified-studio-spark-upgrade-mcp-server"),
    "synth": ServerDef("awslabs.syntheticdata-mcp-server"),
    # Data / Analytics
    "dataproc": ServerDef("awslabs.aws-dataprocessing-mcp-server"),
    # Developer Tools
    "repo-research": ServerDef("awslabs.git-repo-research-mcp-server"),
    "loader": ServerDef("awslabs.document-loader-mcp-server"),
    "openapi": ServerDef("awslabs.openapi-mcp-server"),
    "appsync": ServerDef("awslabs.aws-appsync-mcp-server"),
}


def _expand_server_defs(defs: dict[str, ServerDef]) -> dict[str, dict[str, str]]:
    """Expand ServerDef mapping to full registry entries.

    Args:
        defs: Mapping of short name to ServerDef.

    Returns:
        Registry entries with ``type``, ``package``/``url``, and optional ``doc``.
    """
    result: dict[str, dict[str, str]] = {}
    for name, defn in defs.items():
        if defn.package.startswith("https://"):
            entry: dict[str, str] = {"type": "http", "url": defn.package}
        else:
            entry = {"type": "stdio", "package": defn.package}
        doc = _resolve_doc_url(defn)
        if doc:
            entry["doc"] = doc
        if defn.support_plan:
            entry["support_plan"] = defn.support_plan
        if defn.core:
            entry["core"] = "true"
        result[name] = entry
    return result


def _expand_servers(raw: dict[str, str]) -> dict[str, dict[str, str]]:
    """Expand user-config short_name->package/url mapping to registry entries.

    Args:
        raw: User-supplied mapping of short name to package or URL.

    Returns:
        Registry entries with ``type``, ``package``/``url``, and optional ``doc``.
    """
    result: dict[str, dict[str, str]] = {}
    for name, value in raw.items():
        if value.startswith("https://"):
            result[name] = {"type": "http", "url": value}
        else:
            entry: dict[str, str] = {"type": "stdio", "package": value}
            if value.startswith("awslabs."):
                slug = value[len("awslabs."):]
                entry["doc"] = f"{_DOC_BASE}{slug}"
            result[name] = entry
    return result


# Built at import time from defaults; also recomputed when config changes.
_SERVER_REGISTRY: dict[str, dict[str, str]] = _expand_server_defs(_DEFAULT_SERVERS)

# ---------------------------------------------------------------------------
# Built-in Roles — 18 logical groupings of servers
# ---------------------------------------------------------------------------

_BUILTIN_ROLES: dict[str, list[str]] = {
    "all": list(_SERVER_REGISTRY.keys()),
    "finops": [
        "cost",
        "billing",
        "pricing",
        "support",
    ],
    "security": [
        "iam",
        "cloudtrail",
        "well-arch",
        "support",
    ],
    "compute": [
        "ecs",
        "eks",
        "lambda",
        "sfn",
        "serverless",
    ],
    "database": [
        "dynamodb",
        "documentdb",
        "mysql",
        "postgres",
        "redshift",
        "neptune",
    ],
    "cache": [
        "elasticache",
        "memcached",
        "valkey",
    ],
    "storage": [
        "s3-tables",
    ],
    "ai": [
        "agentcore",
        "bedrock-kb",
        "bedrock-import",
        "bedrock-da",
        "canvas",
        "qbusiness",
        "kendra",
    ],
    "ml": [
        "sagemaker",
        "spark-debug",
        "spark-upgrade",
        "synth",
    ],
    "monitoring": [
        "cloudwatch",
        "appsignals",
        "cloudwatch-appsignals",
        "prometheus",
        "cloudtrail",
    ],
    "networking": [
        "network",
        "location",
    ],
    "messaging": [
        "sns-sqs",
        "mq",
        "msk",
    ],
    "iac": [
        "cdk",
        "cfn",
        "terraform",
        "iac",
    ],
    "devtools": [
        "diagram",
        "repo-research",
        "loader",
        "openapi",
        "core",
    ],
    "data": [
        "dataproc",
        "s3-tables",
        "redshift",
        "synth",
    ],
    "discovery": [
        "doc",
        "core",
        "know",
        "pricing",
    ],
}


# ---------------------------------------------------------------------------
# Config Model
# ---------------------------------------------------------------------------


class Config(BaseModel):
    """AWS pack configuration."""

    profile: str | None = Field(default=None, description="Active AWS profile name")
    region: str | None = Field(default=None, description="Active AWS region")
    timeout: int = Field(default=30, ge=1, description="Boto3 API call timeout seconds")
    roles: dict[str, list[str]] = Field(
        default_factory=dict,
        description="User-defined roles mapping role name to list of server short names",
    )
    servers: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Additional servers beyond the built-in 69, or overrides. "
            "Format: {short_name: package-name} or {short_name: https://url}"
        ),
    )


def _get_config() -> Config:
    return get_tool_config("aws", Config)


# Tracks the profile explicitly set via aws.use() this session.
# Distinguishes "user switched profiles" from "ambient shell AWS_PROFILE".
_session_profile: str | None = None
_session_region: str | None = None


def _registry() -> dict[str, dict[str, str]]:
    """Return server registry merged with any user-defined servers from config."""
    cfg = _get_config()
    if not cfg.servers:
        return _SERVER_REGISTRY
    return {**_SERVER_REGISTRY, **_expand_servers(cfg.servers)}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make_server_config(short_name: str, package_override: str | None = None) -> Any:
    """Create a McpServerConfig for the given short server name.

    Args:
        short_name: Short server name from _SERVER_REGISTRY (e.g., "cost").
        package_override: Raw package name or URL for servers not in the registry.
            If provided and short_name is not in the registry, builds config directly
            from this value (e.g. ``"awslabs.frontend-mcp-server"`` or ``"https://..."``).

    Returns:
        McpServerConfig ready for connect_additional_sync.

    Raises:
        ValueError: If short_name is not in the registry and no package_override given.
    """
    from ot.config.models import McpServerConfig

    entry = _registry().get(short_name)
    if entry is None:
        if package_override is None:
            raise ValueError(f"Unknown server short name: {short_name!r}")
        # Build config directly from the raw package name / URL
        if package_override.startswith("https://"):
            return McpServerConfig(
                type="http",
                url=package_override,
                enabled=True,
                tool_prefix=_TOOL_PREFIXES.get(short_name),
            )
        return McpServerConfig(
            type="stdio",
            command="uvx",
            args=[package_override],
            inherit_env=True,
            enabled=True,
            env={},
            tool_prefix=_TOOL_PREFIXES.get(short_name),
        )

    tool_prefix = _TOOL_PREFIXES.get(short_name)

    if entry["type"] == "http":
        return McpServerConfig(
            type="http",
            url=entry["url"],
            enabled=True,
            tool_prefix=tool_prefix,
        )
    else:
        # Some servers require a specific region regardless of the active profile.
        # aws-pricing-mcp-server only works via the us-east-1 Pricing API endpoint.
        extra_env: dict[str, str] = {}
        if short_name == "pricing":
            extra_env["AWS_DEFAULT_REGION"] = "us-east-1"

        return McpServerConfig(
            type="stdio",
            command="uvx",
            args=[entry["package"]],
            inherit_env=True,
            enabled=True,
            env=extra_env,
            tool_prefix=tool_prefix,
        )


def _resolve_targets(
    role: str | None,
    pack: str | list[str] | None,
) -> tuple[set[str], dict[str, str], str]:
    """Resolve role/pack args to a set of short server names.

    Accepts raw package names (contain ``.``) or HTTPS URLs as pack items —
    these bypass the registry and derive a short name automatically.
    E.g. ``"awslabs.frontend-mcp-server"`` → short name ``"frontend"``.

    Returns:
        ``(targets, ephemeral, "")`` on success, or
        ``(None, {}, error_message)`` on failure.
        ``ephemeral`` maps short names to raw package/URL for servers not in the registry.
    """
    all_roles = _merged_roles()
    targets: set[str] = set()
    ephemeral: dict[str, str] = {}  # short_name -> raw package/URL (unregistered only)

    if role is not None:
        if role not in all_roles:
            available = ", ".join(sorted(all_roles.keys()))
            return None, {}, f"Unknown role {role!r}. Available: {available}"
        targets.update(all_roles[role])

    if pack is not None:
        reg = _registry()
        pack_list = [pack] if isinstance(pack, str) else list(pack)
        for p in pack_list:
            if p.startswith("https://") or ("." in p and "/" not in p):
                # Raw package name or HTTP URL — derive short name and bypass registry
                if p.startswith("awslabs."):
                    slug = p[len("awslabs."):]
                    short = slug.removesuffix("-mcp-server")
                elif p.startswith("https://"):
                    # Derive from hostname first segment (best-effort)
                    host = p.split("//", 1)[1].split("/")[0]
                    short = host.split(".")[0]
                else:
                    # Other dotted name (e.g. "org.package-name")
                    short = p.rsplit(".", 1)[-1]
                targets.add(short)
                if short not in reg:
                    ephemeral[short] = p
            elif p in reg:
                targets.add(p)
            else:
                return None, {}, f"Unknown server {p!r}. Use aws.roles() to browse available servers."

    return targets, ephemeral, ""


def _merged_roles() -> dict[str, list[str]]:
    """Return built-in roles merged with user-defined roles.

    User roles win on name collision (consistent with include: config merge).
    """
    cfg = _get_config()
    merged = dict(_BUILTIN_ROLES)
    merged.update(cfg.roles)
    return merged


def _boto3_session(profile: str | None = None, region: str | None = None) -> Any:
    """Create a boto3 Session with the active profile and region."""
    import boto3  # type: ignore[import-untyped]

    cfg = _get_config()
    return boto3.Session(
        profile_name=profile or cfg.profile or os.environ.get("AWS_PROFILE"),
        region_name=region or cfg.region or os.environ.get("AWS_DEFAULT_REGION"),
    )


def _boto3_client(
    service: str, profile: str | None = None, region: str | None = None
) -> Any:
    """Create a boto3 client for the given service."""
    return _boto3_session(profile=profile, region=region).client(service)


def _parse_sso_expiry(expiry_str: str) -> datetime:
    """Parse SSO cache expiresAt string to aware datetime."""
    # Formats seen: "2024-01-15T10:30:00UTC", "2024-01-15T10:30:00Z"
    for fmt in ("%Y-%m-%dT%H:%M:%SUTC", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            dt = datetime.strptime(expiry_str, fmt)
            return dt.replace(tzinfo=UTC)
        except ValueError:
            continue
    # Last resort: isoformat parse
    return datetime.fromisoformat(
        expiry_str.replace("UTC", "+00:00").replace("Z", "+00:00")
    )


# ---------------------------------------------------------------------------
# Section 5: Credential & Identity Tools
# ---------------------------------------------------------------------------


def check(*, profile: str | None = None) -> dict[str, Any]:
    """Validate active AWS credentials and return a health report.

    First reads ~/.aws/sso/cache/*.json for early SSO expiry detection,
    then falls through to STS GetCallerIdentity for confirmation.

    Args:
        profile: AWS profile name. Defaults to active profile from config or AWS_PROFILE.

    Returns:
        Dict with keys: status, profile, account, arn, expiry, fix.
        status values: "ok", "expired", "no_credentials", "error"

    Examples:
        aws.check()
        aws.check(profile="prod-sso")
    """
    from botocore.exceptions import (  # type: ignore[import-untyped]
        ClientError,
        NoCredentialsError,
        ProfileNotFound,
    )

    active_profile = (
        profile or _get_config().profile or os.environ.get("AWS_PROFILE", "default")
    )

    with LogSpan(span="aws.check", profile=active_profile) as s:
        # Step 1: Read SSO cache for early expiry detection
        sso_cache_dir = Path.home() / ".aws" / "sso" / "cache"
        if sso_cache_dir.exists():
            now = datetime.now(tz=UTC)
            for cache_file in sso_cache_dir.glob("*.json"):
                try:
                    data = json.loads(cache_file.read_text())
                    if "expiresAt" in data:
                        expiry = _parse_sso_expiry(data["expiresAt"])
                        if expiry <= now:
                            s.add(status="expired")
                            return {
                                "status": "expired",
                                "profile": active_profile,
                                "account": None,
                                "arn": None,
                                "region": None,
                                "expiry": data["expiresAt"],
                                "fix": f"aws.login(profile={active_profile!r})",
                            }
                except Exception:
                    continue

        # Step 2: STS GetCallerIdentity
        try:
            session = _boto3_session(
                profile=active_profile if active_profile != "default" else None,
            )
            sts = session.client("sts")
            identity = sts.get_caller_identity()
            region = session.region_name or os.environ.get(
                "AWS_DEFAULT_REGION", "us-east-1"
            )

            s.add(status="ok", account=identity["Account"])
            return {
                "status": "ok",
                "profile": active_profile,
                "account": identity["Account"],
                "arn": identity["Arn"],
                "region": region,
                "expiry": None,
                "fix": None,
            }

        except ProfileNotFound:
            s.add(status="error", reason="profile_not_found")
            return {
                "status": "error",
                "profile": active_profile,
                "account": None,
                "arn": None,
                "region": None,
                "expiry": None,
                "fix": "aws.profiles()  # list available profiles",
            }

        except NoCredentialsError:
            s.add(status="no_credentials")
            return {
                "status": "no_credentials",
                "profile": active_profile,
                "account": None,
                "arn": None,
                "region": None,
                "expiry": None,
                "fix": "aws configure",
            }

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("ExpiredToken", "ExpiredTokenException"):
                s.add(status="expired", error_code=error_code)
                return {
                    "status": "expired",
                    "profile": active_profile,
                    "account": None,
                    "arn": None,
                    "region": None,
                    "expiry": None,
                    "fix": f"aws.login(profile={active_profile!r})",
                }
            s.add(status="error", error_code=error_code)
            return {
                "status": "error",
                "profile": active_profile,
                "account": None,
                "arn": None,
                "region": None,
                "expiry": None,
                "fix": f"aws.login(profile={active_profile!r})",
            }


def login(*, profile: str | None = None) -> dict[str, Any]:
    """Initiate an AWS SSO login flow and block until complete.

    Runs ``aws sso login`` as a subprocess and waits for the browser
    authentication to complete.

    Args:
        profile: AWS profile name. Defaults to active profile from config or AWS_PROFILE.

    Returns:
        Dict with login result and confirmed identity.

    Examples:
        aws.login()
        aws.login(profile="prod-sso")
    """
    active_profile = (
        profile or _get_config().profile or os.environ.get("AWS_PROFILE", "default")
    )

    with LogSpan(span="aws.login", profile=active_profile) as s:
        cmd = ["aws", "sso", "login"]
        if active_profile and active_profile != "default":
            cmd += ["--profile", active_profile]

        try:
            result = subprocess.run(
                cmd,
                capture_output=False,
                text=True,
                check=True,
            )
            _ = result  # subprocess completed
        except subprocess.CalledProcessError as e:
            s.add(status="error")
            return {"status": "error", "error": f"aws sso login failed: {e}"}
        except FileNotFoundError:
            s.add(status="error", reason="aws_cli_not_found")
            return {
                "status": "error",
                "error": "AWS CLI not found. Install from https://aws.amazon.com/cli/",
            }

        # Confirm identity after login
        identity = whoami()
        s.add(status="ok")
        return {"status": "ok", "profile": active_profile, **identity}


def mfa(*, profile: str, token: str) -> dict[str, Any]:
    """Obtain a temporary MFA session and write it to ~/.aws/credentials.

    Looks up the MFA device associated with the profile's IAM user,
    calls STS GetSessionToken with the provided TOTP token, and writes
    the resulting credentials to ~/.aws/credentials under ``[<profile>-mfa]``.

    Args:
        profile: AWS profile name to obtain MFA session for.
        token: 6-digit TOTP token from your MFA device.

    Returns:
        Dict with mfa_profile name, expiry, and ttl.

    Examples:
        aws.mfa(profile="prod", token="123456")
    """
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]

    with LogSpan(span="aws.mfa", profile=profile) as s:
        try:
            iam = _boto3_client("iam", profile=profile)
            devices = iam.list_mfa_devices()["MFADevices"]
            if not devices:
                s.add(status="error", reason="no_mfa_devices")
                return {
                    "status": "error",
                    "error": "No MFA devices found for this profile",
                }
            serial_number = devices[0]["SerialNumber"]

            sts = _boto3_client("sts", profile=profile)
            resp = sts.get_session_token(
                SerialNumber=serial_number,
                TokenCode=token,
                DurationSeconds=43200,  # 12 hours
            )
            creds = resp["Credentials"]

        except ClientError as e:
            s.add(status="error", error=str(e))
            return {"status": "error", "error": str(e)}

        mfa_profile = f"{profile}-mfa"
        creds_path = Path.home() / ".aws" / "credentials"
        parser = configparser.ConfigParser()
        if creds_path.exists():
            parser.read(creds_path)
        parser[mfa_profile] = {
            "aws_access_key_id": creds["AccessKeyId"],
            "aws_secret_access_key": creds["SecretAccessKey"],
            "aws_session_token": creds["SessionToken"],
        }
        creds_path.parent.mkdir(parents=True, exist_ok=True)
        with creds_path.open("w") as fh:
            parser.write(fh)

        s.add(status="ok", mfa_profile=mfa_profile)
        return {
            "status": "ok",
            "mfa_profile": mfa_profile,
            "expires": str(creds["Expiration"]),
            "ttl": "12h",
            "usage": f"aws.use(profile={mfa_profile!r})",
        }


def profiles() -> list[str]:
    """Return all configured AWS profile names.

    Reads both ~/.aws/config and ~/.aws/credentials to build the full list.

    Returns:
        Sorted list of profile names.

    Examples:
        aws.profiles()
    """
    found: set[str] = set()

    for path in [Path.home() / ".aws" / "config", Path.home() / ".aws" / "credentials"]:
        if path.exists():
            parser = configparser.ConfigParser()
            parser.read(path)
            for section in parser.sections():
                # config file uses "profile foo", credentials file uses "foo"
                name = section.removeprefix("profile ").strip()
                if name:
                    found.add(name)

    return sorted(found)


def use(*, profile: str, region: str | None = None) -> dict[str, Any]:
    """Switch the active AWS profile and restart active stdio AWS sub-servers.

    Updates AWS_PROFILE (and optionally AWS_DEFAULT_REGION) in the process
    environment, then restarts all currently active aws-* stdio sub-servers
    so they pick up the new credentials.

    Args:
        profile: AWS profile name to switch to.
        region: AWS region override. If omitted, region is unchanged.

    Returns:
        Dict with confirmed identity and list of restarted servers.

    Examples:
        aws.use(profile="prod")
        aws.use(profile="staging", region="eu-west-1")
    """
    from ot.proxy.manager import get_proxy_manager

    with LogSpan(span="aws.use", profile=profile, region=region) as s:
        global _session_profile, _session_region
        _session_profile = profile
        os.environ["AWS_PROFILE"] = profile
        if region:
            _session_region = region
            os.environ["AWS_DEFAULT_REGION"] = region

        proxy = get_proxy_manager()
        restarted: list[str] = []

        reg = _registry()
        for server_name in list(proxy.servers):
            if not server_name.startswith("aws-"):
                continue
            short = server_name[4:]  # strip "aws-" prefix
            entry = reg.get(short, {})
            if entry.get("type") == "http":
                continue  # HTTP servers have no process to restart

            proxy.disconnect_server_sync(server_name)
            cfg = _make_server_config(short)
            result = proxy.connect_additional_sync(server_name, cfg)
            restarted.append(f"{server_name}: {result}")

        identity = whoami()
        s.add(restarted=len(restarted))
        return {**identity, "restarted_servers": restarted}


def whoami() -> dict[str, Any]:
    """Return the current caller identity via STS GetCallerIdentity.

    Returns:
        Dict with keys: account, arn, user_id, region, profile.

    Examples:
        aws.whoami()
    """
    from botocore.exceptions import (  # type: ignore[import-untyped]
        ClientError,
        NoCredentialsError,
    )

    session = _boto3_session()
    with LogSpan(span="aws.whoami") as s:
        try:
            sts = session.client("sts")
            identity = sts.get_caller_identity()
            s.add(account=identity["Account"])
            return {
                "account": identity["Account"],
                "arn": identity["Arn"],
                "user_id": identity["UserId"],
                "region": session.region_name
                or os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
                "profile": session.profile_name
                or os.environ.get("AWS_PROFILE", "default"),
            }
        except NoCredentialsError:
            s.add(error="no_credentials")
            return {"error": "No credentials configured. Run aws.check() for details."}
        except ClientError as e:
            s.add(error=str(e))
            return {"error": str(e)}


def profile() -> dict[str, Any]:
    """Return the active profile, region, account ID, and account alias.

    Returns:
        Dict with keys: profile, region, account, alias.

    Examples:
        aws.profile()
    """
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]

    with LogSpan(span="aws.profile") as s:
        session = _boto3_session()
        try:
            sts = session.client("sts")
            identity_raw = sts.get_caller_identity()
        except Exception as e:
            s.add(error=str(e))
            return {"error": str(e)}

        alias = ""
        try:
            iam = session.client("iam")
            aliases = iam.list_account_aliases()["AccountAliases"]
            alias = aliases[0] if aliases else ""
        except ClientError:
            pass

        identity = {
            "account": identity_raw["Account"],
            "arn": identity_raw["Arn"],
            "region": session.region_name
            or os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            "profile": session.profile_name or os.environ.get("AWS_PROFILE", "default"),
        }

        s.add(account=identity.get("account"), alias=alias)
        return {
            "profile": identity.get("profile"),
            "region": identity.get("region"),
            "account": identity.get("account"),
            "alias": alias,
            "arn": identity.get("arn"),
        }


# ---------------------------------------------------------------------------
# Section 6: Discovery Tools
# ---------------------------------------------------------------------------

# Mapping of AWS service name to console URL template
_CONSOLE_URL_TEMPLATES: dict[str, str] = {
    "iam": "https://console.aws.amazon.com/iam/home#{resource}",
    "lambda": "https://console.aws.amazon.com/lambda/home?region={region}#/functions/{resource}",
    "s3": "https://console.aws.amazon.com/s3/buckets/{resource}",
    "ec2": "https://console.aws.amazon.com/ec2/v2/home?region={region}#Instances",
    "ecs": "https://console.aws.amazon.com/ecs/home?region={region}",
    "eks": "https://console.aws.amazon.com/eks/home?region={region}",
    "rds": "https://console.aws.amazon.com/rds/home?region={region}",
    "dynamodb": "https://console.aws.amazon.com/dynamodbv2/home?region={region}",
    "cloudwatch": "https://console.aws.amazon.com/cloudwatch/home?region={region}",
    "logs": "https://console.aws.amazon.com/cloudwatch/home?region={region}#logsV2",
    "sns": "https://console.aws.amazon.com/sns/v3/home?region={region}",
    "sqs": "https://console.aws.amazon.com/sqs/v3/home?region={region}",
    "secretsmanager": "https://console.aws.amazon.com/secretsmanager/home?region={region}",
    "kms": "https://console.aws.amazon.com/kms/home?region={region}",
    "cloudformation": "https://console.aws.amazon.com/cloudformation/home?region={region}",
    "stepfunctions": "https://console.aws.amazon.com/states/home?region={region}",
    "sagemaker": "https://console.aws.amazon.com/sagemaker/home?region={region}",
    "bedrock": "https://console.aws.amazon.com/bedrock/home?region={region}",
}


def arn(*, arn_string: str) -> dict[str, Any]:
    """Parse an AWS ARN string into its components.

    ARN format: ``arn:partition:service:region:account-id:resource``

    Args:
        arn_string: Full ARN string to parse.

    Returns:
        Dict with keys: partition, service, region, account, resource, console_url.

    Examples:
        aws.arn(arn_string="arn:aws:iam::123456789012:role/MyRole")
        aws.arn(arn_string="arn:aws:lambda:us-east-1:123456789:function:my-fn")
    """
    if not arn_string.startswith("arn:"):
        return {"error": f"Not a valid ARN: {arn_string!r}"}

    parts = arn_string.split(":", 5)
    if len(parts) < 6:
        return {
            "error": f"Malformed ARN (expected 6 colon-separated parts): {arn_string!r}"
        }

    _, partition, service, region, account, resource = parts

    # Build console URL
    template = _CONSOLE_URL_TEMPLATES.get(service, "")
    if template:
        # For type:name resources (e.g. Lambda "function:my-fn"), use the name part only
        resource_for_url = resource.rsplit(":", 1)[-1] if ":" in resource else resource
        # IAM needs plural type mapping: role/MyRole -> /roles/MyRole
        if service == "iam" and "/" in resource_for_url:
            _IAM_PLURAL = {
                "role": "roles",
                "user": "users",
                "group": "groups",
                "policy": "policies",
            }
            iam_type, iam_name = resource_for_url.split("/", 1)
            resource_for_url = f"/{_IAM_PLURAL.get(iam_type, iam_type + 's')}/{iam_name}"
        console_url = template.format(region=region, resource=resource_for_url)
    else:
        console_url = (
            f"https://console.aws.amazon.com/{service}/home?region={region}"
            if region
            else f"https://console.aws.amazon.com/{service}/home"
        )

    return {
        "partition": partition,
        "service": service,
        "region": region,
        "account": account,
        "resource": resource,
        "console_url": console_url,
    }


def regions(*, service: str = "ec2") -> list[str]:
    """Return available regions for an AWS service.

    Args:
        service: AWS service name (e.g., "ec2", "lambda", "sagemaker"). Default: "ec2".

    Returns:
        Sorted list of region name strings.

    Examples:
        aws.regions()
        aws.regions(service="lambda")
    """
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]

    with LogSpan(span="aws.regions", service=service) as s:
        session = _boto3_session()

        if service == "ec2":
            try:
                ec2 = session.client("ec2", region_name="us-east-1")
                result = ec2.describe_regions(
                    Filters=[
                        {
                            "Name": "opt-in-status",
                            "Values": ["opt-in-not-required", "opted-in"],
                        }
                    ]
                )
                region_list = sorted(r["RegionName"] for r in result["Regions"])
                s.add(count=len(region_list))
                return region_list
            except ClientError as e:
                s.add(status="error")
                return [f"error: {e}"]

        # For other services, use boto3's built-in region list
        try:
            available = session.get_available_regions(service)
            region_list = sorted(available)
            s.add(count=len(region_list))
            return region_list
        except Exception:
            # Fallback: return EC2 regions as a proxy
            logger.warning("aws.regions: get_available_regions({!r}) failed, falling back to EC2 regions", service)
            s.add(status="fallback")
            return regions(service="ec2")


def services(*, filter: str | None = None, limit: int = 100) -> list[str]:
    """List AWS service codes from the Pricing API.

    Uses Pricing API (always us-east-1 endpoint). Returns hundreds of
    service codes — use filter to narrow results or limit to cap the count.

    Args:
        filter: Case-insensitive substring filter on service codes.
        limit: Maximum number of results to return. Default: 100.

    Returns:
        Sorted list of service code strings (e.g., "AmazonEC2", "AmazonRDS").

    Examples:
        aws.services(filter="RDS")
        aws.services(filter="Amazon", limit=20)
    """
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]

    with LogSpan(span="aws.services", filter=filter, limit=limit) as s:
        try:
            pricing = _boto3_client("pricing", region="us-east-1")
            paginator = pricing.get_paginator("describe_services")
            lf = filter.lower() if filter else None
            codes: list[str] = []
            for page in paginator.paginate():
                for svc in page["Services"]:
                    code = svc["ServiceCode"]
                    if lf is None or lf in code.lower():
                        codes.append(code)
                if len(codes) >= limit:
                    break

            result = sorted(codes[:limit])
            s.add(count=len(result))
            return result

        except ClientError as e:
            s.add(status="error")
            return [f"error: {e}"]


def attributes(*, service: str) -> list[str]:
    """Return filterable attribute names for an AWS pricing service.

    Args:
        service: AWS service code (e.g., "AmazonEC2"). Use aws.services() to list codes.

    Returns:
        Sorted list of attribute name strings.

    Examples:
        aws.attributes(service="AmazonEC2")
    """
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]

    with LogSpan(span="aws.attributes", service=service) as s:
        try:
            pricing = _boto3_client("pricing", region="us-east-1")
            result = pricing.describe_services(
                ServiceCode=service, FormatVersion="aws_v1"
            )
            svcs = result.get("Services", [])
            if not svcs:
                s.add(status="not_found")
                return [f"error: service {service!r} not found"]
            attr_list = sorted(svcs[0].get("AttributeNames", []))
            s.add(count=len(attr_list))
            return attr_list

        except ClientError as e:
            s.add(status="error")
            return [f"error: {e}"]


def values(*, service: str, attribute: str) -> list[str]:
    """Return valid values for a pricing attribute.

    Args:
        service: AWS service code (e.g., "AmazonEC2").
        attribute: Attribute name (e.g., "instanceType"). Use aws.attributes() to list.

    Returns:
        Sorted list of attribute value strings.

    Examples:
        aws.values(service="AmazonEC2", attribute="instanceType")
    """
    from botocore.exceptions import ClientError  # type: ignore[import-untyped]

    with LogSpan(span="aws.values", service=service, attribute=attribute) as s:
        try:
            pricing = _boto3_client("pricing", region="us-east-1")
            paginator = pricing.get_paginator("get_attribute_values")
            vals: list[str] = []
            for page in paginator.paginate(
                ServiceCode=service, AttributeName=attribute
            ):
                for item in page.get("AttributeValues", []):
                    vals.append(item["Value"])
            result = sorted(vals)
            s.add(count=len(result))
            return result

        except ClientError as e:
            s.add(status="error")
            return [f"error: {e}"]


# ---------------------------------------------------------------------------
# Section 7: Server Lifecycle Tools
# ---------------------------------------------------------------------------

# Servers that expose deployed AWS resources as tools — 0 tools is expected
# when no matching resources exist in the account.
_DYNAMIC_TOOL_HINTS: dict[str, str] = {
    "lambda": "deploy Lambda functions or set FUNCTION_PREFIX/FUNCTION_LIST env var",
    "sfn": "deploy state machines or set STATE_MACHINE_PREFIX/STATE_MACHINE_LIST env var",
}


def roles() -> dict[str, Any]:
    """List all available roles with their server lists.

    Merges built-in roles with any user-defined roles from
    ``tools: aws: roles:`` in onetool.yaml. User-defined roles are
    tagged with ``[user]``.

    Returns:
        Dict mapping role name to {"servers": [...], "user": bool}.

    Examples:
        aws.roles()
    """
    cfg = _get_config()
    user_role_names = set(cfg.roles.keys())
    merged = {**_BUILTIN_ROLES, **cfg.roles}

    return {
        role_name: {
            "servers": sorted(server_list),
            "user": role_name in user_role_names,
        }
        for role_name, server_list in sorted(merged.items())
    }


def packs() -> dict[str, Any]:
    """List currently connected AWS MCP sub-servers with tool counts and doc links.

    Returns:
        Dict mapping short server name to ``{tools, doc?, core?}``, or a message
        if none active. Core servers (recommended starting points) include ``"core": true``.

    Examples:
        aws.packs()
    """
    from ot.proxy.manager import get_proxy_manager

    proxy = get_proxy_manager()
    reg = _registry()

    result: dict[str, Any] = {}
    for name in proxy.servers:
        if not name.startswith("aws-"):
            continue
        short = name[4:]
        count = proxy.server_tool_count(name)
        entry = reg.get(short, {})
        pack_info: dict[str, Any] = {"tools": count}
        if "doc" in entry:
            pack_info["doc"] = entry["doc"]
        if entry.get("core"):
            pack_info["core"] = True
        result[short] = pack_info

    if not result:
        return {"message": "No AWS packs active. Use aws.start_packs() to activate."}

    return result


def start_packs(
    *,
    role: str | None = None,
    pack: str | list[str] | None = None,
) -> dict[str, Any]:
    """Connect AWS MCP sub-servers without disrupting existing connections.

    Validates credentials before connecting stdio servers. HTTP servers
    (e.g., aws-know) skip credential pre-flight.

    Args:
        role: Role name to activate (e.g., "finops", "security"). Use aws.roles() to list.
        pack: Server short name or list of names (e.g., "iam" or ["iam", "ecs"]).

    Returns:
        Dict mapping server name to connection status.

    Examples:
        aws.start_packs(role="finops")
        aws.start_packs(pack=["iam", "cloudwatch"])
        aws.start_packs(role="finops", pack=["iam"])
    """
    from ot.proxy.manager import get_proxy_manager

    if role is None and pack is None:
        return {"error": "Specify role= or pack= (or both)"}

    targets, ephemeral, err = _resolve_targets(role, pack)
    if targets is None:
        return {"error": err}

    reg = _registry()
    # For targets not in registry, check ephemeral for type; default to stdio
    def _entry_type(short: str) -> str:
        if short in reg:
            return reg[short].get("type", "stdio")
        pkg = ephemeral.get(short, "")
        return "http" if pkg.startswith("https://") else "stdio"

    stdio_targets = [t for t in targets if _entry_type(t) != "http"]
    http_targets = [t for t in targets if _entry_type(t) == "http"]

    results: dict[str, str] = {}
    proxy = get_proxy_manager()

    with LogSpan(span="aws.start_packs", role=role, count=len(targets)) as span:
        # Credential pre-flight for stdio servers
        cred_status: dict[str, Any] = {}
        cred_ok = True
        if stdio_targets:
            cred_status = check()
            cred_ok = cred_status.get("status") == "ok"

            # Ensure AWS_PROFILE and AWS_DEFAULT_REGION are set in os.environ so that
            # sub-server subprocesses (inherit_env=True) pick up the active profile.
            # Priority: aws.use() this session > onetool.yaml config > ambient shell env
            cfg = _get_config()
            active_profile = _session_profile or cfg.profile or os.environ.get("AWS_PROFILE")
            if active_profile:
                os.environ["AWS_PROFILE"] = active_profile
            active_region = _session_region or cfg.region or os.environ.get("AWS_DEFAULT_REGION")
            if active_region:
                os.environ["AWS_DEFAULT_REGION"] = active_region

        # Connect stdio servers
        for short in sorted(stdio_targets):
            if not cred_ok:
                results[short] = (
                    f"skipped: credentials {cred_status.get('status', 'unknown')} "
                    f"— run aws.check()"
                )
                continue
            results[short] = proxy.connect_additional_sync(
                f"aws-{short}", _make_server_config(short, package_override=ephemeral.get(short))
            )

        # Connect HTTP servers (no credential check)
        for short in sorted(http_targets):
            results[short] = proxy.connect_additional_sync(
                f"aws-{short}", _make_server_config(short, package_override=ephemeral.get(short))
            )

        # Append hints for dynamic-tool servers that connected with 0 tools
        for short, status in results.items():
            if status == "ok (0 tools)" and short in _DYNAMIC_TOOL_HINTS:
                results[short] = f"ok (0 tools) — {_DYNAMIC_TOOL_HINTS[short]}"

        span.add(connected=sum(1 for v in results.values() if v.startswith("ok")))

    # Clear security validator namespace cache so new aws-* namespaces are allowed
    from ot.executor.validator import reset as _validator_reset

    _validator_reset()

    return results


def stop_packs(
    *,
    role: str | None = None,
    pack: str | list[str] | None = None,
) -> dict[str, Any]:
    """Disconnect AWS MCP sub-servers without affecting other connections.

    Args:
        role: Role name to deactivate (e.g., "finops"). Use aws.roles() to list.
        pack: Server short name or list of names (e.g., "iam" or ["iam", "ecs"]).

    Returns:
        Dict mapping server name to disconnect status.

    Examples:
        aws.stop_packs(role="finops")
        aws.stop_packs(pack=["iam"])
    """
    from ot.proxy.manager import get_proxy_manager

    if role is None and pack is None:
        return {"error": "Specify role= or pack= (or both)"}

    targets, _ephemeral, err = _resolve_targets(role, pack)
    if targets is None:
        return {"error": err}

    proxy = get_proxy_manager()
    results: dict[str, str] = {}

    with LogSpan(span="aws.stop_packs", role=role, count=len(targets)):
        for short in sorted(targets):
            results[short] = proxy.disconnect_server_sync(f"aws-{short}")

    # Clear security validator namespace cache so removed namespaces are no longer allowed
    from ot.executor.validator import reset as _validator_reset

    _validator_reset()

    return results


def refresh_packs() -> dict[str, Any]:
    """Restart all active AWS stdio servers with current credentials.

    Useful after ``aws.mfa()`` or any credential change that doesn't involve
    a profile switch. HTTP servers (e.g., aws-know) are skipped as they
    require no credentials.

    Returns:
        Dict mapping short server name to reconnection status.

    Examples:
        aws.mfa(profile="prod", token="123456")
        aws.use(profile="prod-mfa")
        aws.refresh_packs()
    """
    from ot.proxy.manager import get_proxy_manager

    proxy = get_proxy_manager()
    reg = _registry()
    results: dict[str, str] = {}

    active_aws = [
        name for name in proxy.servers
        if name.startswith("aws-") and reg.get(name[4:], {}).get("type") != "http"
    ]

    if not active_aws:
        return {"message": "No active AWS stdio packs to refresh."}

    with LogSpan(span="aws.refresh_packs", count=len(active_aws)) as span:
        cred_status = check()
        if cred_status.get("status") != "ok":
            return {
                "error": f"credentials {cred_status.get('status')} — run aws.check()",
            }

        for server_name in sorted(active_aws):
            short = server_name[4:]
            proxy.disconnect_server_sync(server_name)
            results[short] = proxy.connect_additional_sync(server_name, _make_server_config(short))

        span.add(restarted=len(results))

    # Clear security validator namespace cache to reflect reconnected servers
    from ot.executor.validator import reset as _validator_reset

    _validator_reset()

    return results
