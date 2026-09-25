"""Tests for close-dialog result codes and tray menu wiring (no live tray)."""

from __future__ import annotations

import sys

import pytest

from agent.gui.dialogs import CANCEL, KEEP_TRAY, QUIT


def test_close_result_codes_are_distinct() -> None:
    assert len({KEEP_TRAY, QUIT, CANCEL}) == 3
    assert KEEP_TRAY == "tray"
    assert QUIT == "quit"
    assert CANCEL == "cancel"


def test_tray_menu_command_ids() -> None:
    from agent.gui import tray

    assert len({tray.CMD_OPEN, tray.CMD_RESTART, tray.CMD_QUIT}) == 3


def test_tray_icon_requires_windows() -> None:
    if sys.platform == "win32":
        pytest.skip("construction is allowed on Windows")
    from agent.gui.tray import TrayIcon

    with pytest.raises(RuntimeError):
        TrayIcon(on_open=lambda: None)


def test_tray_callbacks_can_be_assigned() -> None:
    if sys.platform != "win32":
        pytest.skip("TrayIcon is Windows-only")
    from agent.gui.tray import TrayIcon

    calls = {"open": 0, "restart": 0, "quit": 0}
    icon = TrayIcon(
        on_open=lambda: calls.__setitem__("open", calls["open"] + 1),
        on_restart=lambda: calls.__setitem__("restart", calls["restart"] + 1),
        on_quit=lambda: calls.__setitem__("quit", calls["quit"] + 1),
    )
    # Do not start the real message loop in unit tests — just verify wiring.
    assert icon.on_open is not None
    assert icon.on_restart is not None
    assert icon.on_quit is not None
    icon.on_open()
    icon.on_restart()
    icon.on_quit()
    assert calls == {"open": 1, "restart": 1, "quit": 1}


def test_notify_icondata_struct_exists() -> None:
    if sys.platform != "win32":
        pytest.skip("Win32 struct")
    from agent.gui.tray import _notify_icondata_cls

    cls = _notify_icondata_cls()
    import ctypes

    assert ctypes.sizeof(cls) > 0
