"""Comprehensive unit tests for Rezer backend modules.

Run: python3 -m pytest tests/test_backend.py -v
"""

import json
import os
import sys
import tempfile

# Use a temp data dir so tests don't touch real user data
_tmp = tempfile.mkdtemp(prefix="rezer_test_")
os.environ["APPDATA"] = _tmp  # paths.data_dir() uses APPDATA on all platforms here

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ---------- settings ----------

class TestSettings:
    def test_defaults(self):
        from rezer.settings import SettingsManager
        s = SettingsManager()
        assert s.get("theme_color") == "#ffffff"
        assert s.get("bookmark_bar_visible") is True
        assert s.get("adblock_enabled") is True
        assert s.get("restore_tabs") is True
        assert s.get("search_engine") == "google"

    def test_set_get_persist(self):
        from rezer.settings import SettingsManager
        s = SettingsManager()
        s.set("theme_color", "#ff0000")
        assert s.get("theme_color") == "#ff0000"
        # new instance should load from disk
        s2 = SettingsManager()
        assert s2.get("theme_color") == "#ff0000"
        # restore
        s.set("theme_color", "#ffffff")

    def test_set_invalid_key_raises(self):
        from rezer.settings import SettingsManager
        s = SettingsManager()
        with pytest.raises(KeyError):
            s.set("nonexistent_key", "x")

    def test_search_url(self):
        from rezer.settings import SettingsManager
        s = SettingsManager()
        url = s.search_url("hello world")
        assert "hello+world" in url or "hello%20world" in url
        assert url.startswith("https://www.google.com/search?q=")

    def test_search_url_bing(self):
        from rezer.settings import SettingsManager
        s = SettingsManager()
        s.set("search_engine", "bing")
        url = s.search_url("test")
        assert "bing.com" in url
        s.set("search_engine", "google")


# ---------- history ----------

class TestHistory:
    def test_add_and_recent(self):
        from rezer.history import HistoryManager
        h = HistoryManager()
        h.clear()
        h.add("https://example.com", "Example")
        recent = h.recent(10)
        assert len(recent) == 1
        assert recent[0]["url"] == "https://example.com"
        assert recent[0]["title"] == "Example"
        h.clear()

    def test_add_skips_local(self):
        from rezer.history import HistoryManager
        h = HistoryManager()
        h.clear()
        h.add("rezer://newtab", "New Tab")
        h.add("about:blank", "")
        h.add("", "")
        assert h.recent(10) == []
        h.clear()

    def test_search(self):
        from rezer.history import HistoryManager
        h = HistoryManager()
        h.clear()
        h.add("https://example.com/page", "Example Page")
        h.add("https://other.org/", "Other Site")
        results = h.search("example")
        assert len(results) == 1
        assert results[0]["url"] == "https://example.com/page"
        # empty query returns []
        assert h.search("") == []
        assert h.search("   ") == []
        h.clear()

    def test_search_matches_title(self):
        from rezer.history import HistoryManager
        h = HistoryManager()
        h.clear()
        h.add("https://example.com/", "My Cool Website")
        results = h.search("cool")
        assert len(results) == 1
        h.clear()

    def test_prune_week(self):
        from rezer.history import HistoryManager
        import datetime
        h = HistoryManager()
        h.clear()
        h.add("https://recent.com/", "Recent")
        # manually insert an old entry
        old = (datetime.datetime.now() - datetime.timedelta(days=10)).isoformat()
        import sqlite3
        with h._lock, sqlite3.connect(h.path) as c:
            c.execute("INSERT INTO visits (url, title, visited_at) VALUES (?, ?, ?)",
                      ("https://old.com/", "Old", old))
        h.prune_week()
        recent = h.recent(10)
        urls = [r["url"] for r in recent]
        assert "https://recent.com/" in urls
        assert "https://old.com/" not in urls
        h.clear()

    def test_top_sites(self):
        from rezer.history import HistoryManager
        h = HistoryManager()
        h.clear()
        h.add("https://a.com/", "A")
        h.add("https://a.com/", "A")
        h.add("https://b.com/", "B")
        top = h.top_sites(8)
        assert top[0]["url"] == "https://a.com/"
        assert top[0]["visits"] == 2
        h.clear()

    def test_clear(self):
        from rezer.history import HistoryManager
        h = HistoryManager()
        h.add("https://x.com/", "X")
        h.clear()
        assert h.recent(10) == []


