"""Filesystem paths: bundled resources and the per-user data directory."""

import os
import sys


def resource_path(relative: str) -> str:
    """Path to a bundled resource. Works both from source and a PyInstaller exe."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = sys._MEIPASS  # type: ignore[attr-defined]
    else:
        # <project>/rezer/paths.py -> <project>
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative)


def data_dir() -> str:
    """Per-user data directory: %APPDATA%/Rezer (falls back to ~/.rezer)."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        d = os.path.join(appdata, "Rezer")
    else:
        d = os.path.join(os.path.expanduser("~"), ".rezer")
    os.makedirs(d, exist_ok=True)
    return d


def downloads_dir() -> str:
    """User's Downloads folder (spec: downloads go straight here, no prompt)."""
    home = os.path.expanduser("~")
    dl = os.path.join(home, "Downloads")
    os.makedirs(dl, exist_ok=True)
    return dl
