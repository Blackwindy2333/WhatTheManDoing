"""Windows system tray icon via Shell_NotifyIcon (stdlib ctypes).

Provides keep-alive background presence with a context menu:
open main window / restart service / quit. Optional nicer icon via Pillow.
"""

from __future__ import annotations

import sys
import threading
from typing import Callable

# --- Win32 constants -------------------------------------------------------
NIM_ADD = 0x00000000
NIM_MODIFY = 0x00000001
NIM_DELETE = 0x00000002
NIF_MESSAGE = 0x00000001
NIF_ICON = 0x00000002
NIF_TIP = 0x00000004
NIF_INFO = 0x00000010
NIIF_INFO = 0x00000001

WM_USER = 0x0400
WM_TRAYICON = WM_USER + 1
WM_DESTROY = 0x0002
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_LBUTTONDBLCLK = 0x0203

MF_STRING = 0x0000
MF_SEPARATOR = 0x0800
TPM_RIGHTBUTTON = 0x0002
TPM_RETURNCMD = 0x0100
TPM_NONOTIFY = 0x0080

IDI_APPLICATION = 32512
IMAGE_ICON = 1
LR_LOADFROMFILE = 0x0010
LR_DEFAULTSIZE = 0x00000040

CMD_OPEN = 1001
CMD_RESTART = 1002
CMD_QUIT = 1003


def _notify_icondata_cls():
    import ctypes
    from ctypes import wintypes

    class NOTIFYICONDATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HICON),
            ("szTip", wintypes.WCHAR * 128),
            ("dwState", wintypes.DWORD),
            ("dwStateMask", wintypes.DWORD),
            ("szInfo", wintypes.WCHAR * 256),
            ("uTimeoutOrVersion", wintypes.UINT),
            ("szInfoTitle", wintypes.WCHAR * 64),
            ("dwInfoFlags", wintypes.DWORD),
            ("guidItem", ctypes.c_byte * 16),
            ("hBalloonIcon", wintypes.HICON),
        ]

    return NOTIFYICONDATA


def make_default_icon():
    """Return an HICON. Prefer a generated app icon; fall back to IDI_APPLICATION."""
    import ctypes

    hicon = _make_icon_from_pil()
    if hicon:
        return hicon
    return ctypes.windll.user32.LoadIconW(None, IDI_APPLICATION)


def _make_icon_from_pil():
    try:
        from io import BytesIO

        from PIL import Image, ImageDraw

        size = 64
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((4, 4, size - 4, size - 4), fill=(0, 113, 227, 255))
        draw.ellipse((18, 18, size - 18, size - 18), fill=(255, 255, 255, 255))
        draw.ellipse((26, 26, size - 26, size - 26), fill=(0, 113, 227, 255))
        ico = BytesIO()
        img.save(ico, format="ICO", sizes=[(16, 16), (32, 32)])
        return _load_icon_from_bytes(ico.getvalue())
    except Exception:
        return None


def _load_icon_from_bytes(data: bytes):
    import ctypes
    import tempfile
    from pathlib import Path

    try:
        tmp = Path(tempfile.gettempdir()) / "wtmd_tray_icon.ico"
        tmp.write_bytes(data)
        user32 = ctypes.windll.user32
        hicon = user32.LoadImageW(
            None, str(tmp), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE
        )
        return int(hicon) if hicon else None
    except Exception:
        return None


