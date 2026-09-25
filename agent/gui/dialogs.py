"""Close-confirmation dialog: minimize to tray vs quit (Apple-style modal)."""

from __future__ import annotations

import tkinter as tk

from agent.gui.theme import FONT_BODY, FONT_BUTTON, FONT_CAPTION, Theme, px

# Result codes
KEEP_TRAY = "tray"
QUIT = "quit"
CANCEL = "cancel"


class CloseDialog(tk.Toplevel):
    """Modal sheet: 退出时最小化到托盘 / 直接退出 / 取消."""

    def __init__(self, master: tk.Misc, theme: Theme, *, on_result) -> None:
        super().__init__(master)
        self.title("关闭窗口")
        self.resizable(False, False)
        self.transient(master)
        self.theme = theme
        self._on_result = on_result
        self._result = CANCEL

        self.configure(bg=theme.bg)
        body = tk.Frame(self, bg=theme.bg, padx=px(22), pady=px(20))
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="要退出监控控制台吗？",
            bg=theme.bg,
            fg=theme.ink,
            font=FONT_BUTTON,
        ).pack(anchor="w")
        tk.Label(
            body,
            text="最小化到系统托盘可保持后台运行；直接退出将停止采集。",
            bg=theme.bg,
            fg=theme.secondary,
            font=FONT_CAPTION,
            wraplength=px(320),
            justify="left",
        ).pack(anchor="w", pady=(px(8), px(18)))

        buttons = tk.Frame(body, bg=theme.bg)
        buttons.pack(fill="x")

        self._btn(
            buttons,
            "最小化到托盘",
            theme.accent,
            "#FFFFFF",
            lambda: self._finish(KEEP_TRAY),
        ).pack(side="left", expand=True, fill="x", padx=(0, px(8)))
        self._btn(
            buttons,
            "直接退出",
            theme.card,
            theme.ink,
            lambda: self._finish(QUIT),
        ).pack(side="left", expand=True, fill="x", padx=(0, px(8)))
        self._btn(
            buttons,
            "取消",
            theme.card,
            theme.secondary,
            lambda: self._finish(CANCEL),
        ).pack(side="left", expand=True, fill="x")

        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(CANCEL))
        self.bind("<Escape>", lambda _e: self._finish(CANCEL))
        self.grab_set()
        self.focus_force()
        # Center over parent
        self.update_idletasks()
        try:
            px_w = self.winfo_width()
            px_h = self.winfo_height()
            x = master.winfo_rootx() + (master.winfo_width() - px_w) // 2
            y = master.winfo_rooty() + (master.winfo_height() - px_h) // 2
            self.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass

    def _btn(self, parent, text, bg, fg, command):
        lbl = tk.Label(
            parent,
            text=text,
            bg=bg,
            fg=fg,
            font=FONT_BODY,
            padx=px(12),
            pady=px(10),
            cursor="hand2",
        )
        lbl.bind("<Button-1>", lambda _e: command())
        return lbl

    def _finish(self, result: str) -> None:
        self._result = result
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()
        if self._on_result:
            self._on_result(result)


def ask_close_action(master: tk.Misc, theme: Theme) -> str:
    """Blocking helper: returns KEEP_TRAY / QUIT / CANCEL."""
    result = {"value": CANCEL}
    done = {"flag": False}

    def on_result(value: str) -> None:
        result["value"] = value
        done["flag"] = True

    dlg = CloseDialog(master, theme, on_result=on_result)
    master.wait_window(dlg)
    return result["value"]
