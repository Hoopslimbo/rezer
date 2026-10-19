#!/usr/bin/env python3
"""Rezer — a lightweight native Windows web browser.

Built on pywebview (WebView2), so it's light on old PCs: no bundled Chromium.
Run:  python rezer.py
"""

import os
import sys
import traceback


def _crash_log_path() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "Rezer")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        d = os.path.expanduser("~")
    return os.path.join(d, "crash.log")


def _show_fatal(message: str):
    """Last-resort error dialog (the exe runs --windowed, so no console)."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                message + "\n\nDetails were written to:\n" + _crash_log_path(),
                "Rezer couldn't start",
                0x10,  # MB_ICONERROR
            )
            return
        except Exception:
            pass
    sys.stderr.write(message + "\n")


def main():
    try:
        from rezer.app import RezerApp
    except Exception:
        with open(_crash_log_path(), "a", encoding="utf-8") as f:
            f.write("=== import crash ===\n" + traceback.format_exc() + "\n")
        _show_fatal(
            "Rezer failed to start (a required component didn't load).\n"
            "Make sure Microsoft Edge WebView2 Runtime is installed."
        )
        return 1
    try:
        app = RezerApp()
        app.run()
    except Exception:
        with open(_crash_log_path(), "a", encoding="utf-8") as f:
            f.write("=== runtime crash ===\n" + traceback.format_exc() + "\n")
        _show_fatal("Rezer ran into a problem and had to close.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
