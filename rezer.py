#!/usr/bin/env python3
"""Rezer — a lightweight native Windows web browser.

Built on pywebview (WebView2), so it's light on old PCs: no bundled Chromium.
Run:  python rezer.py
"""

import sys


def main():
    from rezer.app import RezerApp
    app = RezerApp()
    app.run()


if __name__ == "__main__":
    sys.exit(main())
