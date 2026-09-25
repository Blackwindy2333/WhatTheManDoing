"""Tests for GUI-facing rate limit config validation."""

from __future__ import annotations

from pathlib import Path

from server.app.config import ServerConfig, ensure_config, load_config, save_config


def test_server_config_roundtrip_rate_limit(tmp_path: Path) -> None:
    path = tmp_path / "server.json"
    cfg = ensure_config(path)
    assert cfg.rate_limit_per_minute == 120
    cfg.rate_limit_per_minute = 30
    save_config(cfg, path)
    assert load_config(path).rate_limit_per_minute == 30


def test_rate_limit_bounds() -> None:
    from server.app.config import ConfigError, validate_config_dict
    import pytest

    data = ServerConfig().__dict__
    data["rate_limit_per_minute"] = 0
    with pytest.raises(ConfigError, match="rate_limit_per_minute"):
        validate_config_dict(data)

    data["rate_limit_per_minute"] = 120
    assert validate_config_dict(data).rate_limit_per_minute == 120
