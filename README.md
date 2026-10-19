# Rezer

A lightweight native Windows web browser. Built on **pywebview (WebView2)** — it uses
the Edge engine already on your PC, so there's no bundled Chromium and it stays
light on older machines.

## Features

- Tabs on top, address bar with Google search, bookmark bar (on by default)
- New-tab page: search + top sites + pinnable bookmarks
- **Luna** — built-in AI sidebar (purple moon button, top right). Answers questions,
  summarizes the current page, explains selected text. No keyboard shortcut; click to slide out.
- Built-in ad blocker (blocks common ad/tracker domains in-page)
- History kept 7 days, auto-wiped every Sunday
- Private windows (no history/password/download recording)
- Downloads go straight to your Downloads folder
- Restores your last tabs on startup
- Built-in password manager (Fernet-encrypted, key protected by Windows DPAPI)
- Screenshot button (saves to Pictures/Rezer)
- White theme by default; pick any color with the color wheel in Settings
- Auto-updates from GitHub releases

## Project layout

```
rezer.py                 # entry point
rezer/
  app.py                 # windows, chrome injection, lifecycle
  api.py                 # JS bridge (chrome <-> Python)
  tabs.py                # per-window tab model
  settings.py            # JSON settings
  history.py             # SQLite history (7-day, Sunday wipe)
  bookmarks.py           # JSON bookmarks + pinning
  passwords.py           # encrypted password manager
  dpapi.py               # Windows DPAPI key protection
  adblock.py             # domain list + in-page blocking JS
  luna.py                # Luna AI via Pollinations (free, no key)
  updater.py             # auto-update from GitHub releases
  screenshot.py          # window capture via mss
  paths.py               # resource + data dirs
ui/
  chrome.js / chrome.css # browser chrome injected into every page
  newtab.html            # new-tab page
  settings.html          # settings page (color wheel, toggles)
  history.html           # history viewer
assets/
  logo.png / logo.ico    # pixelated blue R
  luna.png               # purple crescent moon
build.py                 # PyInstaller single-exe build (run on Windows)
.github/workflows/build.yml  # GitHub Actions: builds Rezer.exe on Windows
```

User data lives in `%APPDATA%/Rezer` (settings, history.db, bookmarks, encrypted passwords).

## Run from source (Windows)

```bat
pip install -r requirements.txt
python rezer.py
```

Requires Windows 10/11 with WebView2 (preinstalled on most systems).

## Build the exe

**On Windows:**
```bat
pip install -r requirements.txt pyinstaller
python build.py
```
Output: `dist/Rezer.exe` — a single file, no installer needed. Copy it anywhere and run.

**Via GitHub Actions:** push to `main` (or push a `v*` tag for a release) and the
workflow builds `Rezer.exe` on a Windows runner and uploads it as an artifact
(a release asset for tags). The in-app updater checks those releases.

## If Windows Defender removes Rezer.exe

PyInstaller-built apps sometimes get flagged as malware by Windows Defender
(a common false positive — the exe is just a bundled Python app, not a virus).
If Rezer.exe disappears right after downloading or launching:

1. Open **Windows Security** → **Virus & threat protection** → **Protection history**
2. Find the Rezer entry → **Actions** → **Restore**
3. Add an exclusion so it doesn't happen again: **Virus & threat protection** →
   **Manage settings** → **Exclusions** → **Add or remove exclusions** →
   **Add an exclusion** → **File** → select `Rezer.exe`

The build now ships with `--noupx` and full Windows version metadata, which
reduces (but can't fully eliminate) false-positive detections.

## Troubleshooting

- **Rezer won't start / shows an error:** details go to `%APPDATA%\Rezer\crash.log`.
- **UI looks broken or half-loaded:** injection errors go to
  `%APPDATA%\Rezer\debug.log` — include it when reporting the bug.
- **WebView2 missing:** Rezer needs the Microsoft Edge WebView2 Runtime
  (preinstalled on Windows 10/11). Get it from Microsoft's site if pages won't load.

## Honest limitations (v1)

- **Ad blocking** is in-page (fetch/XHR patching + element hiding), not network-level —
  pywebview doesn't expose WebView2's request interception.
- **Private windows** skip history/password/download recording in Rezer's own code, but
  share the WebView2 profile, so cookies may persist. Full isolation needs a separate
  user-data folder (future work).
- **Downloads** use WebView2's native handling (dialog defaults to Downloads).
- **Luna** needs internet (Pollinations API) and sends the current page text for
  summaries — same tradeoff as Edge/Chrome AI features.
- Tabs are virtual (one webview per window); switching tabs reloads the page.
