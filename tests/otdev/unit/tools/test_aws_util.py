"""Unit tests for aws_util tool pack."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_boto3_available = (
    importlib.util.find_spec("boto3") is not None
    and importlib.util.find_spec("botocore") is not None
)
_skip_boto = pytest.mark.skipif(not _boto3_available, reason="boto3/botocore not installed ([dev] extra)")


# ---------------------------------------------------------------------------
# Task 9.1 — aws.arn() parsing correctness
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestAwsArn:
    """Unit tests for aws.arn() ARN parsing."""

    def _arn(self, arn_string: str) -> dict:
        from otdev.tools.aws_util import arn

        return arn(arn_string=arn_string)

    def test_iam_role_arn(self) -> None:
        """Should parse IAM role ARN with empty region."""
        result = self._arn("arn:aws:iam::123456789012:role/MyRole")

        assert result["partition"] == "aws"
        assert result["service"] == "iam"
        assert result["region"] == ""
        assert result["account"] == "123456789012"
        assert result["resource"] == "role/MyRole"
        assert "console_url" in result

    def test_lambda_arn_with_region(self) -> None:
        """Should parse Lambda ARN and include region in console URL."""
        result = self._arn("arn:aws:lambda:us-east-1:123456789:function:my-fn")

        assert result["service"] == "lambda"
        assert result["region"] == "us-east-1"
        assert result["resource"] == "function:my-fn"
        assert "us-east-1" in result["console_url"]

    def test_lambda_console_url_strips_type_prefix(self) -> None:
        """Lambda console URL should not include the 'function:' type prefix."""
        result = self._arn("arn:aws:lambda:us-east-1:123456789:function:my-fn")

        assert "/functions/my-fn" in result["console_url"]
        assert "function:my-fn" not in result["console_url"]

    def test_iam_role_console_url_uses_plural_fragment(self) -> None:
        """IAM console URL should use #/roles/... format (plural, leading slash)."""
        result = self._arn("arn:aws:iam::123456789012:role/MyRole")

        assert result["console_url"] == "https://console.aws.amazon.com/iam/home#/roles/MyRole"

    def test_iam_user_console_url(self) -> None:
        """IAM user console URL should use #/users/... format."""
        result = self._arn("arn:aws:iam::123456789012:user/alice")

        assert "#/users/alice" in result["console_url"]

    def test_iam_policy_console_url(self) -> None:
        """IAM policy console URL should use #/policies/... format."""
        result = self._arn("arn:aws:iam::123456789012:policy/MyPolicy")

        assert "#/policies/MyPolicy" in result["console_url"]

    def test_s3_arn(self) -> None:
        """Should parse S3 bucket ARN."""
        result = self._arn("arn:aws:s3:::my-bucket")

        assert result["partition"] == "aws"
        assert result["service"] == "s3"
        assert result["account"] == ""

    def test_govcloud_partition(self) -> None:
        """Should parse ARN with aws-us-gov partition."""
        result = self._arn("arn:aws-us-gov:iam::123456789012:role/AdminRole")

        assert result["partition"] == "aws-us-gov"
        assert result["service"] == "iam"

    def test_invalid_arn_prefix(self) -> None:
        """Should return error for non-ARN strings."""
        result = self._arn("not-an-arn")

        assert "error" in result

    def test_malformed_arn_too_few_parts(self) -> None:
        """Should return error for ARN with fewer than 6 parts."""
        result = self._arn("arn:aws:iam")

        assert "error" in result

    def test_console_url_present(self) -> None:
        """Should always return a console_url key."""
        result = self._arn("arn:aws:ec2:us-west-2:123456789012:instance/i-1234567890abcdef0")
        assert "console_url" in result
        assert result["console_url"].startswith("https://")

    def test_dynamodb_arn(self) -> None:
        """Should parse DynamoDB table ARN."""
        result = self._arn("arn:aws:dynamodb:eu-west-1:123456789012:table/my-table")

        assert result["service"] == "dynamodb"
        assert result["region"] == "eu-west-1"
        assert "dynamodb" in result["console_url"].lower()


# ---------------------------------------------------------------------------
# Task 9.2 — aws.check() SSO cache parsing
# ---------------------------------------------------------------------------


