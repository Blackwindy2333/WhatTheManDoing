"""Agent configuration: load, validate, persist, create defaults when missing."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "config.json"

_ALLOWED_STATUS = frozenset({"active", "paused", "idle", "locked"})


class ConfigError(ValueError):
    """Raised when configuration is missing required shape or has invalid values."""


@dataclass
class AgentConfig:
    api_base_url: str = "http://127.0.0.1:8765/api/v1"
    device_id: str = "my-pc"
    device_name: str = "My PC"
    device_token: str = "change-me"
    poll_interval_ms: int = 1000
    report_window_title: bool = False
    app_name_blacklist: list[str] = field(default_factory=list)
    history_limit: int = 50
    privacy_pause: bool = False
    display_name_map: dict[str, str] = field(default_factory=dict)


def default_config() -> AgentConfig:
    return AgentConfig(
        display_name_map={
            "Code.exe": "Visual Studio Code",
            "chrome.exe": "Google Chrome",
            "firefox.exe": "Mozilla Firefox",
            "msedge.exe": "Microsoft Edge",
            "explorer.exe": "File Explorer",
            "WindowsTerminal.exe": "Windows Terminal",
            "ApplicationFrameHost.exe": "UWP App",
        }
    )


def _require_type(data: dict[str, Any], key: str, expected: type) -> Any:
    if key not in data:
        raise ConfigError(f"missing required config key: {key}")
    value = data[key]
    if expected is int and isinstance(value, bool):
        raise ConfigError(f"config key {key!r} must be int, got bool")
    if not isinstance(value, expected):
        raise ConfigError(f"config key {key!r} must be {expected.__name__}, got {type(value).__name__}")
    return value


def validate_config_dict(data: dict[str, Any]) -> AgentConfig:
    if not isinstance(data, dict):
        raise ConfigError("config root must be a JSON object")

    poll_interval_ms = _require_type(data, "poll_interval_ms", int)
    if poll_interval_ms < 100:
        raise ConfigError("poll_interval_ms must be >= 100")

    history_limit = _require_type(data, "history_limit", int)
    if history_limit < 1 or history_limit > 1000:
        raise ConfigError("history_limit must be between 1 and 1000")

    report_window_title = _require_type(data, "report_window_title", bool)
    privacy_pause = _require_type(data, "privacy_pause", bool)

    blacklist = data.get("app_name_blacklist", [])
    if not isinstance(blacklist, list) or not all(isinstance(x, str) for x in blacklist):
        raise ConfigError("app_name_blacklist must be a list of strings")

    name_map = data.get("display_name_map", {})
    if not isinstance(name_map, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in name_map.items()
    ):
        raise ConfigError("display_name_map must be a string-to-string object")

    return AgentConfig(
        api_base_url=_require_type(data, "api_base_url", str),
        device_id=_require_type(data, "device_id", str),
        device_name=_require_type(data, "device_name", str),
        device_token=_require_type(data, "device_token", str),
        poll_interval_ms=poll_interval_ms,
        report_window_title=report_window_title,
        app_name_blacklist=list(blacklist),
        history_limit=history_limit,
        privacy_pause=privacy_pause,
        display_name_map=dict(name_map),
    )


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> AgentConfig:
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return validate_config_dict(data)


def save_config(config: AgentConfig, path: Path | str = DEFAULT_CONFIG_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(config)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def ensure_config(path: Path | str = DEFAULT_CONFIG_PATH) -> AgentConfig:
    """Load config from path; create with defaults when missing. Persisted settings live here."""
    path = Path(path)
    if path.exists():
        return load_config(path)
    config = default_config()
    save_config(config, path)
    return config
