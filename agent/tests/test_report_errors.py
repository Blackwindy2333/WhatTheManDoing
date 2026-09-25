"""Tests for ReportResult details and service error propagation."""

from __future__ import annotations

import time

from agent.config import default_config
from agent.foreground import ForegroundInfo
from agent.reporter import ReportResult, send_report
from agent.service import AgentService


def test_send_report_http_post_seam_ok() -> None:
    cfg = default_config()
    res = send_report(cfg, {"device_id": "my-pc"}, http_post=lambda *a: 201)
    assert res.ok is True
    assert res.status_code == 201
    assert bool(res) is True


def test_send_report_http_post_seam_unauthorized() -> None:
    cfg = default_config()
    res = send_report(cfg, {"device_id": "my-pc"}, http_post=lambda *a: 401)
    assert res.ok is False
    assert res.status_code == 401
    assert res.error and "401" in res.error


def test_send_report_http_post_seam_exception() -> None:
    cfg = default_config()

    def boom(*_a):
        raise RuntimeError("connection refused")

    res = send_report(cfg, {"device_id": "my-pc"}, http_post=boom)
    assert res.ok is False
    assert res.error and "connection refused" in res.error


def test_service_propagates_real_error_not_generic() -> None:
    cfg = default_config()
    cfg.poll_interval_ms = 100

    def fake_report(config, payload):
        return ReportResult(
            ok=False,
            error="无法连接服务端 http://127.0.0.1:8765/api/v1/report：拒绝连接。请确认已启动 API 服务",
        )

    svc = AgentService(
        cfg,
        sampler=lambda: ForegroundInfo(process_name="Code.exe", window_title="t"),
        reporter=fake_report,
    )
    svc.start()
    deadline = time.time() + 2
    while time.time() < deadline and svc.snapshot()["fail_count"] < 1:
        time.sleep(0.02)
    snap = svc.snapshot()
    svc.stop()
    assert snap["fail_count"] >= 1
    assert snap["last_error"]
    assert "无法连接" in snap["last_error"] or "API" in snap["last_error"]
    assert snap["last_error"] != "report failed"


def test_service_bool_reporter_still_works() -> None:
    cfg = default_config()
    cfg.poll_interval_ms = 100
    svc = AgentService(
        cfg,
        sampler=lambda: ForegroundInfo(process_name="Code.exe", window_title="t"),
        reporter=lambda c, p: True,
    )
    svc.start()
    deadline = time.time() + 2
    while time.time() < deadline and svc.snapshot()["ok_count"] < 1:
        time.sleep(0.02)
    snap = svc.snapshot()
    svc.stop()
    assert snap["ok_count"] >= 1
    assert snap["last_error"] is None
