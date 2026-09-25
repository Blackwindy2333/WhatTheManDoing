"""Tests for high-DPI helpers (no GUI mainloop required)."""

from __future__ import annotations

from agent.gui.dpi import scale_px, scaled_font, setup_dpi_awareness
from agent.gui import theme


def test_setup_dpi_awareness_returns_string() -> None:
    method = setup_dpi_awareness()
    assert isinstance(method, str)
    assert method in {"none", "per-monitor-v2", "per-monitor", "system", "failed"}


def test_scale_px_rounds_and_clamps() -> None:
    assert scale_px(10, 1.0) == 10
    assert scale_px(10, 1.5) == 15
    assert scale_px(10, 2.0) == 20
    assert scale_px(1, 0.5) == 1
    assert scale_px(0, 1.0) >= 1


def test_scaled_font_uses_points() -> None:
    font = scaled_font("Segoe UI", 10, "bold", scale=1.0)
    assert font == ("Segoe UI", 10, "bold")
    font2 = scaled_font("Segoe UI", 10, scale=1.0)
    assert font2 == ("Segoe UI", 10)


def test_theme_px_uses_runtime_scale() -> None:
    theme.set_ui_scale(1.0)
    assert theme.px(10) == 10
    assert theme.ui_scale() == 1.0
    theme.set_ui_scale(1.5)
    assert theme.px(10) == 15
    assert theme.px(2) == 3
    theme.set_ui_scale(1.0)  # restore


def test_theme_has_point_fonts() -> None:
    # Tuple form: (family, size) or (family, size, style) — size is points
    assert theme.FONT_BODY[1] == 10
    assert theme.FONT_TITLE[1] == 13
    assert theme.FONT_HINT[1] == 8
