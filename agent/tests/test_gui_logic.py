"""Tests for control-panel form mapping and service integration (no GUI mainloop)."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.config import ensure_config, load_config
from agent.service import AgentService
from agent.foreground import ForegroundInfo


def test_form_validation_via_config_dict() -> None:
    """Mirrors ControlPanel._form_to_config validation rules."""
    from agent.config import validate_config_dict

    data = {
        "api_base_url": "http://127.0.0.1:8765/api/v1",
        "device_id": "desk-01",
        "device_name": "Desk 01",
        "device_token": "secret",
        "poll_interval_ms": 1500,
        "report_window_title": True,
        "app_name_blacklist": ["KeePass.exe"],
        "history_limit": 50,
        "privacy_pause": False,
        "display_name_map": {},
    }
    cfg = validate_config_dict(data)
    assert cfg.device_id == "desk-01"
    assert cfg.report_window_title is True
    assert cfg.app_name_blacklist == ["KeePass.exe"]

    bad = dict(data)
    bad["poll_interval_ms"] = "fast"
    with pytest.raises(Exception):
        validate_config_dict(bad)


def test_save_config_roundtrip_for_gui(tmp_path: Path) -> None:
    from agent.config import default_config, save_config

    path = tmp_path / "agent-config.json"
    cfg = default_config()
    cfg.device_name = "Living Room PC"
    cfg.privacy_pause = True
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.device_name == "Living Room PC"
    assert loaded.privacy_pause is True


def test_service_accepts_config_updates_like_gui_save() -> None:
    from agent.config import default_config

    cfg = default_config()
    cfg.poll_interval_ms = 100
    cfg.device_name = "Before"
    reports = []
    svc = AgentService(
        cfg,
        sampler=lambda: ForegroundInfo(process_name="Code.exe", window_title="x"),
        reporter=lambda c, p: reports.append(p) or True,
    )
    updated = default_config()
    updated.poll_interval_ms = 100
    updated.device_name = "After"
    updated.privacy_pause = True
    svc.update_config(updated)
    svc.start()
    import time

    deadline = time.time() + 2
    while time.time() < deadline and not reports:
        time.sleep(0.02)
    svc.stop()
    assert reports
    assert reports[0]["device_name"] == "After"
    assert reports[0]["status"] == "paused"


def test_ensure_config_path_used_by_gui(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    cfg = ensure_config(path)
    assert path.exists()
    assert cfg.report_window_title is False
