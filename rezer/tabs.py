"""Per-window tab model. Tabs are virtual: one webview per window, and switching
tabs just loads that tab's URL (with its own back/forward stacks in Python)."""

import itertools

_ids = itertools.count(1)


class Tab:
    def __init__(self, url: str, title: str = "New Tab"):
        self.id = next(_ids)
        self.url = url
        self.title = title
        self.history = [url] if url else []
        self.hindex = 0 if url else -1
        self.pinned_scroll = 0

    def navigate(self, url: str):
        # truncate forward history, push new entry
        self.history = self.history[: self.hindex + 1]
        if not self.history or self.history[-1] != url:
            self.history.append(url)
        self.hindex = len(self.history) - 1
        self.url = url

    def record_visit(self, url: str):
        """In-page navigations (links, SPA) land here."""
        if url != self.url:
            self.navigate(url)

    def can_back(self) -> bool:
        return self.hindex > 0

    def can_forward(self) -> bool:
        return self.hindex < len(self.history) - 1

    def back(self):
        if self.can_back():
            self.hindex -= 1
            self.url = self.history[self.hindex]
        return self.url

    def forward(self):
        if self.can_forward():
            self.hindex += 1
            self.url = self.history[self.hindex]
        return self.url

    def to_dict(self):
        return {"id": self.id, "url": self.url, "title": self.title}


class TabManager:
    def __init__(self, newtab_url: str):
        self.newtab_url = newtab_url
        self.tabs = []
        self.active_id = None

    def new_tab(self, url: str = None) -> Tab:
        tab = Tab(url or self.newtab_url)
        self.tabs.append(tab)
        self.active_id = tab.id
        return tab

    def close_tab(self, tab_id: int):
        self.tabs = [t for t in self.tabs if t.id != tab_id]
        if not self.tabs:
            self.new_tab()
        elif self.active_id == tab_id:
            self.active_id = self.tabs[-1].id
        return self.active()

    def active(self) -> Tab:
        for t in self.tabs:
            if t.id == self.active_id:
                return t
        self.active_id = self.tabs[0].id
        return self.tabs[0]

    def switch(self, tab_id: int):
        if any(t.id == tab_id for t in self.tabs):
            self.active_id = tab_id
        return self.active()

    def get(self, tab_id: int):
        for t in self.tabs:
            if t.id == tab_id:
                return t
        return None

    def urls(self):
        return [t.url for t in self.tabs if t.url and not t.url.startswith("rezer://")]
