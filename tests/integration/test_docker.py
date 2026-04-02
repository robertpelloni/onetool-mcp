"""Integration tests for the OneTool Docker image.

Builds the image once per class (class-scoped fixture) and runs targeted checks.

Run:
  uv run pytest tests/integration/test_docker.py -m "integration and docker" -v
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.docker, pytest.mark.slow, pytest.mark.core]

PROJECT_ROOT = Path(__file__).parent.parent.parent
_IMAGE = "onetool-mcp-test"


@pytest.fixture(scope="class")
def built_image():
    """Build the Docker image once per test class; remove it after."""
    result = subprocess.run(
        ["docker", "build", "-t", _IMAGE, "."],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"docker build failed:\n{result.stderr}"
    yield _IMAGE
    subprocess.run(["docker", "rmi", _IMAGE, "--force"], check=False, capture_output=True)


class TestDockerImage:
    def test_build(self, built_image: str) -> None:
        """Build exits 0 (validated by fixture)."""
        assert built_image == _IMAGE

    def test_version(self, built_image: str) -> None:
        """Entrypoint is functional — onetool --version exits 0."""
        result = subprocess.run(
            ["docker", "run", "--rm", built_image, "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_config_valid(self, built_image: str) -> None:
        """Baked-in config passes init validate."""
        result = subprocess.run(
            [
                "docker", "run", "--rm", built_image,
                "init", "validate", "--config", "/onetool/onetool.yaml",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_config_override(self, built_image: str, tmp_path: Path) -> None:
        """Volume-mounted config override is accepted."""
        config = tmp_path / "onetool.yaml"
        config.write_text("version: 2\ntools_dir: []\n")
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{config}:/onetool/onetool.yaml:ro",
                built_image, "--version",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr

    def test_secrets_flag(self, built_image: str, tmp_path: Path) -> None:
        """--secrets flag is accepted without error."""
        secrets = tmp_path / "secrets.yaml"
        secrets.write_text("# dummy\n")
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{secrets}:/run/secrets/secrets.yaml:ro",
                built_image, "--secrets", "/run/secrets/secrets.yaml", "--version",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
