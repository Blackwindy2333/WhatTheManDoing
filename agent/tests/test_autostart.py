"""Tests for autostart registry helpers (winreg mocked)."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from agent import autostart


def _install_fake_winreg(monkeypatch: pytest.MonkeyPatch, store: dict[str, str]) -> types.ModuleType:
    class _Key:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

    def OpenKey(root, path, reserved=0, access=0):
        return _Key()

    def QueryValueEx(key, name):
        if name not in store:
            raise FileNotFoundError(name)
        return store[name], 1

    def SetValueEx(key, name, reserved, kind, value):
        store[name] = value

    def DeleteValue(key, name):
        if name not in store:
            raise FileNotFoundError(name)
        del store[name]

    fake = types.ModuleType("winreg")
    fake.HKEY_CURRENT_USER = 1
    fake.KEY_READ = 2
    fake.KEY_SET_VALUE = 4
    fake.REG_SZ = 1
    fake.OpenKey = OpenKey
    fake.QueryValueEx = QueryValueEx
    fake.SetValueEx = SetValueEx
    fake.DeleteValue = DeleteValue
    monkeypatch.setitem(sys.modules, "winreg", fake)
    return fake


def test_default_command_uses_python_m_agent_gui() -> None:
    cmd = autostart.default_command()
    assert "-m agent.gui" in cmd
    assert cmd.startswith('"')


@pytest.mark.skipif(sys.platform != "win32", reason="autostart targets Windows")
def test_enable_disable_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    store: dict[str, str] = {}
    _install_fake_winreg(monkeypatch, store)
    assert autostart.is_enabled() is False
    assert autostart.current_command() is None

    cmd = autostart.enable(' "C:\\Python\\pythonw.exe" -m agent.gui ')
    assert autostart.is_enabled() is True
    assert autostart.current_command() == cmd
    assert autostart.is_enabled(command=cmd) is True

    assert autostart.disable() is True
    assert autostart.is_enabled() is False
    assert autostart.disable() is False


@pytest.mark.skipif(sys.platform != "win32", reason="autostart targets Windows")
def test_is_enabled_with_matching_command(monkeypatch: pytest.MonkeyPatch) -> None:
    store = {autostart.APP_NAME: "pythonw.exe -m agent.gui"}
    _install_fake_winreg(monkeypatch, store)
    assert autostart.is_enabled() is True
    assert autostart.is_enabled("pythonw.exe -m agent.gui") is True
    assert autostart.is_enabled("other") is False