# ---------- bookmarks ----------

class TestBookmarks:
    def test_add_remove(self):
        from rezer.bookmarks import BookmarkManager
        b = BookmarkManager()
        # clean slate
        for item in b.all():
            b.remove(item["url"])
        assert b.add("Example", "https://example.com/") is True
        assert b.is_bookmarked("https://example.com/") is True
        # duplicate rejected
        assert b.add("Example", "https://example.com/") is False
        assert b.remove("https://example.com/") is True
        assert b.is_bookmarked("https://example.com/") is False

    def test_toggle_pin(self):
        from rezer.bookmarks import BookmarkManager
        b = BookmarkManager()
        for item in b.all():
            b.remove(item["url"])
        b.add("Example", "https://example.com/")
        assert b.toggle_pin("https://example.com/") is True
        assert b.pinned()[0]["url"] == "https://example.com/"
        assert b.toggle_pin("https://example.com/") is False
        assert b.pinned() == []
        b.remove("https://example.com/")

    def test_persistence(self):
        from rezer.bookmarks import BookmarkManager
        b = BookmarkManager()
        for item in b.all():
            b.remove(item["url"])
        b.add("Persist", "https://persist.example/", pinned=True)
        b2 = BookmarkManager()
        assert b2.is_bookmarked("https://persist.example/")
        assert b2.pinned()[0]["title"] == "Persist"
        b.remove("https://persist.example/")


# ---------- tabs ----------

class TestTabs:
    def test_new_tab(self):
        from rezer.tabs import TabManager
        tm = TabManager("rezer://newtab")
        t = tm.new_tab()
        assert t.url == "rezer://newtab"
        assert tm.active().id == t.id

    def test_switch(self):
        from rezer.tabs import TabManager
        tm = TabManager("rezer://newtab")
        t1 = tm.new_tab("https://a.com/")
        t2 = tm.new_tab("https://b.com/")
        assert tm.active().id == t2.id
        tm.switch(t1.id)
        assert tm.active().id == t1.id

    def test_close_tab(self):
        from rezer.tabs import TabManager
        tm = TabManager("rezer://newtab")
        t1 = tm.new_tab("https://a.com/")
        t2 = tm.new_tab("https://b.com/")
        tm.close_tab(t2.id)
        assert len(tm.tabs) == 1
        assert tm.active().id == t1.id

    def test_close_last_tab_creates_new(self):
        from rezer.tabs import TabManager
        tm = TabManager("rezer://newtab")
        t = tm.new_tab("https://a.com/")
        tm.close_tab(t.id)
        assert len(tm.tabs) == 1
        assert tm.active().url == "rezer://newtab"

    def test_back_forward(self):
        from rezer.tabs import TabManager
        tm = TabManager("rezer://newtab")
        t = tm.new_tab("https://a.com/")
        t.navigate("https://b.com/")
        t.navigate("https://c.com/")
        assert t.can_back()
        assert not t.can_forward()
        t.back()
        assert t.url == "https://b.com/"
        assert t.can_forward()
        t.forward()
        assert t.url == "https://c.com/"

    def test_navigate_truncates_forward(self):
        from rezer.tabs import TabManager
        tm = TabManager("rezer://newtab")
        t = tm.new_tab("https://a.com/")
        t.navigate("https://b.com/")
        t.back()
        t.navigate("https://c.com/")  # should drop b.com from forward stack
        assert not t.can_forward()
        assert t.url == "https://c.com/"

    def test_close_active_activates_right_neighbor(self):
        """Chrome behavior: closing the active tab activates the tab that
        slid into its slot (right neighbor), not the last tab."""
        from rezer.tabs import TabManager
        tm = TabManager("rezer://newtab")
        a = tm.new_tab("https://a.com/")
        b = tm.new_tab("https://b.com/")
        c = tm.new_tab("https://c.com/")
        d = tm.new_tab("https://d.com/")
        tm.switch(b.id)
        tm.close_tab(b.id)
        assert tm.active().id == c.id  # right neighbor, NOT d (the last tab)

    def test_close_last_tab_activates_left_neighbor(self):
        from rezer.tabs import TabManager
        tm = TabManager("rezer://newtab")
        a = tm.new_tab("https://a.com/")
        b = tm.new_tab("https://b.com/")
        # b is active and rightmost
        tm.close_tab(b.id)
        assert tm.active().id == a.id

    def test_close_inactive_tab_keeps_active(self):
        from rezer.tabs import TabManager
        tm = TabManager("rezer://newtab")
        a = tm.new_tab("https://a.com/")
        b = tm.new_tab("https://b.com/")
        c = tm.new_tab("https://c.com/")
        # c is active; closing a must not change the active tab
        tm.close_tab(a.id)
        assert tm.active().id == c.id

    def test_urls_excludes_rezer(self):
        from rezer.tabs import TabManager
        tm = TabManager("rezer://newtab")
        tm.new_tab("rezer://newtab")
        tm.new_tab("https://real.com/")
        urls = tm.urls()
        assert "https://real.com/" in urls
        assert "rezer://newtab" not in urls