@_skip_boto
@pytest.mark.unit
@pytest.mark.tools
class TestAwsCheck:
    """Unit tests for aws.check() SSO cache parsing."""

    def _check(self, profile: str | None = None, monkeypatch=None) -> dict:
        from otdev.tools.aws_util import check

        return check(profile=profile)

    def test_check_expired_sso_from_cache(self, tmp_path: Path) -> None:
        """Should detect expired SSO token from cache file."""
        from otdev.tools.aws_util import check

        cache_dir = tmp_path / ".aws" / "sso" / "cache"
        cache_dir.mkdir(parents=True)

        expired = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        cache_file = cache_dir / "token.json"
        cache_file.write_text(json.dumps({
            "startUrl": "https://example.awsapps.com/start",
            "accessToken": "fake-token",
            "expiresAt": expired.strftime("%Y-%m-%dT%H:%M:%SUTC"),
        }))

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = check(profile="test-sso")

        assert result["status"] == "expired"
        assert "login" in result["fix"]

    def test_check_valid_sso_cache_falls_through_to_sts(self, tmp_path: Path) -> None:
        """Should not flag unexpired SSO cache as expired."""
        from otdev.tools.aws_util import check

        cache_dir = tmp_path / ".aws" / "sso" / "cache"
        cache_dir.mkdir(parents=True)

        future = datetime.now(tz=timezone.utc) + timedelta(hours=8)
        cache_file = cache_dir / "token.json"
        cache_file.write_text(json.dumps({
            "startUrl": "https://example.awsapps.com/start",
            "accessToken": "fake-token",
            "expiresAt": future.strftime("%Y-%m-%dT%H:%M:%SUTC"),
        }))

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test",
            "UserId": "AIDATEST",
        }

        mock_session = MagicMock()
        mock_session.client.return_value = mock_sts
        mock_session.region_name = "us-east-1"

        with patch("pathlib.Path.home", return_value=tmp_path), \
             patch("boto3.Session", return_value=mock_session):
            result = check(profile="test-sso")

        assert result["status"] == "ok"
        assert result["account"] == "123456789012"

    def test_check_no_credentials(self, tmp_path: Path) -> None:
        """Should return no_credentials when no credentials configured."""
        from botocore.exceptions import NoCredentialsError

        from otdev.tools.aws_util import check

        cache_dir = tmp_path / ".aws" / "sso" / "cache"
        cache_dir.mkdir(parents=True)

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = NoCredentialsError()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_sts
        mock_session.region_name = None

        with patch("pathlib.Path.home", return_value=tmp_path), \
             patch("boto3.Session", return_value=mock_session):
            result = check()

        assert result["status"] == "no_credentials"
        assert "aws configure" in result["fix"]

    def test_check_profile_not_found(self, tmp_path: Path) -> None:
        """Should return error when profile does not exist."""
        from botocore.exceptions import ProfileNotFound

        from otdev.tools.aws_util import check

        cache_dir = tmp_path / ".aws" / "sso" / "cache"
        cache_dir.mkdir(parents=True)

        mock_session = MagicMock()
        mock_session.client.side_effect = ProfileNotFound(profile="nonexistent")

        with patch("pathlib.Path.home", return_value=tmp_path), \
             patch("boto3.Session", return_value=mock_session):
            result = check(profile="nonexistent")

        assert result["status"] == "error"
        assert "profiles" in result["fix"]

    _EXPECTED_KEYS = {"status", "profile", "account", "arn", "region", "expiry", "fix"}

    def test_check_ok_has_all_keys(self, tmp_path: Path) -> None:
        """ok status should include all standard keys."""
        from otdev.tools.aws_util import check

        cache_dir = tmp_path / ".aws" / "sso" / "cache"
        cache_dir.mkdir(parents=True)

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test",
            "UserId": "AIDATEST",
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_sts
        mock_session.region_name = "us-east-1"

        with patch("pathlib.Path.home", return_value=tmp_path), \
             patch("boto3.Session", return_value=mock_session):
            result = check()

        assert self._EXPECTED_KEYS <= result.keys()

    def test_check_expired_has_all_keys(self, tmp_path: Path) -> None:
        """expired status (SSO cache) should include all standard keys."""
        from otdev.tools.aws_util import check

        cache_dir = tmp_path / ".aws" / "sso" / "cache"
        cache_dir.mkdir(parents=True)

        from datetime import timedelta
        expired = datetime.now(tz=timezone.utc) - timedelta(hours=1)
        (cache_dir / "token.json").write_text(json.dumps({
            "expiresAt": expired.strftime("%Y-%m-%dT%H:%M:%SUTC"),
        }))

        with patch("pathlib.Path.home", return_value=tmp_path):
            result = check(profile="test-sso")

        assert self._EXPECTED_KEYS <= result.keys()

    def test_check_no_credentials_has_all_keys(self, tmp_path: Path) -> None:
        """no_credentials status should include all standard keys."""
        from botocore.exceptions import NoCredentialsError

        from otdev.tools.aws_util import check

        cache_dir = tmp_path / ".aws" / "sso" / "cache"
        cache_dir.mkdir(parents=True)

        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = NoCredentialsError()
        mock_session = MagicMock()
        mock_session.client.return_value = mock_sts
        mock_session.region_name = None

        with patch("pathlib.Path.home", return_value=tmp_path), \
             patch("boto3.Session", return_value=mock_session):
            result = check()

        assert self._EXPECTED_KEYS <= result.keys()

    def test_check_client_error_fix_is_actionable(self, tmp_path: Path) -> None:
        """ClientError fix should be an actionable hint, not a raw boto3 error string."""
        from botocore.exceptions import ClientError

        from otdev.tools.aws_util import check

        cache_dir = tmp_path / ".aws" / "sso" / "cache"
        cache_dir.mkdir(parents=True)

        error_response = {"Error": {"Code": "InvalidClientTokenId", "Message": "bad token"}}
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = ClientError(error_response, "GetCallerIdentity")
        mock_session = MagicMock()
        mock_session.client.return_value = mock_sts
        mock_session.region_name = None

        with patch("pathlib.Path.home", return_value=tmp_path), \
             patch("boto3.Session", return_value=mock_session):
            result = check(profile="myprofile")

        assert result["status"] == "error"
        assert "aws.login" in result["fix"]
        assert "InvalidClientTokenId" not in result["fix"]