class TrayIcon:
    """Background tray icon with open / restart / quit menu."""

    def __init__(
        self,
        *,
        tooltip: str = "WhatTheManDoing",
        on_open: Callable[[], None] | None = None,
        on_restart: Callable[[], None] | None = None,
        on_quit: Callable[[], None] | None = None,
    ) -> None:
        if sys.platform != "win32":
            raise RuntimeError("system tray is only supported on Windows")
        self.tooltip = tooltip
        self.on_open = on_open
        self.on_restart = on_restart
        self.on_quit = on_quit

        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._hwnd = None
        self._hicon = None
        self._nid = None
        self._error: str | None = None
        self._wndproc_ref = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, timeout: float = 3.0) -> bool:
        if self.running:
            return True
        self._stop.clear()
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="wtmd-tray", daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        return self._error is None and self.running

    def stop(self) -> None:
        self._stop.set()
        try:
            import ctypes

            if self._hwnd:
                ctypes.windll.user32.PostMessageW(int(self._hwnd), WM_DESTROY, 0, 0)
        except Exception:
            pass
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None

    def notify(self, title: str, message: str) -> None:
        try:
            if not self._nid:
                return
            import ctypes

            self._nid.uFlags = NIF_INFO
            self._nid.szInfoTitle = title[:63]
            self._nid.szInfo = message[:255]
            self._nid.dwInfoFlags = NIIF_INFO
            ctypes.windll.shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(self._nid))
        except Exception:
            pass

    def _run(self) -> None:
        try:
            self._run_impl()
        except Exception as exc:  # noqa: BLE001
            self._error = str(exc)
            self._ready.set()

    def _run_impl(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32

        NOTIFYICONDATA = _notify_icondata_cls()
        self._notify_cls = NOTIFYICONDATA

        wc = wintypes.WNDCLASSW()
        wc.lpfnWndProc = self._make_wndproc()
        wc.hInstance = ctypes.windll.kernel32.GetModuleHandleW(None)
        wc.lpszClassName = "WhatTheManDoingTray"
        wc.hCursor = user32.LoadCursorW(None, 32512)
        user32.RegisterClassW(ctypes.byref(wc))

        self._hwnd = user32.CreateWindowExW(
            0,
            "WhatTheManDoingTray",
            "WhatTheManDoingTray",
            0,
            0,
            0,
            1,
            1,
            0,
            0,
            wc.hInstance,
            None,
        )
        if not self._hwnd:
            self._error = "CreateWindowExW failed"
            self._ready.set()
            return

        self._hicon = make_default_icon()
        nid = NOTIFYICONDATA()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
        nid.hWnd = self._hwnd
        nid.uID = 1
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = WM_TRAYICON
        nid.hIcon = self._hicon
        nid.szTip = self.tooltip[:127]
        self._nid = nid

        if not shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid)):
            self._error = "Shell_NotifyIconW(NIM_ADD) failed"
            self._ready.set()
            return

        self._ready.set()

        msg = wintypes.MSG()
        while not self._stop.is_set():
            has = user32.PeekMessageW(ctypes.byref(msg), 0, 0, 0, 1)
            if has:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
            else:
                self._stop.wait(0.05)

        try:
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
        except Exception:
            pass
        try:
            if self._hicon:
                user32.DestroyIcon(self._hicon)
        except Exception:
            pass

    def _make_wndproc(self):
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        WNDPROC = ctypes.WINFUNCTYPE(
            ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_TRAYICON:
                # Some Windows versions pack the mouse event in the low word.
                mouse = int(lparam) & 0xFFFF
                if mouse in (WM_LBUTTONUP, WM_LBUTTONDBLCLK):
                    if self.on_open:
                        self.on_open()
                elif mouse == WM_RBUTTONUP:
                    self._show_menu(hwnd)
                return 0
            if msg == WM_DESTROY:
                self._stop.set()
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc_ref = WNDPROC(wndproc)
        return self._wndproc_ref

    def _show_menu(self, hwnd) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hmenu = user32.CreatePopupMenu()
        if not hmenu:
            return
        try:
            user32.AppendMenuW(hmenu, MF_STRING, CMD_OPEN, "打开主页面")
            user32.AppendMenuW(hmenu, MF_STRING, CMD_RESTART, "重启服务")
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(hmenu, MF_STRING, CMD_QUIT, "退出")

            point = wintypes.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            user32.SetForegroundWindow(hwnd)
            cmd = user32.TrackPopupMenu(
                hmenu,
                TPM_RIGHTBUTTON | TPM_RETURNCMD | TPM_NONOTIFY,
                point.x,
                point.y,
                0,
                hwnd,
                None,
            )

            if cmd == CMD_OPEN and self.on_open:
                self.on_open()
            elif cmd == CMD_RESTART and self.on_restart:
                self.on_restart()
            elif cmd == CMD_QUIT and self.on_quit:
                self.on_quit()
        finally:
            user32.DestroyMenu(hmenu)
