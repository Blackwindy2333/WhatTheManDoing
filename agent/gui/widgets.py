"""Reusable Apple-style tkinter widgets (cards, buttons, toggles, fields)."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from agent.gui.theme import (
    FONT_BODY,
    FONT_BUTTON,
    FONT_CAPTION,
    FONT_TITLE,
    Theme,
)


class Card(tk.Frame):
    """Elevated surface with hairline border (material weight = depth)."""

    def __init__(self, master: tk.Misc, theme: Theme, **kwargs) -> None:
        super().__init__(
            master,
            bg=theme.card,
            highlightthickness=1,
            highlightbackground=theme.card_border,
            padx=16,
            pady=14,
            **kwargs,
        )


class SectionLabel(tk.Label):
    def __init__(self, master: tk.Misc, theme: Theme, text: str) -> None:
        super().__init__(
            master,
            text=text,
            bg=theme.bg,
            fg=theme.secondary,
            font=FONT_CAPTION,
            anchor="w",
        )


class DisplayLabel(tk.Label):
    def __init__(self, master: tk.Misc, theme: Theme, text: str = "", size: int = 22) -> None:
        super().__init__(
            master,
            text=text,
            bg=theme.card,
            fg=theme.ink,
            font=(FONT_TITLE[0], size, "bold"),
            anchor="w",
            justify="left",
        )


class BodyLabel(tk.Label):
    def __init__(self, master: tk.Misc, theme: Theme, text: str = "", *, on_card: bool = True) -> None:
        super().__init__(
            master,
            text=text,
            bg=theme.card if on_card else theme.bg,
            fg=theme.ink,
            font=FONT_BODY,
            anchor="w",
            justify="left",
        )


class CaptionLabel(tk.Label):
    def __init__(self, master: tk.Misc, theme: Theme, text: str = "", *, on_card: bool = True) -> None:
        super().__init__(
            master,
            text=text,
            bg=theme.card if on_card else theme.bg,
            fg=theme.secondary,
            font=FONT_CAPTION,
            anchor="w",
            justify="left",
        )


class LabeledEntry(tk.Frame):
    """Label above a flat field; focus ring uses accent color."""

    def __init__(
        self,
        master: tk.Misc,
        theme: Theme,
        label: str,
        *,
        show: str | None = None,
        width: int = 36,
    ) -> None:
        super().__init__(master, bg=theme.card)
        self.theme = theme
        self._label = tk.Label(self, text=label, bg=theme.card, fg=theme.secondary, font=FONT_CAPTION, anchor="w")
        self._label.pack(fill="x")
        self.var = tk.StringVar()
        self.entry = tk.Entry(
            self,
            textvariable=self.var,
            font=FONT_BODY,
            bg=theme.field,
            fg=theme.ink,
            insertbackground=theme.ink,
            relief="flat",
            highlightthickness=1,
            highlightbackground=theme.field_border,
            highlightcolor=theme.field_focus,
            show=show or "",
            width=width,
        )
        self.entry.pack(fill="x", pady=(4, 0), ipady=6)

    def get(self) -> str:
        return self.var.get()

    def set(self, value: str) -> None:
        self.var.set(value)


class Toggle(tk.Frame):
    """iOS-like switch. Pointer-down commits intent with instant color response."""

    def __init__(
        self,
        master: tk.Misc,
        theme: Theme,
        *,
        command: Callable[[bool], None] | None = None,
        on: bool = False,
    ) -> None:
        super().__init__(master, bg=theme.card)
        self.theme = theme
        self._on = bool(on)
        self._command = command
        self._width = 46
        self._height = 28
        self.canvas = tk.Canvas(
            self,
            width=self._width,
            height=self._height,
            bg=theme.card,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self._on_click)
        self._draw(self._on)

    def _draw(self, on: bool) -> None:
        c = self.canvas
        t = self.theme
        c.delete("all")
        c.configure(bg=t.card)
        if on:
            track = t.green
        else:
            track = t.track
        c.create_oval(2, 2, self._height - 2, self._height - 2, fill=track, outline=track)
        c.create_oval(
            self._width - self._height + 2,
            2,
            self._width - 2,
            self._height - 2,
            fill=track,
            outline=track,
        )
        c.create_rectangle(
            self._height / 2,
            2,
            self._width - self._height / 2,
            self._height - 2,
            fill=track,
            outline=track,
        )
        pad = 3
        if on:
            x0 = self._width - self._height + pad
        else:
            x0 = pad
        y0 = pad
        x1 = x0 + self._height - pad * 2
        y1 = self._height - pad
        c.create_oval(x0, y0, x1, y1, fill=t.knob, outline=t.knob)

    def _on_click(self, _event=None) -> None:
        self.set(not self._on, fire=True)

    def get(self) -> bool:
        return self._on

    def set(self, value: bool, *, fire: bool = False) -> None:
        value = bool(value)
        changed = value != self._on
        self._on = value
        self._draw(self._on)
        if fire and changed and self._command:
            self._command(self._on)


class Pill(tk.Frame):
    """Small status capsule (online / running / error)."""

    def __init__(self, master: tk.Misc, theme: Theme, text: str = "") -> None:
        super().__init__(master, bg=theme.bg_elevated, padx=10, pady=6)
        self.theme = theme
        self.dot = tk.Canvas(self, width=10, height=10, bg=theme.bg_elevated, highlightthickness=0)
        self.dot.pack(side="left", padx=(0, 8))
        self.label = tk.Label(
            self,
            text=text,
            bg=theme.bg_elevated,
            fg=theme.ink,
            font=FONT_BODY,
        )
        self.label.pack(side="left")

    def set_state(self, text: str, color: str) -> None:
        self.label.configure(text=text)
        self.dot.delete("all")
        self.dot.create_oval(1, 1, 9, 9, fill=color, outline=color)


class AppleButton(tk.Frame):
    """Filled primary / quiet secondary button with press feedback on pointer-down."""

    def __init__(
        self,
        master: tk.Misc,
        theme: Theme,
        text: str,
        *,
        kind: str = "primary",
        command: Callable[[], None] | None = None,
    ) -> None:
        bg = theme.bg
        super().__init__(master, bg=bg)
        self.theme = theme
        self.kind = kind
        self.command = command
        self._enabled = True
        self._bg = theme.accent if kind == "primary" else theme.card
        self._bg_active = "#0060C0" if kind == "primary" and theme.accent == "#0071E3" else theme.field_border
        if kind == "secondary":
            self._bg_active = theme.field_border
        self._fg = theme.accent_text if kind == "primary" else theme.accent
        self.label = tk.Label(
            self,
            text=text,
            bg=self._bg,
            fg=self._fg,
            font=FONT_BUTTON,
            padx=18,
            pady=10,
            cursor="hand2",
        )
        self.label.pack(fill="x", expand=True)
        for widget in (self, self.label):
            widget.bind("<Button-1>", self._press)
            widget.bind("<ButtonRelease-1>", self._release)

    def _press(self, _event=None) -> None:
        if not self._enabled:
            return
        self.label.configure(bg=self._bg_active)

    def _release(self, _event=None) -> None:
        if not self._enabled:
            return
        self.label.configure(bg=self._bg)
        if self.command:
            self.command()

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if enabled:
            self.label.configure(bg=self._bg, fg=self._fg, cursor="hand2")
        else:
            self.label.configure(bg=self.theme.track, fg=self.theme.secondary, cursor="arrow")

    def set_text(self, text: str) -> None:
        self.label.configure(text=text)


class StatusPulse(tk.Frame):
    """Compact live stats row."""

    def __init__(self, master: tk.Misc, theme: Theme) -> None:
        super().__init__(master, bg=theme.card)
        self.theme = theme
        self.ok_label = CaptionLabel(self, theme, "成功 0")
        self.fail_label = CaptionLabel(self, theme, "失败 0")
        self.time_label = CaptionLabel(self, theme, "尚未上报")
        self.ok_label.pack(side="left")
        self.fail_label.pack(side="left", padx=(12, 0))
        self.time_label.pack(side="right")

    def update_stats(self, ok: int, fail: int, last_at: str | None) -> None:
        self.ok_label.configure(text=f"成功 {ok}")
        self.fail_label.configure(text=f"失败 {fail}")
        self.time_label.configure(text=f"上次 {last_at}" if last_at else "尚未上报")