# ---------------------------------------------------------------------------
# Task 9.3 — aws.roles() built-in + user role merging
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestAwsRoles:
    """Unit tests for aws.roles() role merging."""

    def test_builtin_roles_count(self) -> None:
        """Should expose exactly 16 built-in roles (healthcare and iot removed)."""
        from otdev.tools.aws_util import _BUILTIN_ROLES

        assert len(_BUILTIN_ROLES) == 16

    def test_builtin_roles_present(self) -> None:
        """Should include key built-in roles."""
        from otdev.tools.aws_util import _BUILTIN_ROLES

        for expected in ("all", "finops", "security", "compute", "database", "ai", "iac"):
            assert expected in _BUILTIN_ROLES, f"Missing built-in role: {expected!r}"

    def test_roles_returns_all_builtin(self) -> None:
        """Should return all built-in roles without user config."""
        from otdev.tools.aws_util import _BUILTIN_ROLES, Config, roles

        mock_cfg = Config()
        with patch("otdev.tools.aws_util._get_config", return_value=mock_cfg):
            result = roles()

        for role_name in _BUILTIN_ROLES:
            assert role_name in result

    def test_builtin_roles_not_tagged_user(self) -> None:
        """Built-in roles should have user=False."""
        from otdev.tools.aws_util import Config, roles

        mock_cfg = Config()
        with patch("otdev.tools.aws_util._get_config", return_value=mock_cfg):
            result = roles()

        for role_name, info in result.items():
            assert info["user"] is False, f"{role_name} should not be tagged user"

    def test_user_roles_merged_and_tagged(self) -> None:
        """User-defined roles should appear and be tagged with user=True."""
        from otdev.tools.aws_util import Config, roles

        mock_cfg = Config(roles={"myteam": ["ecs", "dynamodb"]})
        with patch("otdev.tools.aws_util._get_config", return_value=mock_cfg):
            result = roles()

        assert "myteam" in result
        assert result["myteam"]["user"] is True
        assert "ecs" in result["myteam"]["servers"]
        assert "dynamodb" in result["myteam"]["servers"]

    def test_user_role_overrides_builtin(self) -> None:
        """User-defined role should override built-in role with same name."""
        from otdev.tools.aws_util import Config, roles

        custom_finops = ["cost"]  # smaller than built-in
        mock_cfg = Config(roles={"finops": custom_finops})
        with patch("otdev.tools.aws_util._get_config", return_value=mock_cfg):
            result = roles()

        assert result["finops"]["servers"] == sorted(custom_finops)
        assert result["finops"]["user"] is True

    def test_all_role_contains_all_servers(self) -> None:
        """The 'all' role should contain all servers in the registry."""
        from otdev.tools.aws_util import Config, _SERVER_REGISTRY, roles

        mock_cfg = Config()
        with patch("otdev.tools.aws_util._get_config", return_value=mock_cfg):
            result = roles()

        all_servers = set(result["all"]["servers"])
        registry_servers = set(_SERVER_REGISTRY.keys())
        assert all_servers == registry_servers


