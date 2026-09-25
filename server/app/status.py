"""Local status source for GET /api/v1/status (this machine's foreground app)."""

from __future__ import annotations

from typing import Any, Callable

from agent.config import AgentConfig
from agent.foreground import ForegroundError, ForegroundInfo, get_foreground_info, is_blacklisted, resolve_display_name
from agent.reporter import utc_now_iso


def build_status_payload(
    info: ForegroundInfo | None,
    *,
    device_id: str = "local",
    device_name: str = "Local",
    status: str = "active",
    config: AgentConfig | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Public status object (already privacy-filtered)."""
    app: dict[str, Any] | None = None
    if info is not None and status not in {"paused", "stopped", "idle"}:
        if config is not None and is_blacklisted(info.process_name, config.app_name_blacklist):
            app = {
                "process_name": "redacted",
                "display_name": "Redacted",
                "window_title": None,
            }
        else:
            name_map = config.display_name_map if config else {}
            show_title = bool(config.report_window_title) if config else False
            app = {
                "process_name": info.process_name,
                "display_name": resolve_display_name(info.process_name, name_map),
                "window_title": info.window_title if show_title and info.window_title else None,
            }

    return {
        "device_id": device_id,
        "device_name": device_name,
        "status": status,
        "app": app,
        "timestamp": timestamp or utc_now_iso(),
    }


def sample_local_status(
    *,
    config: AgentConfig | None = None,
    sampler: Callable[[], ForegroundInfo] | None = None,
) -> dict[str, Any]:
    """Sample this machine's foreground app right now."""
    sample = sampler or get_foreground_info
    device_id = config.device_id if config else "local"
    device_name = config.device_name if config else "Local"

    if config is not None and config.privacy_pause:
        return build_status_payload(
            None, device_id=device_id, device_name=device_name, status="paused", config=config
        )

    try:
        info = sample()
    except ForegroundError:
        return build_status_payload(
            None, device_id=device_id, device_name=device_name, status="idle", config=config
        )
    return build_status_payload(
        info, device_id=device_id, device_name=device_name, status="active", config=config
    )


def service_snapshot_to_status(
    snapshot: dict[str, Any],
    *,
    device_id: str = "local",
    device_name: str = "Local",
) -> dict[str, Any]:
    """Convert AgentService.snapshot() into the public status shape."""
    payload = snapshot.get("last_payload")
    if isinstance(payload, dict) and payload.get("app") is not None:
        app = payload.get("app")
        status = payload.get("status") or "active"
        timestamp = payload.get("timestamp") or snapshot.get("last_report_at") or utc_now_iso()
        return {
            "device_id": payload.get("device_id") or device_id,
            "device_name": payload.get("device_name") or device_name,
            "status": status if snapshot.get("running") else "stopped",
            "app": app,
            "timestamp": timestamp,
        }
    status = "stopped"
    if snapshot.get("running"):
        status = str(snapshot.get("status") or "active")
    return {
        "device_id": device_id,
        "device_name": device_name,
        "status": status,
        "app": None,
        "timestamp": snapshot.get("last_report_at") or utc_now_iso(),
    }
