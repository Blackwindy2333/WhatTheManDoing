"""Build and send foreground-status reports to the backend."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from agent.config import AgentConfig
from agent.foreground import ForegroundInfo, is_blacklisted, resolve_display_name
from logconfig import get_logger

log = get_logger("reporter")

Status = str  # active | paused | idle | locked


@dataclass(frozen=True)
class ReportResult:
    """Outcome of one POST /report attempt."""

    ok: bool
    status_code: int | None = None
    error: str | None = None
    url: str = ""

    def __bool__(self) -> bool:
        return self.ok


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
) -> ReportResult:
    """POST payload to the backend. Always returns ReportResult with a clear error."""
    url = report_url(config)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {config.device_token}",
    }

    if http_post is not None:
        try:
            status = int(http_post(url, payload, headers))
        except Exception as exc:  # noqa: BLE001
            log.warning("report via http_post failed url=%s err=%s", url, exc)
            return ReportResult(ok=False, error=f"report exception: {exc}", url=url)
        if 200 <= status < 300:
            log.debug("report ok status=%s url=%s", status, url)
            return ReportResult(ok=True, status_code=status, url=url)
        err = _friendly_http_error(status, url)
        log.warning("report rejected status=%s url=%s", status, url)
        return ReportResult(ok=False, status_code=status, error=err, url=url)

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = int(getattr(resp, "status", 200) or 200)
            if 200 <= status < 300:
                log.debug("report ok status=%s url=%s", status, url)
                return ReportResult(ok=True, status_code=status, url=url)
            err = _friendly_http_error(status, url)
            log.warning("report status=%s url=%s", status, url)
            return ReportResult(ok=False, status_code=status, error=err, url=url)
    except urllib.error.HTTPError as exc:
        code = int(exc.code)
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
        except Exception:
            detail = ""
        if code == 401:
            err = (
                f"鉴权失败 (401)：device_token 与服务端 agent_tokens 不匹配。url={url} {detail}"
            )
        elif code == 429:
            err = f"触发限流 (429)。url={url} {detail}"
        elif code == 400:
            err = f"请求被拒绝 (400)：{detail or 'bad request'}"
        else:
            err = _friendly_http_error(code, url) + (f" {detail}" if detail else "")
        log.warning("report HTTP error code=%s url=%s detail=%s", code, url, detail)
        return ReportResult(ok=False, status_code=code, error=err, url=url)
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        err = (
            f"无法连接服务端 {url}：{reason}。"
            f"请确认已启动 API 服务（python -m server.app.main），"
            f"且 api_base_url / 端口正确。"
        )
        log.warning("report unreachable url=%s reason=%s", url, reason)
        return ReportResult(ok=False, error=err, url=url)
    except TimeoutError:
        err = f"上报超时（{timeout}s）：{url}"
        log.warning("report timeout url=%s", url)
        return ReportResult(ok=False, error=err, url=url)
    except OSError as exc:
        err = f"网络错误：{exc}（url={url}）"
        log.warning("report OSError url=%s err=%s", url, exc)
        return ReportResult(ok=False, error=err, url=url)


def _friendly_http_error(status: int, url: str) -> str:
    return f"HTTP {status} from {url}"