# ---------------------------------------------------------------------------
# Task 9.4 — Integration smoke test: module import + __all__ completeness
# ---------------------------------------------------------------------------


@pytest.mark.smoke
@pytest.mark.tools
class TestAwsUtilModuleSmoke:
    """Smoke tests for aws_util module structure."""

    def test_pack_name(self) -> None:
        """Module pack attribute should be 'aws'."""
        from otdev.tools import aws_util

        assert aws_util.pack == "aws"

    def test_all_defined(self) -> None:
        """Module should define __all__."""
        from otdev.tools import aws_util

        assert hasattr(aws_util, "__all__")
        assert len(aws_util.__all__) > 0

    def test_all_completeness(self) -> None:
        """__all__ should include all expected public functions."""
        from otdev.tools import aws_util

        expected = {
            "arn", "attributes", "check", "stop_packs", "start_packs",
            "login", "mfa", "packs", "profile", "profiles", "regions",
            "roles", "services", "use", "values", "whoami",
        }
        missing = expected - set(aws_util.__all__)
        assert not missing, f"Missing from __all__: {missing}"

    def test_all_exports_are_callable(self) -> None:
        """All functions in __all__ should be callable."""
        from otdev.tools import aws_util

        for name in aws_util.__all__:
            assert callable(getattr(aws_util, name)), f"{name} should be callable"

    def test_server_registry_count(self) -> None:
        """_SERVER_REGISTRY should contain exactly 57 servers (after curation)."""
        from otdev.tools.aws_util import _SERVER_REGISTRY

        assert len(_SERVER_REGISTRY) == 57, f"Expected 57 servers, got {len(_SERVER_REGISTRY)}"

    def test_server_registry_has_http_knowledge(self) -> None:
        """aws-knowledge should be type http in the registry."""
        from otdev.tools.aws_util import _SERVER_REGISTRY

        assert "know" in _SERVER_REGISTRY
        assert _SERVER_REGISTRY["know"]["type"] == "http"

    def test_server_registry_stdio_entries_have_package(self) -> None:
        """All stdio entries should have a 'package' field."""
        from otdev.tools.aws_util import _SERVER_REGISTRY

        for short, entry in _SERVER_REGISTRY.items():
            if entry["type"] == "stdio":
                assert "package" in entry, f"stdio entry {short!r} missing 'package'"
                assert entry["package"].startswith("awslabs."), (
                    f"stdio entry {short!r} package should start with 'awslabs.'"
                )

    def test_make_server_config_stdio(self) -> None:
        """_make_server_config should return valid stdio McpServerConfig."""
        from ot.config.models import McpServerConfig

        from otdev.tools.aws_util import _make_server_config

        cfg = _make_server_config("iam")
        assert isinstance(cfg, McpServerConfig)
        assert cfg.type == "stdio"
        assert cfg.command == "uvx"
        assert cfg.enabled is True
        assert cfg.inherit_env is True

    def test_make_server_config_http(self) -> None:
        """_make_server_config should return valid http McpServerConfig."""
        from ot.config.models import McpServerConfig

        from otdev.tools.aws_util import _make_server_config

        cfg = _make_server_config("know")
        assert isinstance(cfg, McpServerConfig)
        assert cfg.type == "http"
        assert cfg.url is not None
        assert cfg.url.startswith("https://")

    def test_make_server_config_unknown_raises(self) -> None:
        """_make_server_config should raise ValueError for unknown short names."""
        from otdev.tools.aws_util import _make_server_config

        with pytest.raises(ValueError, match="Unknown server"):
            _make_server_config("nonexistent-server-xyz")

    def test_resolve_targets_unknown_server_no_name_dump(self) -> None:
        """Unknown server error should not dump all server names."""
        from otdev.tools.aws_util import _resolve_targets

        _, _eph, error = _resolve_targets(None, pack="nonexistent")

        assert "nonexistent" in error
        assert "aws.roles()" in error
        # Should NOT enumerate server names
        assert "," not in error

    def test_ot_requires_declared(self) -> None:
        """Module should declare __ot_requires__ with boto3."""
        from otdev.tools import aws_util

        assert hasattr(aws_util, "__ot_requires__")
        reqs = aws_util.__ot_requires__
        assert "lib" in reqs
        lib_reqs = [r[0] if isinstance(r, (list, tuple)) else r for r in reqs["lib"]]
        assert "boto3" in lib_reqs


