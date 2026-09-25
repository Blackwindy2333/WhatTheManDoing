"""In-process agent runtime: start/stop polling and expose a status snapshot.

Used by the local GUI (and unit tests) so status updates do not require parsing logs.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from agent.config import AgentConfig
from agent.foreground import ForegroundError, ForegroundInfo, get_foreground_info
from agent.reporter import ReportResult, build_payload, send_report
from logconfig import get_logger

log = get_logger("service")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class RuntimeStats:
    running: bool = False
    ok_count: int = 0
    fail_count: int = 0
    last_error: str | None = None
    last_report_at: str | None = None
    last_payload: dict[str, Any] | None = None
    current_app: str | None = None
    current_process: str | None = None
    status: str = "stopped"
    extra: dict[str, Any] = field(default_factory=dict)

    def snapshot(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "ok_count": self.ok_count,
            "fail_count": self.fail_count,
            "last_error": self.last_error,
            "last_report_at": self.last_report_at,
            "last_payload": self.last_payload,
            "current_app": self.current_app,
            "current_process": self.current_process,
            "status": self.status,
            **self.extra,
        }


class AgentService:
    """Background poll loop with start/stop and thread-safe status."""

    def __init__(
        self,
        config: AgentConfig,
        *,
        on_update: Callable[[dict[str, Any]], None] | None = None,
        sampler: Callable[[], ForegroundInfo] | None = None,
        reporter: Callable[[AgentConfig, dict[str, Any]], ReportResult | bool] | None = None,
    ) -> None:
        self._config = config
        self._on_update = on_update
        self._sampler = sampler or get_foreground_info
        self._reporter = reporter or send_report
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()
        self._stats = RuntimeStats()

    @property
    def config(self) -> AgentConfig:
        return self._config

    def update_config(self, config: AgentConfig) -> None:
        with self._lock:
            self._config = config

    def is_running(self) -> bool:
        with self._lock:
            return self._stats.running

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._stats.snapshot()

    def start(self) -> bool:
        with self._lock:
            if self._stats.running:
                return False
            self._stop.clear()
            self._stats = RuntimeStats(running=True, status="starting")
            self._thread = threading.Thread(target=self._run, name="agent-service", daemon=True)
            self._thread.start()
            self._notify()
            return True

    def stop(self, timeout: float = 2.0) -> bool:
        self._stop.set()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)
        with self._lock:
            self._stats.running = False
            self._stats.status = "stopped"
            self._thread = None
        self._notify()
        return True

    def _notify(self) -> None:
        if self._on_update is None:
            return
        try:
            self._on_update(self.snapshot())
        except Exception:
            pass

    def _run(self) -> None:
        log.info("agent service started device_id=%s", self._config.device_id)
        while not self._stop.is_set():
            config = self._config
            interval = max(config.poll_interval_ms, 100) / 1000.0
            sample_error: str | None = None
            try:
                payload = self._build_payload(config)
            except ForegroundError as exc:
                log.warning("foreground sample failed: %s", exc)
                sample_error = str(exc)
                payload = build_payload(config, None, status="idle")
            except Exception as exc:  # noqa: BLE001 — keep loop alive
                log.exception("unexpected error while sampling foreground")
                sample_error = f"采样失败: {exc}"
                payload = build_payload(config, None, status="idle")

            # Always report (including idle/paused frames) so the server stays fresh.
            try:
                result = self._reporter(config, payload)
            except Exception as exc:  # noqa: BLE001
                log.exception("reporter raised")
                self._note_fail(f"report exception: {exc}", payload)
            else:
                if isinstance(result, ReportResult):
                    ok, err = result.ok, result.error
                else:
                    ok = bool(result)
                    err = None if ok else "report failed"
                if ok and not sample_error:
                    self._note_ok(payload)
                elif ok and sample_error:
                    self._note_fail(sample_error, payload)
                else:
                    detail = err or sample_error or "report failed"
                    log.warning("report failed: %s", detail)
                    self._note_fail(detail, payload)

            self._stop.wait(interval)

        log.info("agent service stopped device_id=%s", self._config.device_id)
        with self._lock:
            self._stats.running = False
            self._stats.status = "stopped"
        self._notify()

    def _build_payload(self, config: AgentConfig) -> dict[str, Any]:
        if config.privacy_pause:
            return build_payload(config, None, status="paused")
        info = self._sampler()
        return build_payload(config, info, status="active")

    def _note_ok(self, payload: dict[str, Any]) -> None:
        app = payload.get("app") or {}
        with self._lock:
            self._stats.ok_count += 1
            self._stats.last_error = None
            self._stats.last_report_at = payload.get("timestamp") or utc_now_iso()
            self._stats.last_payload = payload
            self._stats.current_app = app.get("display_name") if isinstance(app, dict) else None
            self._stats.current_process = app.get("process_name") if isinstance(app, dict) else None
            self._stats.status = payload.get("status") or "active"
        self._notify()

    def _note_fail(self, error: str, payload: dict[str, Any]) -> None:
        app = payload.get("app") or {}
        with self._lock:
            self._stats.fail_count += 1
            self._stats.last_error = error
            self._stats.last_payload = payload
            if isinstance(app, dict) and app:
                self._stats.current_app = app.get("display_name")
                self._stats.current_process = app.get("process_name")
            self._stats.status = payload.get("status") or "error"
        self._notify()
