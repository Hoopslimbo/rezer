#!/usr/bin/env python3
"""Build Rezer into a single-file Windows exe with PyInstaller.

Run ON WINDOWS:  python build.py
Output: dist/Rezer.exe
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)


def main():
    try:
        import PyInstaller.__main__  # noqa
    except ImportError:
        sys.exit("PyInstaller is not installed. Run: pip install pyinstaller")

    sep = ";"  # Windows path separator for --add-data
    args = [
        "rezer.py",
        "--onefile",
        "--windowed",          # no console window
        "--noupx",             # UPX packing triggers Defender heuristics; skip it
        "--name", "Rezer",
        "--icon", os.path.join("assets", "logo.ico"),
        "--version-file", os.path.join(HERE, "version_info.txt"),
        "--add-data", f"ui{sep}ui",
        "--add-data", f"assets{sep}assets",
        # keep these out of the bundle scan noise but ensure they're included
        "--hidden-import", "cryptography",
        "--hidden-import", "mss",
        "--hidden-import", "requests",
        "--hidden-import", "webview",
        "--clean",
        "--noconfirm",
    ]
    import PyInstaller.__main__
    PyInstaller.__main__.run(args)
    print("\nBuilt:", os.path.join(HERE, "dist", "Rezer.exe"))


if __name__ == "__main__":
    main()