# ---------------------------------------------------------------------------
# Task 9.5 — aws.regions() fallback warning
# ---------------------------------------------------------------------------


@_skip_boto
@pytest.mark.unit
@pytest.mark.tools
class TestAwsRegions:
    """Unit tests for aws.regions() fallback behaviour."""

    def test_regions_fallback_on_unsupported_service(self) -> None:
        """Should fall back to EC2 regions when get_available_regions raises."""
        from unittest.mock import MagicMock, patch

        from otdev.tools.aws_util import regions

        mock_session = MagicMock()
        mock_session.get_available_regions.side_effect = Exception("unsupported service")

        # Patch EC2 fallback so it returns a known list without hitting AWS
        ec2_regions = ["us-east-1", "us-west-2"]
        with patch("otdev.tools.aws_util._boto3_session", return_value=mock_session), \
             patch("otdev.tools.aws_util.regions", wraps=regions) as _wrapped:
            # We call with a fake service that raises, then it recursively calls regions("ec2")
            # Patch the ec2 branch so it doesn't hit real AWS
            mock_ec2_client = MagicMock()
            mock_ec2_client.describe_regions.return_value = {
                "Regions": [{"RegionName": r} for r in ec2_regions]
            }
            mock_session.client.return_value = mock_ec2_client

            result = regions(service="fakesvc")

        assert sorted(result) == sorted(ec2_regions)

    def test_regions_ec2_returns_list(self) -> None:
        """EC2 branch should return a sorted list of region names."""
        from unittest.mock import MagicMock, patch

        from otdev.tools.aws_util import regions

        mock_ec2 = MagicMock()
        mock_ec2.describe_regions.return_value = {
            "Regions": [
                {"RegionName": "us-west-2"},
                {"RegionName": "us-east-1"},
                {"RegionName": "eu-west-1"},
            ]
        }
        mock_session = MagicMock()
        mock_session.client.return_value = mock_ec2

        with patch("otdev.tools.aws_util._boto3_session", return_value=mock_session):
            result = regions(service="ec2")

        assert result == ["eu-west-1", "us-east-1", "us-west-2"]


# ---------------------------------------------------------------------------
# Issue fixes: pricing env, zero-tools hints
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestMakeServerConfigPricingRegion:
    """_make_server_config for 'pricing' should pin AWS_DEFAULT_REGION=us-east-1."""

    def test_pricing_injects_us_east_1(self) -> None:
        """pricing server config should include AWS_DEFAULT_REGION=us-east-1."""
        from otdev.tools.aws_util import _make_server_config

        cfg = _make_server_config("pricing")

        assert cfg.env.get("AWS_DEFAULT_REGION") == "us-east-1"

    def test_other_servers_no_forced_region(self) -> None:
        """Non-pricing stdio servers should not have a forced AWS_DEFAULT_REGION."""
        from otdev.tools.aws_util import _make_server_config

        for server in ("iam", "cloudtrail", "cost"):
            cfg = _make_server_config(server)
            assert "AWS_DEFAULT_REGION" not in cfg.env, (
                f"{server!r} should not have forced AWS_DEFAULT_REGION"
            )


