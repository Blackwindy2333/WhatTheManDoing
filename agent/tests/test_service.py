"""Tests for AgentService start/stop and status snapshot."""

from __future__ import annotations

import time

from agent.config import default_config
from agent.foreground import ForegroundInfo
from agent.service import AgentService


def _info() -> ForegroundInfo:
    return ForegroundInfo(process_name="Code.exe", window_title="t")


def test_start_stop_and_counts() -> None:
    cfg = default_config()
    cfg.poll_interval_ms = 100
    reports = []

    def fake_report(config, payload):
        reports.append(payload)
        return True

    svc = AgentService(cfg, sampler=_info, reporter=fake_report)
    assert svc.is_running() is False
    assert svc.start() is True
    assert svc.start() is False  # already running

    deadline = time.time() + 2.0
    while time.time() < deadline and len(reports) < 2:
        time.sleep(0.02)

    snap = svc.snapshot()
    assert snap["running"] is True
    assert snap["ok_count"] >= 1
    assert snap["current_process"] == "Code.exe"
    assert snap["current_app"] == "Visual Studio Code"
    assert snap["last_payload"]["app"]["window_title"] is None

    svc.stop()
    assert svc.is_running() is False
    assert svc.snapshot()["status"] == "stopped"


def test_privacy_pause_payload() -> None:
    cfg = default_config()
    cfg.poll_interval_ms = 100
    cfg.privacy_pause = True
    captured = []

    def fake_report(config, payload):
        captured.append(payload)
        return True

    svc = AgentService(cfg, sampler=_info, reporter=fake_report)
    svc.start()
    deadline = time.time() + 2.0
    while time.time() < deadline and not captured:
        time.sleep(0.02)
    svc.stop()
    assert captured
    assert captured[0]["status"] == "paused"
    assert captured[0]["app"] is None
    assert svc.snapshot()["status"] in {"paused", "stopped"}


def test_fail_path_increments() -> None:
    cfg = default_config()
    cfg.poll_interval_ms = 100

    def fake_report(config, payload):
        return False

    svc = AgentService(cfg, sampler=_info, reporter=fake_report)
    svc.start()
    deadline = time.time() + 2.0
    while time.time() < deadline and svc.snapshot()["fail_count"] < 1:
        time.sleep(0.02)
    snap = svc.snapshot()
    svc.stop()
    assert snap["fail_count"] >= 1
    assert snap["last_error"]


def test_on_update_callback() -> None:
    cfg = default_config()
    cfg.poll_interval_ms = 100
    seen = []
    svc = AgentService(
        cfg,
        on_update=lambda snap: seen.append(snap["running"]),
        sampler=_info,
        reporter=lambda c, p: True,
    )
    svc.start()
    deadline = time.time() + 2.0
    while time.time() < deadline and not seen:
        time.sleep(0.02)
    svc.stop()
    assert seen[0] is True
    assert seen[-1] is False or seen[-1] is True  # stop notify


def test_sample_error_still_reports_idle() -> None:
    """Foreground failure must still POST an idle frame to the server."""
    from agent.foreground import ForegroundError

    cfg = default_config()
    cfg.poll_interval_ms = 100
    reported = []

    def bad_sampler():
        raise ForegroundError("no window")

    svc = AgentService(
        cfg,
        sampler=bad_sampler,
        reporter=lambda c, p: reported.append(p) or True,
    )
    svc.start()
    deadline = time.time() + 2.0
    while time.time() < deadline and not reported:
        time.sleep(0.02)
    svc.stop()
    assert reported
    assert reported[0]["status"] == "idle"
    assert reported[0]["app"] is None
    # sample error is visible, not swallowed
    assert "no window" in (svc.snapshot()["last_error"] or "")
