"""High-DPI awareness for crisp text on Windows scaled displays.

Must be called BEFORE creating a Tk root window. Without this, Windows
bitmap-stretches the whole window and tkinter fonts look blurry.
"""

from __future__ import annotations

import sys
from typing import Any

# Windows DPI awareness context: PER_MONITOR_AWARE_V2 (Win10 1703+)
_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
_PROCESS_PER_MONITOR_DPI_AWARE = 2


def setup_dpi_awareness() -> str:
    """Best-effort DPI awareness. Returns which method was applied."""
    if sys.platform != "win32":
        return "none"

    # 1) Per-Monitor V2 — sharpest on mixed-DPI / 150%+ scaling
    try:
        import ctypes

        user32 = ctypes.windll.user32
        # BOOL SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT)
        fn = getattr(user32, "SetProcessDpiAwarenessContext", None)
        if fn is not None:
            fn(ctypes.c_void_p(_DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2))
            return "per-monitor-v2"
    except Exception:
        pass

    # 2) Per-Monitor (Win 8.1+)
    try:
        import ctypes

        shcore = ctypes.windll.shcore
        shcore.SetProcessDpiAwareness(_PROCESS_PER_MONITOR_DPI_AWARE)
        return "per-monitor"
    except Exception:
        pass

    # 3) System DPI aware (Vista+)
    try:
        import ctypes

        ctypes.windll.user32.SetProcessDPIAware()
        return "system"
    except Exception:
        pass

    return "failed"


def query_scale_factor(root: Any | None = None) -> float:
    """Return UI scale relative to 96 DPI (1.0 = 100%, 1.5 = 150%).

    Prefers a live Tk root's pixel-per-inch; falls back to Windows GetDpiForWindow
    or GetDeviceCaps; finally 1.0.
    """
    if root is not None:
        try:
            dpi = float(root.winfo_fpixels("1i"))
            if dpi > 0:
                return max(0.5, dpi / 96.0)
        except Exception:
            pass

    if sys.platform == "win32":
        try:
            import ctypes

            user32 = ctypes.windll.user32
            # UINT GetDpiForWindow(HWND) — Win10 1607+
            hwnd = 0
            get_dpi = getattr(user32, "GetDpiForWindow", None)
            if get_dpi is not None and root is not None:
                try:
                    hwnd = int(root.winfo_id())
                except Exception:
                    hwnd = 0
            if get_dpi is not None and hwnd:
                dpi = int(get_dpi(hwnd))
                if dpi > 0:
                    return max(0.5, dpi / 96.0)

            gdi32 = ctypes.windll.gdi32
            hdc = user32.GetDC(0)
            try:
                dpi = int(gdi32.GetDeviceCaps(hdc, 88))  # LOGPIXELSX
            finally:
                user32.ReleaseDC(0, hdc)
            if dpi > 0:
                return max(0.5, dpi / 96.0)
        except Exception:
            pass

    return 1.0


def apply_tk_scaling(root: Any) -> float:
    """Set tk scaling so font points map to real pixels. Returns scale factor used."""
    scale = query_scale_factor(root)
    try:
        # tk "scaling" is pixels-per-point (1.0 at 72 DPI). 96 DPI ≈ 1.333.
        dpi = float(root.winfo_fpixels("1i"))
        if dpi > 0:
            root.tk.call("tk", "scaling", dpi / 72.0)
        else:
            root.tk.call("tk", "scaling", scale * (96.0 / 72.0))
    except Exception:
        try:
            root.tk.call("tk", "scaling", scale * (96.0 / 72.0))
        except Exception:
            pass
    return scale


def scale_px(value: int | float, scale: float) -> int:
    """Scale a CSS-like pixel value for this display. Rounds to int for Tk."""
    return max(1, int(round(value * scale)))


def scaled_font(family: str, size: int | float, *styles: str, scale: float = 1.0):
    """Tkinter font tuple: size stays in points (Tk scales with dpi once aware)."""
    size_pt = max(6, int(round(size * max(scale, 0.5))))
    if styles:
        return (family, size_pt, " ".join(styles))
    return (family, size_pt)
