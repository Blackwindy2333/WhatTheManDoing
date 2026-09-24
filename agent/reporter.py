"""Build and send foreground-status reports to the backend."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable

from agent.config import AgentConfig
from agent.foreground import ForegroundInfo, is_blacklisted, resolve_display_name

Status = str  # active | paused | idle | locked


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_payload(
    config: AgentConfig,
    info: ForegroundInfo | None,
    status: Status = "active",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Create the JSON body posted to POST /api/v1/report.

    Privacy: window_title is included only when config.report_window_title is True.
    Blacklisted apps are replaced with a redacted marker.
    """
    payload: dict[str, Any] = {
        "device_id": config.device_id,
        "device_name": config.device_name,
        "status": status,
        "timestamp": timestamp or utc_now_iso(),
        "app": None,
    }

    if status == "paused" or info is None:
        return payload

    if is_blacklisted(info.process_name, config.app_name_blacklist):
        payload["app"] = {
            "process_name": "redacted",
            "display_name": "Redacted",
            "window_title": None,
        }
        return payload

    display_name = resolve_display_name(info.process_name, config.display_name_map)
    app: dict[str, Any] = {
        "process_name": info.process_name,
        "display_name": display_name,
        "window_title": None,
    }
    if config.report_window_title and info.window_title:
        app["window_title"] = info.window_title
    payload["app"] = app
    return payload


def report_url(config: AgentConfig) -> str:
    return config.api_base_url.rstrip("/") + "/report"


def send_report(
    config: AgentConfig,
    payload: dict[str, Any],
    http_post: Callable[[str, dict[str, Any], dict[str, str]], int] | None = None,
    timeout: float = 5.0,
) -> bool:
    """POST payload to the backend. Returns True on HTTP success.

    `http_post(url, json_body, headers) -> status_code` is a test seam.
    """
    url = report_url(config)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.device_token}",
    }
    if http_post is not None:
        status = int(http_post(url, payload, headers))
        return 200 <= status < 300

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= int(resp.status) < 300
    except urllib.error.HTTPError as exc:
        return 200 <= exc.code < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