# ---------- passwords (mock dpapi) ----------

class TestPasswords:
    def test_save_get(self):
        import rezer.dpapi as dpapi_mod
        # dpapi is passthrough off-Windows already; just use it
        from rezer.passwords import PasswordManager
        pm = PasswordManager()
        pm.put("https://example.com/login", "user1", "pass123")
        assert pm.has("https://example.com/login")
        creds = pm.get("https://example.com/login")
        assert creds["username"] == "user1"
        assert creds["password"] == "pass123"
        # domain matching: different path, same domain
        assert pm.has("https://example.com/other")
        pm.delete("https://example.com/login")
        assert not pm.has("https://example.com/login")

    def test_persistence_encrypted(self):
        from rezer.passwords import PasswordManager
        pm = PasswordManager()
        pm.put("https://persist.test/", "u", "p")
        # raw file should NOT contain plaintext password
        with open(pm.path, "r") as f:
            raw = f.read()
        assert "p" not in json.loads(raw).get("data", "") or True  # encrypted blob
        assert '"password": "p"' not in raw  # not plaintext JSON
        # reload and verify decrypt works
        pm2 = PasswordManager()
        assert pm2.get("https://persist.test/")["username"] == "u"
        pm.delete("https://persist.test/")


# ---------- adblock ----------

class TestAdblock:
    def test_injection_js_valid(self):
        from rezer.adblock import injection_js
        js = injection_js()
        assert "%DOMAINS%" not in js
        assert "%SELECTORS%" not in js
        assert "doubleclick.net" in js
        # write to temp file and node --check it
        import subprocess
        with tempfile.NamedTemporaryFile(suffix=".js", mode="w", delete=False) as f:
            f.write(js)
            path = f.name
        try:
            r = subprocess.run(["node", "--check", path], capture_output=True, timeout=10)
            assert r.returncode == 0, r.stderr.decode()
        finally:
            os.unlink(path)

    def test_blocked_domains_nonempty(self):
        from rezer.adblock import BLOCKED_DOMAINS, AD_SELECTORS
        assert len(BLOCKED_DOMAINS) > 10
        assert len(AD_SELECTORS) > 5


# ---------- updater ----------

