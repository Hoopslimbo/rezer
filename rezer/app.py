"""Rezer application: windows, chrome injection, lifecycle."""

import json
import os
import time
import traceback

import webview

from . import adblock as adblock_mod
from . import updater
from .api import Api
from .bookmarks import BookmarkManager
from .history import HistoryManager
from .passwords import PasswordManager
from .paths import data_dir, resource_path
from .settings import SettingsManager
from .tabs import TabManager

CHROME_CSS_PATH = resource_path(os.path.join("ui", "chrome.css"))
CHROME_JS_PATH = resource_path(os.path.join("ui", "chrome.js"))
NEWTAB_PATH = resource_path(os.path.join("ui", "newtab.html"))
SETTINGS_PATH = resource_path(os.path.join("ui", "settings.html"))
HISTORY_PATH = resource_path(os.path.join("ui", "history.html"))

NEWTAB_URL = "rezer://newtab"
SETTINGS_URL = "rezer://settings"
HISTORY_URL = "rezer://history"


def _file_url(path: str) -> str:
    import pathlib
    return pathlib.Path(path).as_uri()


# rezer://... -> file:///...  (and the reverse, for normalizing location.href)
SCHEME_MAP = {}
REVERSE_SCHEME_MAP = {}


def _init_scheme():
    SCHEME_MAP[NEWTAB_URL] = _file_url(NEWTAB_PATH)
    SCHEME_MAP[SETTINGS_URL] = _file_url(SETTINGS_PATH)
    SCHEME_MAP[HISTORY_URL] = _file_url(HISTORY_PATH)
    for k, v in SCHEME_MAP.items():
        REVERSE_SCHEME_MAP[v] = k
        # file urls may differ in case/encoding; also map the plain path
        REVERSE_SCHEME_MAP[v.lower()] = k


def normalize_url(url: str) -> str:
    """Map a loaded file:// local page back to its rezer:// alias."""
    if not url:
        return url
    if url in REVERSE_SCHEME_MAP:
        return REVERSE_SCHEME_MAP[url]
    low = url.lower().split("#")[0].split("?")[0]
    return REVERSE_SCHEME_MAP.get(low, url)


