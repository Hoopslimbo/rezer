"""JS bridge: methods the browser chrome (injected JS) can call.

One Api instance per window. The chrome calls these via `pywebview.api.<name>`.
After state-changing calls, Python pushes fresh state into the page with
`RezerChrome.sync(state)` so the tab strip / address bar stay correct.
"""

import json
import os
import threading

from . import luna as luna_ai
from . import screenshot as screenshot_mod
from .paths import resource_path


def _is_url(text: str) -> bool:
    t = text.strip()
    if " " in t:
        return False
    if t.startswith(("http://", "https://", "file://", "rezer://")):
        return True
    # domain.tld or localhost...
    return "." in t and not t.startswith(".")


class Api:
    def __init__(self, ctx):
        """
        ctx: dict with keys: window, tabs (TabManager), settings, history,
             bookmarks, passwords, private (bool), newtab_url, on_navigate (fn),
             open_private (fn), app_quit_check (fn)
        """
        self.c = ctx
        self._luna_open = False

    # ---------- internal helpers ----------

    def _w(self):
        # app.py passes "window" as a lambda (deferred lookup, since the
        # window doesn't exist yet when the Api is constructed). Resolve it.
        w = self.c["window"]
        return w() if callable(w) else w

    def _eval(self, js: str):
        try:
            self._w().evaluate_js(js)
        except Exception:
            pass

    def state(self):
        tabs = self.c["tabs"]
        active = tabs.active()
        s = self.c["settings"]
        return {
            "tabs": [t.to_dict() for t in tabs.tabs],
            "activeId": active.id,
            "activeUrl": active.url,
            "canBack": active.can_back(),
            "canForward": active.can_forward(),
            "bookmarks": self.c["bookmarks"].all(),
            "bookmarked": self.c["bookmarks"].is_bookmarked(active.url),
            "bookmarkBar": s.get("bookmark_bar_visible"),
            "themeColor": s.get("theme_color"),
            "adblock": s.get("adblock_enabled"),
            "lunaOpen": self._luna_open,
            "private": self.c["private"],
            "hasPassword": self.c["passwords"].has(active.url),
        }

    def push_state(self):
        self._eval("window.RezerChrome && RezerChrome.sync(" + json.dumps(self.state()) + ")")

    def get_state(self):
        # called once by freshly injected chrome to pull initial state
        return self.state()

    def _load_active(self):
        tab = self.c["tabs"].active()
        self._w().load_url(self.c["resolve_url"](tab.url))
        self.push_state()

    # ---------- tabs ----------

    def new_tab(self, url=None):
        tab = self.c["tabs"].new_tab(url or self.c["newtab_url"])
        self._load_active()
        return tab.id

    def close_tab(self, tab_id):
        self.c["tabs"].close_tab(int(tab_id))
        self._load_active()

    def switch_tab(self, tab_id):
        self.c["tabs"].switch(int(tab_id))
        self._load_active()

    # ---------- navigation ----------

    def navigate(self, text):
        text = (text or "").strip()
        if not text:
            return
        if _is_url(text):
            url = text if "://" in text else "https://" + text
        else:
            url = self.c["settings"].search_url(text)
        tab = self.c["tabs"].active()
        tab.navigate(url)
        self.c["on_navigate"](tab, url)
        self._load_active()

    def go_back(self):
        tab = self.c["tabs"].active()
        url = tab.back()
        self._w().load_url(self.c["resolve_url"](url))
        self.push_state()

    def go_forward(self):
        tab = self.c["tabs"].active()
        url = tab.forward()
        self._w().load_url(self.c["resolve_url"](url))
        self.push_state()

    def reload(self):
        tab = self.c["tabs"].active()
        self._w().load_url(self.c["resolve_url"](tab.url))

    def on_url_changed(self, url):
        """Called by the injected poller when location.href changes in-page."""
        if not url or url == "about:blank":
            return
        url = self.c["normalize_url"](url)
        tab = self.c["tabs"].active()
        if url != tab.url:
            tab.record_visit(url)
            self.c["on_navigate"](tab, url)
            self.push_state()

    def on_title(self, title):
        tab = self.c["tabs"].active()
        if title and title != tab.title:
            tab.title = title[:120]
            self.push_state()

    # ---------- bookmarks ----------

    def toggle_bookmark(self):
        tab = self.c["tabs"].active()
        bm = self.c["bookmarks"]
        if bm.is_bookmarked(tab.url):
            bm.remove(tab.url)
        else:
            bm.add(tab.title, tab.url)
        self.push_state()

    def open_bookmark(self, url):
        self.navigate(url)

    def toggle_pin(self, url):
        self.c["bookmarks"].toggle_pin(url)
        self.push_state()

    def remove_bookmark(self, url):
        self.c["bookmarks"].remove(url)
        self.push_state()

    # ---------- Luna ----------

    def toggle_luna(self):
        self._luna_open = not self._luna_open
        self.push_state()

    def luna_ask(self, prompt):
        # run off-thread; deliver via evaluate_js callback
        def work():
            resp = luna_ai.ask(prompt or "")
            self._eval("window.RezerChrome && RezerChrome.lunaReply(" + json.dumps(resp) + ")")
        threading.Thread(target=work, daemon=True).start()
        return True

    def luna_summarize(self, page_text):
        def work():
            resp = luna_ai.summarize_page(page_text or "")
            self._eval("window.RezerChrome && RezerChrome.lunaReply(" + json.dumps(resp) + ")")
        threading.Thread(target=work, daemon=True).start()
        return True

    def luna_explain(self, selected_text):
        def work():
            resp = luna_ai.explain_selection(selected_text or "")
            self._eval("window.RezerChrome && RezerChrome.lunaReply(" + json.dumps(resp) + ")")
        threading.Thread(target=work, daemon=True).start()
        return True

    # ---------- passwords ----------

    def password_offer(self, username, password):
        """JS found a login form submit. Returns True if we should prompt to save."""
        if self.c["private"]:
            return False
        tab = self.c["tabs"].active()
        return not self.c["passwords"].has(tab.url)

    def password_save(self, username, password):
        if self.c["private"]:
            return False
        tab = self.c["tabs"].active()
        self.c["passwords"].put(tab.url, username or "", password or "")
        self.push_state()
        return True

    def password_fill(self):
        tab = self.c["tabs"].active()
        return self.c["passwords"].get(tab.url) or {}

    # ---------- screenshot ----------

    def take_screenshot(self):
        w = self._w()
        try:
            x, y = w.x, w.y
            width, height = w.width, w.height
        except Exception:
            return {"ok": False, "error": "window geometry unavailable"}
        try:
            path = screenshot_mod.capture_window(x, y, width, height)
            return {"ok": True, "path": path}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ---------- history ----------

    def get_history(self):
        return self.c["history"].recent(100)

    def get_suggestions(self, query):
        """Autocomplete suggestions: history entries matching the query."""
        try:
            return self.c["history"].search(query or "", limit=8)
        except Exception:
            return []

    def clear_history(self):
        self.c["history"].clear()
        return True

    # ---------- settings ----------

    def get_settings(self):
        s = self.c["settings"].all()
        # settings.html renders the bookmark list from here
        s["bookmarks"] = self.c["bookmarks"].all()
        return s

    def get_version(self):
        from . import __version__
        return __version__

    def set_setting(self, key, value):
        try:
            self.c["settings"].set(key, value)
        except KeyError:
            return False
        self.push_state()
        return True

    def open_settings(self):
        self.navigate(self.c["settings_url"])

    def check_update_now(self):
        from . import updater
        found = updater.check_for_update()
        return {"update": bool(found), "tag": found[0] if found else ""}

    # ---------- windows ----------

    def open_private(self):
        self.c["open_private"]()

    def open_new_window(self):
        self.c["open_window"]()

    # ---------- misc ----------

    def asset_url(self, name):
        # file:// url for bundled asset (logos)
        import pathlib
        p = pathlib.Path(resource_path(os.path.join("assets", name))).as_uri()
        return p

    def luna_logo(self):
        return self.asset_url("luna.png")