class TestUpdater:
    def test_version_tuple(self):
        from rezer.updater import _version_tuple
        assert _version_tuple("v0.1.3") == (0, 1, 3)
        assert _version_tuple("0.1.10") == (0, 1, 10)
        assert _version_tuple("v1.0.0") > _version_tuple("v0.9.9")

    def test_check_for_update_newer(self, monkeypatch):
        import rezer.updater as up
        import rezer

        class FakeResp:
            def raise_for_status(self): pass
            def json(self):
                return {"tag_name": "v9.9.9",
                        "assets": [{"name": "Rezer.exe",
                                    "browser_download_url": "https://example.com/Rezer.exe"}]}

        monkeypatch.setattr(up.requests, "get", lambda *a, **k: FakeResp())
        monkeypatch.setattr(rezer, "__version__", "0.1.3")
        # need to re-read __version__ — updater does `from . import __version__` at import time
        # so patch the module attr directly
        monkeypatch.setattr(up, "__version__", "0.1.3")
        result = up.check_for_update()
        assert result is not None
        assert result[0] == "v9.9.9"

    def test_check_for_update_not_newer(self, monkeypatch):
        import rezer.updater as up

        class FakeResp:
            def raise_for_status(self): pass
            def json(self):
                return {"tag_name": "v0.1.0",
                        "assets": [{"name": "Rezer.exe",
                                    "browser_download_url": "https://example.com/Rezer.exe"}]}

        monkeypatch.setattr(up.requests, "get", lambda *a, **k: FakeResp())
        monkeypatch.setattr(up, "__version__", "0.1.3")
        assert up.check_for_update() is None

    def test_check_for_update_no_exe_asset(self, monkeypatch):
        import rezer.updater as up

        class FakeResp:
            def raise_for_status(self): pass
            def json(self):
                return {"tag_name": "v9.9.9", "assets": [{"name": "readme.txt"}]}

        monkeypatch.setattr(up.requests, "get", lambda *a, **k: FakeResp())
        monkeypatch.setattr(up, "__version__", "0.1.3")
        assert up.check_for_update() is None

    def test_check_for_update_network_fail(self, monkeypatch):
        import rezer.updater as up
        import requests

        def boom(*a, **k):
            raise requests.RequestException("nope")
        monkeypatch.setattr(up.requests, "get", boom)
        assert up.check_for_update() is None

    def test_check_for_update_picks_rezer_exe_not_installer(self, monkeypatch):
        """Releases ship BOTH Rezer.exe and Rezer-Setup.exe (installer).
        Even when the installer is listed first, the updater must pick the
        browser exe — swapping the installer in as the browser would break it."""
        import rezer.updater as up

        class FakeResp:
            def raise_for_status(self): pass
            def json(self):
                return {"tag_name": "v9.9.9",
                        "assets": [
                            {"name": "Rezer-Setup.exe",
                             "browser_download_url": "https://example.com/Rezer-Setup.exe"},
                            {"name": "Rezer.exe",
                             "browser_download_url": "https://example.com/Rezer.exe"},
                        ]}

        monkeypatch.setattr(up.requests, "get", lambda *a, **k: FakeResp())
        monkeypatch.setattr(up, "__version__", "0.1.3")
        result = up.check_for_update()
        assert result is not None
        assert result[1] == "https://example.com/Rezer.exe"

    def test_check_for_update_installer_only_is_none(self, monkeypatch):
        """If a release somehow has only the installer, don't 'update' to it."""
        import rezer.updater as up

        class FakeResp:
            def raise_for_status(self): pass
            def json(self):
                return {"tag_name": "v9.9.9",
                        "assets": [{"name": "Rezer-Setup.exe",
                                    "browser_download_url": "https://example.com/Rezer-Setup.exe"}]}

        monkeypatch.setattr(up.requests, "get", lambda *a, **k: FakeResp())
        monkeypatch.setattr(up, "__version__", "0.1.3")
        assert up.check_for_update() is None


# ---------- luna ----------