class RezerApp:
    def __init__(self):
        _init_scheme()
        self.settings = SettingsManager()
        self.history = HistoryManager()
        self.bookmarks = BookmarkManager()
        self.passwords = PasswordManager()
        self.windows = []  # list of dicts: {window, tabs, api, private}

        # weekly maintenance
        self.history.prune_week()
        self.history.maybe_sunday_clear(self.settings)

        # Fail loudly (not silently) if bundled resources are missing —
        # a missing ui/ or assets/ in the exe means a broken build.
        for label, path in (
            ("chrome CSS", CHROME_CSS_PATH),
            ("chrome JS", CHROME_JS_PATH),
            ("new-tab page", NEWTAB_PATH),
            ("settings page", SETTINGS_PATH),
            ("history page", HISTORY_PATH),
        ):
            if not os.path.isfile(path):
                raise RuntimeError(
                    "Rezer is missing its %s (%s). The install may be corrupt — "
                    "try reinstalling." % (label, path)
                )

        with open(CHROME_CSS_PATH, encoding="utf-8") as f:
            self.chrome_css = f.read()
        with open(CHROME_JS_PATH, encoding="utf-8") as f:
            self.chrome_js = f.read()
        self.adblock_js = adblock_mod.injection_js()

    @staticmethod
    def _log(msg: str):
        """Append to %APPDATA%/Rezer/debug.log — the injection path used to
        fail silently, which made UI bugs impossible to diagnose."""
        try:
            p = os.path.join(data_dir(), "debug.log")
            with open(p, "a", encoding="utf-8") as f:
                f.write(time.strftime("[%Y-%m-%d %H:%M:%S] ") + msg + "\n")
        except OSError:
            pass

    # ---------- window management ----------

    def create_window(self, private: bool = False, start_urls=None):
        title = "Rezer" + (" (Private)" if private else "")
        tabs = TabManager(NEWTAB_URL)
        entry = {"tabs": tabs, "private": private, "window": None, "api": None}

        api = Api({
            "window": lambda: entry["window"],
            "tabs": tabs,
            "settings": self.settings,
            "history": self.history,
            "bookmarks": self.bookmarks,
            "passwords": self.passwords,
            "private": private,
            "newtab_url": NEWTAB_URL,
            "settings_url": SETTINGS_URL,
            "resolve_url": lambda u: SCHEME_MAP.get(u, u),
            "normalize_url": normalize_url,
            "on_navigate": lambda tab, url: self._on_navigate(entry, tab, url),
            "open_private": lambda: self.create_window(private=True),
            "open_window": lambda: self.create_window(private=False),
        })
        entry["api"] = api

        urls = start_urls or [NEWTAB_URL]
        for u in urls:
            tabs.new_tab(u)
        first = SCHEME_MAP.get(urls[0], urls[0])

        w = webview.create_window(
            title, first, js_api=api,
            width=1280, height=800, min_size=(800, 600),
            text_select=True,
        )
        entry["window"] = w
        w.events.loaded += lambda: self._on_loaded(entry)
        w.events.closing += lambda: self._on_closing(entry)
        self.windows.append(entry)
        return entry

    # ---------- navigation / injection ----------

    def _on_navigate(self, entry, tab, url: str):
        # history is recorded in _on_loaded once the page commits
        pass

    def _on_loaded(self, entry):
        w = entry["window"]
        try:
            cur = w.evaluate_js("location.href") or ""
        except Exception:
            cur = ""
        if not cur or cur == "about:blank":
            return
        cur = normalize_url(cur)

        # The JS API bridge (window.pywebview.api) is created by pywebview
        # AFTER the page's load event fires. Injecting the chrome before the
        # bridge exists meant get_state()/etc. silently returned null, so the
        # tab strip, address bar and bookmarks rendered empty ("buggy UI").
        # Wait for the bridge (up to ~6s), then inject.
        if not self._wait_for_bridge(w):
            self._log("bridge timeout on " + cur[:120])

        self._inject(entry)

        tab = entry["tabs"].active()
        if cur != tab.url:
            tab.record_visit(cur)
        # record history for real pages (skip private + local pages)
        if not entry["private"] and not cur.startswith("rezer://") and not cur.startswith("file://"):
            self.history.add(cur, tab.title or cur)

        entry["api"].push_state()
        try:
            title = w.evaluate_js("document.title") or ""
            if title:
                entry["api"].on_title(title)
        except Exception:
            pass

    def _wait_for_bridge(self, w, timeout: float = 6.0) -> bool:
        """Poll until window.pywebview.api exists. Returns False on timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if w.evaluate_js("!!(window.pywebview && window.pywebview.api)"):
                    return True
            except Exception:
                pass
            time.sleep(0.15)
        return False

    def _inject(self, entry):
        w = entry["window"]
        # json.dumps produces a correctly-escaped JS string literal — safer
        # than hand-escaping backslashes/backticks/${ for a template literal.
        css_lit = json.dumps(self.chrome_css)
        payload = (
            "(function(){"
            "if(window.__rezerChrome){return;}"
            "var st=document.createElement('style');st.id='rezer-chrome-css';"
            "st.textContent=" + css_lit + ";"
            "(document.head||document.documentElement).appendChild(st);"
            "})();"
        )
        try:
            w.evaluate_js(payload)
        except Exception:
            self._log("CSS inject failed:\n" + traceback.format_exc())
            return
        try:
            w.evaluate_js(self.chrome_js)
        except Exception:
            self._log("chrome.js inject failed:\n" + traceback.format_exc())
            return
        if self.settings.get("adblock_enabled"):
            try:
                w.evaluate_js(self.adblock_js)
            except Exception:
                self._log("adblock inject failed:\n" + traceback.format_exc())

    def _on_closing(self, entry):
        # persist tabs for restore (non-private only)
        if not entry["private"] and self.settings.get("restore_tabs"):
            urls = entry["tabs"].urls()
            self.settings.set("saved_tabs", urls or [NEWTAB_URL])
        self.windows = [e for e in self.windows if e is not entry]

    # ---------- run ----------

    def run(self):
        saved = self.settings.get("saved_tabs") if self.settings.get("restore_tabs") else []
        start_urls = [u for u in (saved or []) if u] or [NEWTAB_URL]
        self.create_window(private=False, start_urls=start_urls)
        updater.start_background()
        webview.start(debug=False)
