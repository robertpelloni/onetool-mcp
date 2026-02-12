"""Asset loader for bundled scripts."""

from pathlib import Path

_ASSETS_DIR = Path(__file__).parent


def get_inject_script(filename: str = "inject.js") -> str:
    """Load a bundled script asset as a string.

    Args:
        filename: Name of the script file in the assets directory.

    Returns:
        The script contents as a string, suitable for injection via evaluate_script().

    Raises:
        FileNotFoundError: If the asset file does not exist.
    """
    path = _ASSETS_DIR / filename
    return path.read_text(encoding="utf-8")