@pytest.mark.unit
@pytest.mark.tools
class TestStartPacksZeroToolsHint:
    """start_packs should append a usage hint for dynamic-tool servers with 0 tools."""

    def _run_start_packs(self, server_statuses: dict[str, str]) -> dict:
        """Run start_packs with mocked proxy returning given statuses."""
        from otdev.tools.aws_util import Config, start_packs

        mock_proxy = MagicMock()
        mock_proxy.connect_additional_sync.side_effect = lambda name, cfg: server_statuses.get(
            name, "ok (3 tools)"
        )

        mock_cred = {"status": "ok", "account": "123", "arn": "arn:aws:iam::123:user/test"}

        with (
            patch("otdev.tools.aws_util._get_config", return_value=Config()),
            patch("ot.proxy.manager.get_proxy_manager", return_value=mock_proxy),
            patch("otdev.tools.aws_util.check", return_value=mock_cred),
        ):
            return start_packs(role="compute")

    def test_lambda_zero_tools_appends_hint(self) -> None:
        """lambda with 0 tools should include a hint about FUNCTION_PREFIX."""
        result = self._run_start_packs({"aws-lambda": "ok (0 tools)"})

        assert "lambda" in result
        assert result["lambda"].startswith("ok (0 tools)")
        assert "FUNCTION_PREFIX" in result["lambda"] or "FUNCTION_LIST" in result["lambda"]

    def test_stepfunctions_zero_tools_appends_hint(self) -> None:
        """sfn with 0 tools should include a hint about STATE_MACHINE env vars."""
        result = self._run_start_packs({"aws-sfn": "ok (0 tools)"})

        assert "sfn" in result
        assert result["sfn"].startswith("ok (0 tools)")
        assert "STATE_MACHINE" in result["sfn"]

    def test_nonzero_tools_no_hint(self) -> None:
        """lambda with tools should not have a hint appended."""
        result = self._run_start_packs({"aws-lambda": "ok (5 tools)"})

        assert result["lambda"] == "ok (5 tools)"

    def test_non_dynamic_server_zero_tools_no_hint(self) -> None:
        """Other servers with 0 tools should not get a hint."""
        result = self._run_start_packs({"aws-ecs": "ok (0 tools)"})

        # ecs is in compute role but not in _DYNAMIC_TOOL_HINTS
        assert result.get("ecs") == "ok (0 tools)"


# ---------------------------------------------------------------------------
# ServerDef and _resolve_doc_url
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestResolveDocUrl:
    """Unit tests for ServerDef and _resolve_doc_url."""

    def setup_method(self) -> None:
        from otdev.tools.aws_util import ServerDef, _DOC_BASE, _resolve_doc_url

        self.ServerDef = ServerDef
        self.DOC_BASE = _DOC_BASE
        self.resolve = _resolve_doc_url

    def test_awslabs_package_derives_slug(self) -> None:
        """awslabs.* package should derive doc URL from slug."""
        defn = self.ServerDef("awslabs.iam-mcp-server")
        assert self.resolve(defn) == f"{self.DOC_BASE}iam-mcp-server"

    def test_explicit_doc_override(self) -> None:
        """Explicit doc URL should override derivation."""
        defn = self.ServerDef(
            "https://knowledge-mcp.global.api.aws",
            doc=f"{self.DOC_BASE}aws-knowledge-mcp-server",
        )
        assert self.resolve(defn) == f"{self.DOC_BASE}aws-knowledge-mcp-server"

    def test_empty_doc_returns_none(self) -> None:
        """doc='' sentinel should return None (no docs page)."""
        defn = self.ServerDef("awslabs.mcp-lambda-handler", doc="")
        assert self.resolve(defn) is None

    def test_http_server_no_doc_returns_none(self) -> None:
        """HTTP server with no doc override should return None."""
        defn = self.ServerDef("https://example.amazonaws.com/mcp")
        assert self.resolve(defn) is None

    def test_registry_includes_doc_for_stdio_servers(self) -> None:
        """Expanded registry should include doc for standard awslabs servers."""
        from otdev.tools.aws_util import _SERVER_REGISTRY

        assert "doc" in _SERVER_REGISTRY["iam"]
        assert _SERVER_REGISTRY["iam"]["doc"] == f"{self.DOC_BASE}iam-mcp-server"

    def test_registry_know_has_explicit_doc(self) -> None:
        """know (HTTP server) should have explicit doc URL in registry."""
        from otdev.tools.aws_util import _SERVER_REGISTRY

        assert "doc" in _SERVER_REGISTRY["know"]
        assert _SERVER_REGISTRY["know"]["doc"] == f"{self.DOC_BASE}aws-knowledge-mcp-server"

    def test_registry_lambda_handler_has_no_doc(self) -> None:
        """lambda-handler has no docs page; should not have doc key in registry."""
        from otdev.tools.aws_util import _SERVER_REGISTRY

        assert "doc" not in _SERVER_REGISTRY["lambda-handler"]

    def test_core_servers_have_core_flag(self) -> None:
        """Core servers should have core='true' in the registry entry."""
        from otdev.tools.aws_util import _SERVER_REGISTRY

        for expected_core in ("api", "core", "know", "iam", "cloudtrail"):
            assert _SERVER_REGISTRY[expected_core].get("core") == "true", (
                f"{expected_core!r} should be flagged core"
            )

    def test_non_core_servers_lack_core_flag(self) -> None:
        """Non-core servers should not have a core key in the registry entry."""
        from otdev.tools.aws_util import _SERVER_REGISTRY

        for non_core in ("cost", "billing", "ecs", "sagemaker"):
            assert "core" not in _SERVER_REGISTRY[non_core], (
                f"{non_core!r} should not be flagged core"
            )

    def test_removed_servers_absent(self) -> None:
        """Removed servers should not appear in the registry."""
        from otdev.tools.aws_util import _SERVER_REGISTRY

        removed = ("frontend", "codedoc", "finch", "ccapi", "sitewise",
                   "omics", "imaging", "healthlake", "aurora-dsql",
                   "keyspaces", "timestream", "qindex", "wa")
        for name in removed:
            assert name not in _SERVER_REGISTRY, f"{name!r} should have been removed"

    def test_well_arch_renamed(self) -> None:
        """well-arch should exist in registry (renamed from wa)."""
        from otdev.tools.aws_util import _SERVER_REGISTRY

        assert "well-arch" in _SERVER_REGISTRY
        assert "awslabs.well-architected-security-mcp-server" in (
            _SERVER_REGISTRY["well-arch"].get("package", "")
        )


