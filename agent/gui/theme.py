"""Apple-inspired design tokens for the local control panel."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    bg: str
    bg_elevated: str
    card: str
    card_border: str
    ink: str
    secondary: str
    accent: str
    accent_text: str
    field: str
    field_border: str
    field_focus: str
    green: str
    orange: str
    red: str
    track: str
    knob: str
    shadow: str


LIGHT = Theme(
    bg="#F5F5F7",
    bg_elevated="#FFFFFF",
    card="#FFFFFF",
    card_border="#E5E5EA",
    ink="#1D1D1F",
    secondary="#6E6E73",
    accent="#0071E3",
    accent_text="#FFFFFF",
    field="#FFFFFF",
    field_border="#D1D1D6",
    field_focus="#0071E3",
    green="#34C759",
    orange="#FF9F0A",
    red="#FF3B30",
    track="#E9E9EB",
    knob="#FFFFFF",
    shadow="#D1D1D6",
)

DARK = Theme(
    bg="#1C1C1E",
    bg_elevated="#2C2C2E",
    card="#2C2C2E",
    card_border="#3A3A3C",
    ink="#F5F5F7",
    secondary="#98989D",
    accent="#0A84FF",
    accent_text="#FFFFFF",
    field="#1C1C1E",
    field_border="#48484A",
    field_focus="#0A84FF",
    green="#30D158",
    orange="#FF9F0A",
    red="#FF453A",
    track="#39393D",
    knob="#FFFFFF",
    shadow="#111111",
)

# Type scale (optical sizing: tighter tracking on display text)
FONT_FAMILY = "Segoe UI"
FONT_DISPLAY = (FONT_FAMILY, 22, "bold")
FONT_TITLE = (FONT_FAMILY, 13, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_CAPTION = (FONT_FAMILY, 9)
FONT_MONO = ("Consolas", 9)
FONT_BUTTON = (FONT_FAMILY, 10, "bold")

RADIUS = 12
PAD = 16
CARD_PAD = 14
# Critically-damped feel for micro transitions (ms)
TICK_MS = 50
MOTION_MS = 180


def system_theme() -> Theme:
    """Prefer light; dark if user clearly runs a dark Windows mode (best-effort)."""
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return LIGHT if int(value) else DARK
    except Exception:
        return LIGHT
