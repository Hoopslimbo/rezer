"""Windows DPAPI helpers (ctypes) to protect the password-manager key.

DPAPI ties encryption to the Windows user account: only the same user on the
same machine can decrypt. Non-Windows platforms fall back to a plain file
(development only — Rezer targets Windows).
"""

import ctypes
import os
import sys

from .paths import data_dir

_ON_WINDOWS = sys.platform == "win32"


def _blob_class():
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_byte))]
    return _Blob


def _crypt_protect(data: bytes) -> bytes:
    _Blob = _blob_class()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    blob_in = _Blob(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    blob_out = _Blob()
    if not crypt32.CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _crypt_unprotect(data: bytes) -> bytes:
    _Blob = _blob_class()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    blob_in = _Blob(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
    blob_out = _Blob()
    if not crypt32.CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def protect(data: bytes) -> bytes:
    if _ON_WINDOWS:
        return _crypt_protect(data)
    return data


def unprotect(data: bytes) -> bytes:
    if _ON_WINDOWS:
        return _crypt_unprotect(data)
    return data


def key_path() -> str:
    return os.path.join(data_dir(), "pm.key")