# ---------------------------------------------------------------------------
# Escape hatch: raw package names in _resolve_targets and _make_server_config
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.tools
class TestEscapeHatch:
    """Tests for starting unregistered packs by raw package name."""

    def test_resolve_targets_raw_awslabs_package(self) -> None:
        """Raw awslabs package name should derive short name and populate ephemeral."""
        from otdev.tools.aws_util import _resolve_targets

        targets, ephemeral, err = _resolve_targets(None, pack="awslabs.frontend-mcp-server")

        assert err == ""
        assert "frontend" in targets
        assert ephemeral.get("frontend") == "awslabs.frontend-mcp-server"

    def test_resolve_targets_raw_https_url(self) -> None:
        """HTTPS URL should be treated as raw HTTP server."""
        from otdev.tools.aws_util import _resolve_targets

        targets, ephemeral, err = _resolve_targets(None, pack="https://example.amazonaws.com/mcp")

        assert err == ""
        assert len(targets) == 1
        short = next(iter(targets))
        assert ephemeral.get(short) == "https://example.amazonaws.com/mcp"

    def test_resolve_targets_registered_pack_no_ephemeral(self) -> None:
        """A registered pack should not appear in ephemeral."""
        from otdev.tools.aws_util import _resolve_targets

        targets, ephemeral, err = _resolve_targets(None, pack="iam")

        assert err == ""
        assert "iam" in targets
        assert "iam" not in ephemeral

    def test_make_server_config_package_override_stdio(self) -> None:
        """package_override for unregistered stdio package builds valid McpServerConfig."""
        from ot.config.models import McpServerConfig

        from otdev.tools.aws_util import _make_server_config

        cfg = _make_server_config("frontend", package_override="awslabs.frontend-mcp-server")
        assert isinstance(cfg, McpServerConfig)
        assert cfg.type == "stdio"
        assert cfg.command == "uvx"
        assert "awslabs.frontend-mcp-server" in cfg.args

    def test_make_server_config_package_override_http(self) -> None:
        """package_override with https:// builds an HTTP McpServerConfig."""
        from ot.config.models import McpServerConfig

        from otdev.tools.aws_util import _make_server_config

        url = "https://example.amazonaws.com/mcp"
        cfg = _make_server_config("example", package_override=url)
        assert isinstance(cfg, McpServerConfig)
        assert cfg.type == "http"
        assert cfg.url == url

    def test_make_server_config_no_override_unknown_raises(self) -> None:
        """Without package_override, unknown short name still raises ValueError."""
        from otdev.tools.aws_util import _make_server_config

        with pytest.raises(ValueError, match="Unknown server"):
            _make_server_config("nonexistent-xyz")