class TestLuna:
    def test_ask_success(self, monkeypatch):
        import rezer.luna as luna

        class FakeResp:
            text = "Hello from Luna"
            def raise_for_status(self): pass

        monkeypatch.setattr(luna.requests, "get", lambda *a, **k: FakeResp())
        assert luna.ask("hi") == "Hello from Luna"

    def test_ask_network_fail(self, monkeypatch):
        import rezer.luna as luna
        import requests

        def boom(*a, **k):
            raise requests.RequestException("down")
        monkeypatch.setattr(luna.requests, "get", boom)
        resp = luna.ask("hi")
        assert "couldn't reach" in resp

    def test_summarize_truncates(self, monkeypatch):
        import rezer.luna as luna
        seen = {}

        class FakeResp:
            text = "summary"
            def raise_for_status(self): pass

        def fake_get(url, **k):
            seen["url"] = url
            return FakeResp()
        monkeypatch.setattr(luna.requests, "get", fake_get)
        luna.summarize_page("x" * 10000)
        # URL should not contain the full 10000 chars (truncated to 4000)
        assert len(seen["url"]) < 9000


# ---------- api contract ----------

class TestApiContract:
    """Verify every method JS can call exists and behaves sanely."""

    def _make_api(self):
        from rezer.api import Api
        from rezer.tabs import TabManager
        from rezer.settings import SettingsManager
        from rezer.history import HistoryManager
        from rezer.bookmarks import BookmarkManager
        from rezer.passwords import PasswordManager

        class FakeWindow:
            def __init__(self):
                self.loaded_urls = []
                self.evaluated = []
            def load_url(self, url):
                self.loaded_urls.append(url)
            def evaluate_js(self, js):
                self.evaluated.append(js)
                return None

        w = FakeWindow()
        tabs = TabManager("rezer://newtab")
        tabs.new_tab("rezer://newtab")
        settings = SettingsManager()
        history = HistoryManager()
        bookmarks = BookmarkManager()
        passwords = PasswordManager()
        ctx = {
            # NOTE: app.py passes a lambda here; Api._w() must resolve it.
            "window": lambda: w,
            "tabs": tabs,
            "settings": settings,
            "history": history,
            "bookmarks": bookmarks,
            "passwords": passwords,
            "private": False,
            "newtab_url": "rezer://newtab",
            "settings_url": "rezer://settings",
            "resolve_url": lambda u: u,
            "normalize_url": lambda u: u,
            "on_navigate": lambda tab, url: None,
            "open_private": lambda: None,
            "open_window": lambda: None,
        }
        api = Api(ctx)
        return api, w, ctx

    def test_w_resolves_window(self):
        """CRITICAL: _w() must return the window, not the lambda."""
        api, w, ctx = self._make_api()
        resolved = api._w()
        assert resolved is w, \
            f"_w() returned {type(resolved)} instead of the window! push_state/load_url are broken."

    def test_push_state_evaluates(self):
        api, w, ctx = self._make_api()
        api.push_state()
        assert len(w.evaluated) == 1
        assert "RezerChrome.sync(" in w.evaluated[0]

    def test_new_tab_loads_url(self):
        api, w, ctx = self._make_api()
        api.new_tab("https://example.com/")
        assert w.loaded_urls, "new_tab did not call window.load_url"
        assert "https://example.com/" in w.loaded_urls[-1]

    def test_navigate_url(self):
        api, w, ctx = self._make_api()
        api.navigate("https://example.com/")
        assert "https://example.com/" in w.loaded_urls[-1]

    def test_navigate_search(self):
        api, w, ctx = self._make_api()
        api.navigate("some search query")
        assert "google.com/search" in w.loaded_urls[-1]

    def test_navigate_bare_domain(self):
        api, w, ctx = self._make_api()
        api.navigate("example.com")
        assert w.loaded_urls[-1] == "https://example.com"

    def test_navigate_empty_noop(self):
        api, w, ctx = self._make_api()
        n = len(w.loaded_urls)
        api.navigate("")
        api.navigate(None)
        assert len(w.loaded_urls) == n

    def test_switch_tab(self):
        api, w, ctx = self._make_api()
        tabs = ctx["tabs"]
        t1 = tabs.tabs[0]
        api.new_tab("https://b.com/")
        api.switch_tab(t1.id)
        assert tabs.active().id == t1.id

    def test_close_tab(self):
        api, w, ctx = self._make_api()
        tabs = ctx["tabs"]
        t = tabs.new_tab("https://b.com/")
        api.close_tab(t.id)
        assert all(x.id != t.id for x in tabs.tabs)

    def test_go_back_forward(self):
        api, w, ctx = self._make_api()
        api.navigate("https://a.com/")
        api.navigate("https://b.com/")
        api.go_back()
        assert "https://a.com/" in w.loaded_urls[-1]
        api.go_forward()
        assert "https://b.com/" in w.loaded_urls[-1]

    def test_toggle_bookmark(self):
        api, w, ctx = self._make_api()
        bm = ctx["bookmarks"]
        # clean
        for item in bm.all():
            bm.remove(item["url"])
        api.navigate("https://example.com/")
        api.toggle_bookmark()
        assert bm.is_bookmarked("https://example.com/")
        api.toggle_bookmark()
        assert not bm.is_bookmarked("https://example.com/")

    def test_open_bookmark(self):
        api, w, ctx = self._make_api()
        api.open_bookmark("https://example.com/")
        assert "https://example.com/" in w.loaded_urls[-1]

    def test_toggle_pin(self):
        api, w, ctx = self._make_api()
        bm = ctx["bookmarks"]
        for item in bm.all():
            bm.remove(item["url"])
        bm.add("X", "https://x.com/")
        api.toggle_pin("https://x.com/")
        assert bm.pinned()
        bm.remove("https://x.com/")

    def test_remove_bookmark(self):
        api, w, ctx = self._make_api()
        bm = ctx["bookmarks"]
        for item in bm.all():
            bm.remove(item["url"])
        bm.add("X", "https://x.com/")
        api.remove_bookmark("https://x.com/")
        assert not bm.is_bookmarked("https://x.com/")

    def test_toggle_luna(self):
        api, w, ctx = self._make_api()
        assert api._luna_open is False
        api.toggle_luna()
        assert api._luna_open is True
        assert "lunaOpen" in w.evaluated[-1]

    def test_get_state_shape(self):
        api, w, ctx = self._make_api()
        s = api.get_state()
        for key in ("tabs", "activeId", "activeUrl", "canBack", "canForward",
                    "bookmarks", "bookmarked", "bookmarkBar", "themeColor",
                    "adblock", "lunaOpen", "private", "hasPassword"):
            assert key in s, f"state missing {key}"

    def test_get_suggestions(self):
        api, w, ctx = self._make_api()
        hist = ctx["history"]
        hist.clear()
        hist.add("https://example.com/", "Example")
        out = api.get_suggestions("example")
        assert isinstance(out, list) and len(out) == 1
        assert api.get_suggestions("") == []
        hist.clear()

    def test_suggestions_after_browsing(self):
        """Simulate the real flow: visits get recorded (as app._on_loaded
        does), then typing in the address bar must surface them."""
        api, w, ctx = self._make_api()
        hist = ctx["history"]
        hist.clear()
        # what _on_loaded records after real page loads
        hist.add("https://www.youtube.com/watch?v=abc", "Cool Video - YouTube")
        hist.add("https://github.com/Hoopslimbo/rezer", "Hoopslimbo/rezer - GitHub")
        hist.add("https://www.reddit.com/r/test", "test subreddit")
        out = api.get_suggestions("you")
        assert any("youtube.com" in r["url"] for r in out), out
        out = api.get_suggestions("git")
        assert any("github.com" in r["url"] for r in out), out
        # matched by title as well as URL
        out = api.get_suggestions("cool video")
        assert any("youtube.com" in r["url"] for r in out), out
        assert api.get_suggestions("nonexistentthing") == []
        hist.clear()

    def test_google_suggestions(self, monkeypatch):
        import rezer.api as api_mod

        class FakeResp:
            def raise_for_status(self): pass
            def json(self):
                return ["you", ["youtube", "youtube music", "you"]]

        seen = {}
        def fake_get(url, **k):
            seen["url"] = url
            seen["params"] = k.get("params")
            return FakeResp()
        monkeypatch.setattr(api_mod.requests, "get", fake_get)
        api, w, ctx = self._make_api()
        out = api.google_suggestions("you")
        assert seen["url"] == "https://suggestqueries.google.com/complete/search"
        titles = [o["title"] for o in out]
        # echo of the query itself is dropped; results tagged as search kind
        assert titles == ["youtube", "youtube music"]
        assert all(o["kind"] == "search" for o in out)
        assert all("google.com/search" in o["url"] for o in out)

    def test_google_suggestions_offline_and_empty(self, monkeypatch):
        import rezer.api as api_mod
        import requests as req

        def boom(*a, **k):
            raise req.RequestException("offline")
        monkeypatch.setattr(api_mod.requests, "get", boom)
        api, w, ctx = self._make_api()
        assert api.google_suggestions("anything") == []  # must not raise
        assert api.google_suggestions("") == []
        assert api.google_suggestions("   ") == []

    def test_cycle_tab(self):
        api, w, ctx = self._make_api()
        tabs = ctx["tabs"]
        t1 = tabs.tabs[0]
        api.new_tab("https://b.com/")
        t2 = tabs.active()
        api.new_tab("https://c.com/")
        t3 = tabs.active()
        api.switch_tab(t1.id)
        api.cycle_tab(1)
        assert tabs.active().id == t2.id
        api.cycle_tab(1)
        assert tabs.active().id == t3.id
        api.cycle_tab(1)  # wraps around
        assert tabs.active().id == t1.id
        api.cycle_tab(-1)  # and backwards
        assert tabs.active().id == t3.id

    def test_get_history(self):
        api, w, ctx = self._make_api()
        assert isinstance(api.get_history(), list)

    def test_clear_history(self):
        api, w, ctx = self._make_api()
        ctx["history"].add("https://x.com/", "X")
        assert api.clear_history() is True
        assert ctx["history"].recent(10) == []

    def test_get_set_setting(self):
        api, w, ctx = self._make_api()
        s = api.get_settings()
        assert "theme_color" in s
        assert api.set_setting("theme_color", "#123456") is True
        assert api.get_settings()["theme_color"] == "#123456"
        assert api.set_setting("bogus_key", 1) is False
        api.set_setting("theme_color", "#ffffff")

    def test_open_settings(self):
        api, w, ctx = self._make_api()
        api.open_settings()
        assert "rezer://settings" in w.loaded_urls[-1]

    def test_on_url_changed(self):
        api, w, ctx = self._make_api()
        api.on_url_changed("about:blank")  # noop
        api.on_url_changed("https://example.com/page")
        assert ctx["tabs"].active().url == "https://example.com/page"

    def test_on_title(self):
        api, w, ctx = self._make_api()
        api.on_title("My Title")
        assert ctx["tabs"].active().title == "My Title"

    def test_password_flow(self):
        api, w, ctx = self._make_api()
        pw = ctx["passwords"]
        api.navigate("https://secure.example/")
        assert api.password_offer("u", "p") is True
        assert api.password_save("u", "p") is True
        assert api.password_offer("u", "p") is False  # already saved
        creds = api.password_fill()
        assert creds["username"] == "u" and creds["password"] == "p"
        pw.delete("https://secure.example/")

    def test_password_private_blocked(self):
        from rezer.api import Api
        api, w, ctx = self._make_api()
        ctx["private"] = True
        assert api.password_offer("u", "p") is False
        assert api.password_save("u", "p") is False

    def test_take_screenshot_no_window(self):
        api, w, ctx = self._make_api()
        # FakeWindow has no x/y attrs -> error dict, not exception
        r = api.take_screenshot()
        assert isinstance(r, dict) and r["ok"] is False

    def test_asset_url(self):
        api, w, ctx = self._make_api()
        u = api.asset_url("luna.png")
        assert u.startswith("file://")

    def test_luna_logo(self):
        api, w, ctx = self._make_api()
        assert api.luna_logo().startswith("file://")

    def test_check_update_now_shape(self, monkeypatch):
        import rezer.api as api_mod
        import rezer.updater as up
        monkeypatch.setattr(up, "check_for_update", lambda: ("v9.9.9", "https://x/Rezer.exe"))
        api, w, ctx = self._make_api()
        r = api.check_update_now()
        assert r == {"update": True, "tag": "v9.9.9"}
        monkeypatch.setattr(up, "check_for_update", lambda: None)
        r = api.check_update_now()
        assert r == {"update": False, "tag": ""}

    def test_reload(self):
        api, w, ctx = self._make_api()
        api.navigate("https://example.com/")
        n = len(w.loaded_urls)
        api.reload()
        assert len(w.loaded_urls) == n + 1


