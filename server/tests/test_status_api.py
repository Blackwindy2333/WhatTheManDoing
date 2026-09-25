"""Tests for local status API and rate limiting (TestClient only)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent.config import default_config
from agent.foreground import ForegroundInfo
from server.app.config import ServerConfig
from server.app.main import create_app
from server.app.ratelimit import GlobalRateLimiter
from server.app.storage import Storage


def make_client(tmp_path: Path, *, limit: int = 100, status=None) -> TestClient:
    cfg = ServerConfig(
        host="127.0.0.1",
        port=8765,
        db_path=str(tmp_path / "t.db"),
        viewer_token="",
        agent_tokens={"my-pc": "dev-token"},
        rate_limit_per_minute=limit,
    )
    app = create_app(
        cfg,
        Storage(cfg.db_path),
        agent_config=default_config(),
        status_provider=status,
        limiter=GlobalRateLimiter(limit),
    )
    return TestClient(app)


def test_health_envelope(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 0
    assert body["message"] == "ok"
    assert body["data"]["status"] == "ok"
    assert "X-RateLimit-Limit" in res.headers


def test_status_envelope_and_privacy(tmp_path: Path) -> None:
    def provider():
        return {
            "device_id": "my-pc",
            "device_name": "My PC",
            "status": "active",
            "app": {
                "process_name": "Code.exe",
                "display_name": "Visual Studio Code",
                "window_title": None,
            },
            "timestamp": "2026-01-01T00:00:00Z",
        }

    client = make_client(tmp_path, status=provider)
    res = client.get("/api/v1/status")
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 0
    assert body["data"]["app"]["process_name"] == "Code.exe"
    assert body["data"]["app"]["window_title"] is None


def test_status_without_provider_samples(tmp_path: Path) -> None:
    # On Windows this may succeed live; on non-Windows returns idle.
    client = make_client(tmp_path)
    res = client.get("/api/v1/status")
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == 0
    assert "status" in body["data"]


def test_rate_limit_returns_429_envelope(tmp_path: Path) -> None:
    client = make_client(tmp_path, limit=3)
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    res = client.get("/api/v1/health")
    assert res.status_code == 429
    body = res.json()
    assert body["code"] == 42900
    assert body["data"] is None
    assert res.headers.get("Retry-After")


def test_report_and_devices_envelope(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    payload = {
        "device_id": "my-pc",
        "device_name": "My PC",
        "status": "active",
        "timestamp": "2026-01-01T00:00:00Z",
        "app": {"process_name": "Code.exe", "display_name": "Visual Studio Code", "window_title": "SECRET"},
    }
    res = client.post("/api/v1/report", json=payload, headers={"Authorization": "Bearer dev-token"})
    assert res.status_code == 200
    assert res.json()["code"] == 0

    res = client.get("/api/v1/devices")
    body = res.json()
    assert body["code"] == 0
    assert body["data"]["devices"][0]["app"]["window_title"] is None

    res = client.get("/api/v1/devices/missing")
    assert res.status_code == 404
    assert res.json()["code"] == 40400


def test_report_unauthorized_envelope(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    res = client.post("/api/v1/report", json={"device_id": "my-pc"})
    assert res.status_code == 401
    assert res.json()["code"] == 40100
