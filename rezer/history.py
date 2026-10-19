"""Browsing history: SQLite, keeps the past week, wiped every Sunday."""

import datetime
import os
import sqlite3
import threading

from .paths import data_dir

SCHEMA = """
CREATE TABLE IF NOT EXISTS visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    visited_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_visits_time ON visits(visited_at);
"""


class HistoryManager:
    def __init__(self):
        self.path = os.path.join(data_dir(), "history.db")
        self._lock = threading.Lock()
        with self._connect() as c:
            c.executescript(SCHEMA)

    def _connect(self):
        return sqlite3.connect(self.path)

    @staticmethod
    def _now_iso():
        return datetime.datetime.now().isoformat(timespec="seconds")

    def add(self, url: str, title: str = ""):
        """Record a visit. Skips local browser pages (new tab / settings)."""
        if not url or url.startswith(("about:", "rezer://")):
            return
        with self._lock, self._connect() as c:
            c.execute(
                "INSERT INTO visits (url, title, visited_at) VALUES (?, ?, ?)",
                (url, title or url, self._now_iso()),
            )

    def recent(self, limit: int = 50):
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
        with self._lock, self._connect() as c:
            rows = c.execute(
                "SELECT url, title, visited_at FROM visits "
                "WHERE visited_at >= ? ORDER BY visited_at DESC LIMIT ?",
                (cutoff, limit),
            ).fetchall()
        return [{"url": u, "title": t, "visited_at": ts} for u, t, ts in rows]

    def top_sites(self, limit: int = 8):
        """Most-visited domains in the past week (for new-tab shortcuts)."""
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
        with self._lock, self._connect() as c:
            rows = c.execute(
                "SELECT url, title, COUNT(*) AS n FROM visits "
                "WHERE visited_at >= ? GROUP BY url ORDER BY n DESC LIMIT ?",
                (cutoff, limit),
            ).fetchall()
        return [{"url": u, "title": t, "visits": n} for u, t, n in rows]

    def prune_week(self):
        """Drop anything older than 7 days."""
        cutoff = (datetime.datetime.now() - datetime.timedelta(days=7)).isoformat()
        with self._lock, self._connect() as c:
            c.execute("DELETE FROM visits WHERE visited_at < ?", (cutoff,))

    def clear(self):
        with self._lock, self._connect() as c:
            c.execute("DELETE FROM visits")

    def maybe_sunday_clear(self, settings) -> bool:
        """Spec: history resets every Sunday. Returns True if a wipe happened."""
        today = datetime.date.today()
        if today.weekday() != 6:  # Monday=0 .. Sunday=6
            return False
        if settings.get("last_sunday_clear") == today.isoformat():
            return False
        self.clear()
        settings.set("last_sunday_clear", today.isoformat())
        return True