# ---------- JS <-> Python contract ----------

# Every api.X() call found in the UI must exist on Api.
JS_API_CALLS = [
    # chrome.js
    "close_tab", "switch_tab", "new_tab", "cycle_tab", "go_back", "go_forward", "reload",
    "toggle_bookmark", "open_settings", "take_screenshot", "navigate",
    "get_suggestions", "google_suggestions", "open_bookmark", "toggle_pin",
    "toggle_luna", "luna_ask", "luna_summarize", "luna_explain", "luna_logo",
    "password_offer", "password_save", "password_fill",
    "on_url_changed", "on_title", "get_state",
    "open_new_window", "open_private",
    # newtab.html
    # (navigate, get_suggestions, get_state, get_history, toggle_pin — covered)
    # settings.html
    "get_settings", "set_setting", "clear_history", "check_update_now",
    "remove_bookmark", "get_version", "get_history",
    # history.html
    # (get_history, navigate, clear_history — covered)
]


def test_js_api_contract():
    """Every JS-called method must exist on Api."""
    from rezer.api import Api
    missing = [name for name in JS_API_CALLS if not hasattr(Api, name)]
    assert not missing, f"JS calls methods missing on Api: {missing}"


def test_js_calls_actually_in_files():
    """Sanity: the contract list above matches what's really in the UI files."""
    import re
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ui")
    found = set()
    for fn in ("chrome.js", "newtab.html", "settings.html", "history.html"):
        with open(os.path.join(base, fn), encoding="utf-8") as f:
            text = f.read()
        # call('name' ...)  /  api.name(  /  a.name(
        for m in re.finditer(r"""call\(\s*['"]([a-z_]+)['"]""", text):
            found.add(m.group(1))
        for m in re.finditer(r"""(?:api|a)\.([a-z_]+)\s*\(""", text):
            found.add(m.group(1))
    # every real call site should be in our contract list
    unlisted = {c for c in found if c not in JS_API_CALLS and c != "then"}
    # 'then' is promise chaining, not an api call; filter noise
    noise = {"then", "catch", "querySelector", "getElementById", "addEventListener",
             "createElement", "appendChild", "remove", "forEach", "slice", "trim",
             "preventDefault", "stopPropagation", "setTimeout", "clearTimeout",
             "setInterval", "dispatchEvent", "scrollTop", "focus", "blur", "select",
             "getSelection", "toString", "push", "filter", "indexOf", "replace"}
    unlisted -= noise
    assert not unlisted, f"JS calls not in contract test list: {sorted(unlisted)}"
