"""Windows start-with-Windows (HKCU Run key) helpers. Stdlib-only."""

from __future__ import annotations

import sys
from pathlib import Path

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "WhatTheManDoingAgent"


class AutostartError(RuntimeError):
    """Raised when autostart registration fails."""


def _require_windows() -> None:
    if sys.platform != "win32":
        raise AutostartError("autostart is only supported on Windows")


def default_command() -> str:
    """Command registered at login: show the local GUI via pythonw (no console)."""
    exe = Path(sys.executable)
    # Prefer pythonw so a console window does not flash at startup.
    pythonw = exe.with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else exe
    return f'"{interpreter}" -m agent.gui'


def is_enabled(command: str | None = None) -> bool:
    _require_windows()
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise AutostartError(f"cannot read Run key: {exc}") from exc
    if command is None:
        return True
    return str(value).strip() == command.strip()


def current_command() -> str | None:
    _require_windows()
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
        return str(value)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise AutostartError(f"cannot read Run key: {exc}") from exc


def enable(command: str | None = None) -> str:
    """Write the Run key. Returns the registered command."""
    _require_windows()
    import winreg

    cmd = command or default_command()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
    except OSError as exc:
        raise AutostartError(f"cannot write Run key: {exc}") from exc
    return cmd


def disable() -> bool:
    """Remove the Run value. Returns True if something was removed."""
    _require_windows()
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, APP_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise AutostartError(f"cannot delete Run value: {exc}") from exc
