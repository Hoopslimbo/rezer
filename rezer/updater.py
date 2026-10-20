"""Auto-update: checks GitHub releases, downloads the new exe, swaps it in.

Spec: auto-check + auto-install. Flow: on startup (and every 15 min) compare the
latest release tag with the bundled version. If newer, download the exe asset
to a temp file, write a small updater .bat that waits for this process to exit,
replaces the exe, and relaunches it — then exit immediately.
"""

import os
import subprocess
import sys
import tempfile
import threading
import time

import requests

from . import __version__

REPO = "Hoopslimbo/rezer"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_INTERVAL = 15 * 60


def _current_exe() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return ""  # dev mode: never self-update


def _version_tuple(v: str):
    return tuple(int(p) for p in v.lstrip("v").split(".") if p.isdigit())


def check_for_update():
    """Returns (tag, asset_url) if a newer release exists, else None."""
    try:
        r = requests.get(API_URL, timeout=15, headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        data = r.json()
        tag = (data.get("tag_name") or "").strip()
        if not tag or _version_tuple(tag) <= _version_tuple(__version__):
            return None
        # Releases also ship Rezer-Setup.exe (the installer). The updater must
        # swap in ONLY the browser executable itself — match the exact name.
        for a in data.get("assets", []):
            if a.get("name", "").lower() == "rezer.exe":
                return tag, a.get("browser_download_url")
        return None
    except requests.RequestException:
        return None


def _write_updater_bat(exe_path: str, new_exe_tmp: str) -> str:
    bat = os.path.join(tempfile.gettempdir(), "rezer_update.bat")
    with open(bat, "w") as f:
        f.write(
            "@echo off\n"
            f':wait\ntasklist /FI "IMAGENAME eq {os.path.basename(exe_path)}" 2>NUL | find /I "{os.path.basename(exe_path)}" >NUL\n'
            "if not errorlevel 1 (timeout /t 1 /nobreak >NUL & goto wait)\n"
            f'move /Y "{new_exe_tmp}" "{exe_path}" >NUL\n'
            f'start "" "{exe_path}"\n'
            "del \"%~f0\"\n"
        )
    return bat


def download_and_install(asset_url: str) -> bool:
    exe_path = _current_exe()
    if not exe_path:
        return False
    try:
        tmp = os.path.join(tempfile.gettempdir(), "Rezer-new.exe")
        with requests.get(asset_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(1024 * 256):
                    f.write(chunk)
        bat = _write_updater_bat(exe_path, tmp)
        subprocess.Popen(["cmd", "/c", bat], shell=False,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (requests.RequestException, OSError):
        return False


def auto_update_loop(stop_event):
    """Background thread: check on start, then every CHECK_INTERVAL."""
    time.sleep(20)  # let the browser settle first
    while not stop_event.is_set():
        try:
            found = check_for_update()
            if found:
                _, asset_url = found
                if download_and_install(asset_url):
                    # updater bat will relaunch us; exit now
                    os._exit(0)
        except Exception:
            # a single bad check must never kill the background thread
            pass
        stop_event.wait(CHECK_INTERVAL)


def start_background():
    if not _current_exe():
        return None
    import threading as _t
    stop = _t.Event()
    t = _t.Thread(target=auto_update_loop, args=(stop,), daemon=True)
    t.start()
    return stop
