"""Server configuration: load, validate, persist, create defaults when missing."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config.json"


class ConfigError(ValueError):
    """Raised when server configuration is invalid."""


@dataclass
class ServerConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    db_path: str = "server/data/monitor.db"
    viewer_token: str = ""
    agent_tokens: dict[str, str] = field(default_factory=lambda: {"my-pc": "change-me"})
    offline_after_seconds: int = 30
    history_limit: int = 50
    cors_origins: list[str] = field(default_factory=lambda: ["*"])


def default_config() -> ServerConfig:
    return ServerConfig()


def _require_type(data: dict[str, Any], key: str, expected: type) -> Any:
    if key not in data:
        raise ConfigError(f"missing required config key: {key}")
    value = data[key]
    if expected is int and isinstance(value, bool):
        raise ConfigError(f"config key {key!r} must be int, got bool")
    if not isinstance(value, expected):
        raise ConfigError(f"config key {key!r} must be {expected.__name__}, got {type(value).__name__}")
    return value


def validate_config_dict(data: dict[str, Any]) -> ServerConfig:
    if not isinstance(data, dict):
        raise ConfigError("config root must be a JSON object")

    port = _require_type(data, "port", int)
    if not (1 <= port <= 65535):
        raise ConfigError("port must be between 1 and 65535")

    offline_after_seconds = _require_type(data, "offline_after_seconds", int)
    if offline_after_seconds < 1:
        raise ConfigError("offline_after_seconds must be >= 1")

    history_limit = _require_type(data, "history_limit", int)
    if history_limit < 1 or history_limit > 1000:
        raise ConfigError("history_limit must be between 1 and 1000")

    agent_tokens = data.get("agent_tokens", {})
    if not isinstance(agent_tokens, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in agent_tokens.items()
    ):
        raise ConfigError("agent_tokens must be a string-to-string object")

    cors_origins = data.get("cors_origins", ["*"])
    if not isinstance(cors_origins, list) or not all(isinstance(x, str) for x in cors_origins):
        raise ConfigError("cors_origins must be a list of strings")

    return ServerConfig(
        host=_require_type(data, "host", str),
        port=port,
        db_path=_require_type(data, "db_path", str),
        viewer_token=_require_type(data, "viewer_token", str),
        agent_tokens=dict(agent_tokens),
        offline_after_seconds=offline_after_seconds,
        history_limit=history_limit,
        cors_origins=list(cors_origins),
    )


def load_config(path: Path | str = DEFAULT_CONFIG_PATH) -> ServerConfig:
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return validate_config_dict(data)


def save_config(config: ServerConfig, path: Path | str = DEFAULT_CONFIG_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(asdict(config), fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def ensure_config(path: Path | str = DEFAULT_CONFIG_PATH) -> ServerConfig:
    """Load config from path; create with defaults when missing."""
    path = Path(path)
    if path.exists():
        return load_config(path)
    config = default_config()
    save_config(config, path)
    return config
