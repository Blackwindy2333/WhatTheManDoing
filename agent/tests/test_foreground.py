"""Tests for foreground helpers (pure functions; Win32 is not exercised)."""

from __future__ import annotations

import pytest

from agent.foreground import (
    ForegroundError,
    ForegroundInfo,
    get_foreground_info,
    is_blacklisted,
    resolve_display_name,
)


def test_resolve_display_name_from_map() -> None:
    mapping = {"Code.exe": "Visual Studio Code", "chrome.exe": "Google Chrome"}
    assert resolve_display_name("Code.exe", mapping) == "Visual Studio Code"
    assert resolve_display_name("chrome.exe", mapping) == "Google Chrome"


def test_resolve_display_name_case_insensitive() -> None:
    mapping = {"Code.exe": "Visual Studio Code"}
    assert resolve_display_name("code.exe", mapping) == "Visual Studio Code"
    assert resolve_display_name("CODE.EXE", mapping) == "Visual Studio Code"


def test_resolve_display_name_fallback_raw() -> None:
    assert resolve_display_name("Weird.exe", {}) == "Weird.exe"
    assert resolve_display_name("", {}) == "Unknown"


def test_is_blacklisted_exact_and_exe_suffix() -> None:
    assert is_blacklisted("KeePass.exe", ["KeePass.exe"])
    assert is_blacklisted("KeePass.exe", ["KeePass"])
    assert is_blacklisted("keepass.exe", ["KeePass"])
    assert is_blacklisted("KeePass", ["KeePass.exe"])
    assert not is_blacklisted("Code.exe", ["KeePass"])
    assert not is_blacklisted("Code.exe", [])
    assert not is_blacklisted("", ["x"])
    assert not is_blacklisted("Code.exe", ["", "  "])


def test_foreground_info_frozen() -> None:
    info = ForegroundInfo(process_name="Code.exe", window_title="a.py")
    assert info.process_name == "Code.exe"
    with pytest.raises(Exception):
        info.process_name = "other"  # type: ignore[misc]


def test_get_foreground_info_non_windows_raises() -> None:
    import sys

    if sys.platform == "win32":
        pytest.skip("live capture available on Windows; unit test targets non-win guard")
    with pytest.raises(ForegroundError):
        get_foreground_info()
