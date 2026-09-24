"""Tests for server config bootstrap and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.app.config import ConfigError, default_config, ensure_config, load_config, save_config


def test_ensure_creates_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    cfg = ensure_config(path)
    assert path.exists()
    assert cfg.port == 8765
    assert cfg.viewer_token == ""
    assert "my-pc" in cfg.agent_tokens
    assert load_config(path).history_limit == cfg.history_limit


def test_ensure_keeps_existing(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    cfg = default_config()
    cfg.viewer_token = "read-only-token"
    cfg.agent_tokens = {"desk-01": "secret"}
    save_config(cfg, path)
    loaded = ensure_config(path)
    assert loaded.viewer_token == "read-only-token"
    assert loaded.agent_tokens["desk-01"] == "secret"


def test_invalid_port_rejected(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    data = json.loads(json.dumps(default_config().__dict__))
    data["port"] = 0
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ConfigError, match="port"):
        load_config(path)


def test_agent_tokens_must_be_strings() -> None:
    data = default_config().__dict__
    data["agent_tokens"] = {"a": 1}
    from server.app.config import validate_config_dict

    with pytest.raises(ConfigError, match="agent_tokens"):
        validate_config_dict(data)
