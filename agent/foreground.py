"""Windows foreground window capture (pure helpers + Win32 backend)."""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ForegroundInfo:
    process_name: str
    window_title: str
    process_path: str = ""
    hwnd: int = 0


class ForegroundError(RuntimeError):
    """Raised when the foreground window cannot be queried."""


def resolve_display_name(process_name: str, name_map: dict[str, str] | None = None) -> str:
    """Map a process executable name to a friendly display name."""
    if not process_name:
        return "Unknown"
    name_map = name_map or {}
    for key in (process_name, process_name.lower(), process_name.capitalize()):
        if key in name_map:
            return name_map[key]
    # Case-insensitive fallback
    lower_map = {k.lower(): v for k, v in name_map.items()}
    if process_name.lower() in lower_map:
        return lower_map[process_name.lower()]
    return process_name


def is_blacklisted(process_name: str, blacklist: list[str] | None = None) -> bool:
    """Return True when process_name matches the local privacy blacklist."""
    if not process_name or not blacklist:
        return False
    target = process_name.lower()
    return any(target == item.lower() or target == item.lower() + ".exe" for item in blacklist)


def get_foreground_info() -> ForegroundInfo:
    """Return the current foreground app. Windows-only for live capture."""
    if sys.platform != "win32":
        raise ForegroundError("live foreground capture requires Windows")
    return _get_foreground_info_win32()


def _get_foreground_info_win32() -> ForegroundInfo:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetForegroundWindow.argtypes = []

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        raise ForegroundError("GetForegroundWindow returned null")

    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int

    title_len = user32.GetWindowTextLengthW(hwnd)
    title_buf = ctypes.create_unicode_buffer(title_len + 1)
    user32.GetWindowTextW(hwnd, title_buf, title_len + 1)
    window_title = title_buf.value or ""

    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, wintypes.LPDWORD]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    pid = wintypes.DWORD(0)
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ForegroundInfo(process_name="Unknown", window_title=window_title, hwnd=int(hwnd))

    process_query_limited = 0x1000
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(process_query_limited, False, pid.value)
    if not handle:
        return ForegroundInfo(process_name="Unknown", window_title=window_title, hwnd=int(hwnd))

    try:
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            wintypes.PDWORD,
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        size = wintypes.DWORD(32768)
        path_buf = ctypes.create_unicode_buffer(size.value)
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, path_buf, ctypes.byref(size))
        process_path = path_buf.value if ok else ""
        process_name = process_path.rsplit("\\", 1)[-1] if process_path else "Unknown"
        return ForegroundInfo(
            process_name=process_name,
            window_title=window_title,
            process_path=process_path,
            hwnd=int(hwnd),
        )
    finally:
        kernel32.CloseHandle(handle)
