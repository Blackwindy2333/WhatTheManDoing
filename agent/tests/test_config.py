"""Tests for agent configuration persistence and defaults."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.config import (
    AgentConfig,
    ConfigError,
    default_config,
    ensure_config,
    load_config,
    save_config,
    validate_config_dict,
)


def test_default_config_values() -> None:
    cfg = default_config()
    assert cfg.report_window_title is False
    assert cfg.poll_interval_ms == 1000
    assert cfg.history_limit == 50
    assert cfg.privacy_pause is False
    assert "Code.exe" in cfg.display_name_map


def test_ensure_config_creates_default_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    assert not path.exists()
    cfg = ensure_config(path)
    assert path.exists()
    assert cfg.device_id == "my-pc"
    reloaded = load_config(path)
    assert reloaded.device_id == cfg.device_id
    assert reloaded.report_window_title is False


def test_ensure_config_loads_existing_without_overwrite(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    custom = default_config()
    custom.device_id = "desk-01"
    custom.device_name = "Desk 01"
    custom.report_window_title = True
    save_config(custom, path)

    cfg = ensure_config(path)
    assert cfg.device_id == "desk-01"
    assert cfg.device_name == "Desk 01"
    assert cfg.report_window_title is True


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "config.json"
    cfg = default_config()
    cfg.app_name_blacklist = ["KeePass.exe"]
    save_config(cfg, path)
    loaded = load_config(path)
    assert loaded.app_name_blacklist == ["KeePass.exe"]
    assert loaded.display_name_map == cfg.display_name_map


def test_load_rejects_invalid_poll_interval(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    data = json.loads(json.dumps(default_config().__dict__))
    data["poll_interval_ms"] = 10
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigError, match="poll_interval_ms"):
        load_config(path)


def test_load_rejects_missing_keys(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"api_base_url": "http://x"}), encoding="utf-8")
    with pytest.raises(ConfigError, match="missing required"):
        load_config(path)


def test_validate_rejects_bool_for_int() -> None:
    data = default_config().__dict__
    data["poll_interval_ms"] = True
    with pytest.raises(ConfigError, match="poll_interval_ms"):
        validate_config_dict(data)


def test_validate_rejects_bad_blacklist() -> None:
    data = default_config().__dict__
    data["app_name_blacklist"] = [1, 2]
    with pytest.raises(ConfigError, match="app_name_blacklist"):
        validate_config_dict(data)


def test_config_is_plain_json_object() -> None:
    cfg = AgentConfig()
    assert isinstance(cfg.report_window_title, bool)
