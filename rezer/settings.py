"""Persistent settings (JSON)."""

import json
import os

from .paths import data_dir

DEFAULTS = {
    "theme_color": "#ffffff",      # default white; changeable via color wheel
    "dark_text": True,             # dark text on light themes
    "bookmark_bar_visible": True, # bookmark bar visible by default
    "adblock_enabled": True,
    "restore_tabs": True,          # restore last tabs on startup
    "search_engine": "google",
    "luna_enabled": True,
    "last_sunday_clear": "",       # date string of last weekly history wipe
    "saved_tabs": [],              # urls restored on startup
}

SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q={q}",
    "bing": "https://www.bing.com/search?q={q}",
    "duckduckgo": "https://duckduckgo.com/?q={q}",
}


class SettingsManager:
    def __init__(self):
        self.path = os.path.join(data_dir(), "settings.json")
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k in DEFAULTS:
                    self._data[k] = v
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self.path)

    def get(self, key):
        return self._data.get(key, DEFAULTS.get(key))

    def set(self, key, value):
        if key not in DEFAULTS:
            raise KeyError(key)
        self._data[key] = value
        self.save()

    def all(self):
        return dict(self._data)

    def search_url(self, query: str) -> str:
        tmpl = SEARCH_ENGINES.get(self.get("search_engine"), SEARCH_ENGINES["google"])
        from urllib.parse import quote_plus
        return tmpl.format(q=quote_plus(query))
