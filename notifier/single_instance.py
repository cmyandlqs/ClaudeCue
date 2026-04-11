"""Single-instance guard for notifier process."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Optional

ERROR_ALREADY_EXISTS = 183


class SingleInstanceGuard:
    """Named mutex based single-instance guard for Windows."""

    def __init__(self, name: str = "Global\\ccCueNotifier") -> None:
        self.name = name
        self._handle: Optional[int] = None

    def acquire(self) -> bool:
        if self._handle:
            return True

        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
        kernel32.CreateMutexW.restype = wintypes.HANDLE

        handle = kernel32.CreateMutexW(None, False, self.name)
        if not handle:
            return False

        last_error = kernel32.GetLastError()
        if last_error == ERROR_ALREADY_EXISTS:
            kernel32.CloseHandle(handle)
            return False

        self._handle = handle
        return True

    def release(self) -> None:
        if not self._handle:
            return
        try:
            ctypes.windll.kernel32.CloseHandle(self._handle)
        finally:
            self._handle = None

    def __enter__(self) -> "SingleInstanceGuard":
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()
