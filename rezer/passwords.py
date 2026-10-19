"""Built-in password manager. Credentials are Fernet-encrypted; the Fernet key
itself is DPAPI-protected (Windows user account bound)."""

import json
import os
import secrets

from cryptography.fernet import Fernet, InvalidToken

from . import dpapi
from .paths import data_dir


class PasswordManager:
    def __init__(self):
        self.path = os.path.join(data_dir(), "passwords.json")
        self._fernet = Fernet(self._load_or_create_key())
        self._store = {}  # domain -> {username, password}
        self.load()

    def _load_or_create_key(self) -> bytes:
        kp = dpapi.key_path()
        if os.path.exists(kp):
            with open(kp, "rb") as f:
                return dpapi.unprotect(f.read())
        key = Fernet.generate_key()
        with open(kp, "wb") as f:
            f.write(dpapi.protect(key))
        try:
            os.chmod(kp, 0o600)
        except OSError:
            pass
        return key

    @staticmethod
    def _domain(url: str) -> str:
        from urllib.parse import urlparse
        try:
            return urlparse(url).netloc.lower()
        except Exception:
            return url.lower()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                blob = json.load(f).get("data", "")
            raw = self._fernet.decrypt(blob.encode()).decode()
            data = json.loads(raw)
            self._store = data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, InvalidToken, ValueError):
            self._store = {}

    def save(self):
        blob = self._fernet.encrypt(json.dumps(self._store).encode()).decode()
        # small random pad so file size doesn't leak entry count precisely
        pad = secrets.token_hex(8)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"data": blob, "pad": pad}, f)
        os.replace(tmp, self.path)

    def has(self, url: str) -> bool:
        return self._domain(url) in self._store

    def get(self, url: str):
        return self._store.get(self._domain(url))

    def put(self, url: str, username: str, password: str):
        self._store[self._domain(url)] = {"username": username, "password": password}
        self.save()

    def delete(self, url: str) -> bool:
        if self._domain(url) in self._store:
            del self._store[self._domain(url)]
            self.save()
            return True
        return False

    def domains(self):
        return sorted(self._store.keys())
