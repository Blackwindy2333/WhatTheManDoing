"""API tests for report auth and read-only viewer endpoints (TestClient only)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from server.app.config import ServerConfig
from server.app.main import create_app
from server.app.storage import Storage


def make_client(tmp_path: Path, *, viewer_token: str = "") -> TestClient:
    cfg = ServerConfig(
        host="127.0.0.1",
        port=8765,
        db_path=str(tmp_path / "test.db"),
        viewer_token=viewer_token,
        agent_tokens={"my-pc": "dev-token"},
        offline_after_seconds=30,
        history_limit=50,
        cors_origins=["*"],
    )
    app = create_app(cfg, Storage(cfg.db_path))
    return TestClient(app)


def sample_body(title: str = "work.md") -> dict:
    return {
        "device_id": "my-pc",
        "device_name": "My PC",
        "status": "active",
        "timestamp": "2026-01-01T00:00:00Z",
        "app": {
            "process_name": "Code.exe",
            "display_name": "Visual Studio Code",
            "window_title": title,
        },
    }


def test_health(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    assert res.json()["code"] == 0
    assert res.json()["data"]["status"] == "ok"


def test_report_requires_valid_agent_token(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    res = client.post("/api/v1/report", json=sample_body())
    assert res.status_code == 401
    assert res.json()["code"] == 40100

    res = client.post(
        "/api/v1/report",
        json=sample_body(),
        headers={"Authorization": "Bearer wrong"},
    )
    assert res.status_code == 401

    res = client.post(
        "/api/v1/report",
        json=sample_body(),
        headers={"Authorization": "Bearer dev-token"},
    )
    assert res.status_code == 200
    assert res.json()["code"] == 0
    assert res.json()["data"]["ok"] is True


def test_report_unknown_device_id(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    body = sample_body()
    body["device_id"] = "nope"
    res = client.post("/api/v1/report", json=body, headers={"Authorization": "Bearer dev-token"})
    assert res.status_code == 401


def test_viewer_devices_hides_window_title(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post("/api/v1/report", json=sample_body("TOP SECRET"), headers={"Authorization": "Bearer dev-token"})
    res = client.get("/api/v1/devices")
    assert res.status_code == 200
    devices = res.json()["data"]["devices"]
    assert len(devices) == 1
    assert devices[0]["device_id"] == "my-pc"
    assert devices[0]["app"]["window_title"] is None
    assert devices[0]["app"]["display_name"] == "Visual Studio Code"


def test_viewer_history_hides_window_title(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post("/api/v1/report", json=sample_body("TOP SECRET"), headers={"Authorization": "Bearer dev-token"})
    res = client.get("/api/v1/devices/my-pc/history")
    assert res.status_code == 200
    hist = res.json()["data"]["history"]
    assert hist[0]["window_title"] is None


def test_viewer_token_optional(tmp_path: Path) -> None:
    open_client = make_client(tmp_path, viewer_token="")
    open_client.post("/api/v1/report", json=sample_body(), headers={"Authorization": "Bearer dev-token"})
    assert open_client.get("/api/v1/devices").status_code == 200

    locked = make_client(tmp_path, viewer_token="read-token")
    locked.post("/api/v1/report", json=sample_body(), headers={"Authorization": "Bearer dev-token"})
    assert locked.get("/api/v1/devices").status_code == 401
    assert locked.get("/api/v1/devices", headers={"Authorization": "Bearer read-token"}).status_code == 200


def test_get_device_404(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    res = client.get("/api/v1/devices/missing")
    assert res.status_code == 404
    assert res.json()["code"] == 40400


def test_viewer_endpoints_are_read_only(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.post("/api/v1/report", json=sample_body(), headers={"Authorization": "Bearer dev-token"})
    # No mutating viewer routes exist for privacy/config
    assert client.post("/api/v1/devices", json={}).status_code in (404, 405)
    assert client.put("/api/v1/devices/my-pc", json={}).status_code in (404, 405)
    assert client.delete("/api/v1/devices/my-pc").status_code in (404, 405)
    assert client.patch("/api/v1/devices/my-pc", json={}).status_code in (404, 405)
