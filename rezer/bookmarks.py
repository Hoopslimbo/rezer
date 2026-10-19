"""Bookmarks: JSON list. `pinned` bookmarks show at the top of the new-tab page."""

import json
import os

from .paths import data_dir


class BookmarkManager:
    def __init__(self):
        self.path = os.path.join(data_dir(), "bookmarks.json")
        self._items = []  # [{title, url, pinned}]
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self._items = [b for b in data if b.get("url")]
        except (FileNotFoundError, json.JSONDecodeError):
            self._items = []

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._items, f, indent=2)
        os.replace(tmp, self.path)

    def all(self):
        return list(self._items)

    def pinned(self):
        return [b for b in self._items if b.get("pinned")]

    def is_bookmarked(self, url: str) -> bool:
        return any(b["url"] == url for b in self._items)

    def add(self, title: str, url: str, pinned: bool = False):
        if not url or self.is_bookmarked(url):
            return False
        self._items.append({"title": title or url, "url": url, "pinned": pinned})
        self.save()
        return True

    def remove(self, url: str) -> bool:
        before = len(self._items)
        self._items = [b for b in self._items if b["url"] != url]
        if len(self._items) != before:
            self.save()
            return True
        return False

    def toggle_pin(self, url: str):
        for b in self._items:
            if b["url"] == url:
                b["pinned"] = not b.get("pinned", False)
                self.save()
                return b["pinned"]
        return None
