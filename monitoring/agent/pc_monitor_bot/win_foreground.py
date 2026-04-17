"""Windows: process + title cua so dang nhan tien canh (khong hook ban phim)."""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

import psutil


def foreground_process_title() -> tuple[str, str] | None:
    """
    Tra ve (process_name_lower, window_title) hoac None.
    """
    if sys.platform != "win32":
        return None
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        buf = ctypes.create_unicode_buffer(1024)
        user32.GetWindowTextW(hwnd, buf, 1024)
        title = (buf.value or "").strip()
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        try:
            p = psutil.Process(int(pid.value))
            name = (p.name() or "").lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, TypeError):
            name = ""
        if not name:
            return None
        return name, title
    except Exception:
        return None
