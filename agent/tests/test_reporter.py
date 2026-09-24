"""Tests for report payload privacy rules and HTTP sender seam."""

from __future__ import annotations

from agent.config import default_config
from agent.foreground import ForegroundInfo
from agent.main import sample_once
from agent.reporter import build_payload, report_url, send_report


def _info(title: str = "secret - work") -> ForegroundInfo:
    return ForegroundInfo(process_name="Code.exe", window_title=title)


def test_payload_omits_window_title_by_default() -> None:
    cfg = default_config()
    assert cfg.report_window_title is False
    payload = build_payload(cfg, _info(), status="active")
    assert payload["device_id"] == cfg.device_id
    assert payload["status"] == "active"
    assert payload["app"] is not None
    assert payload["app"]["process_name"] == "Code.exe"
    assert payload["app"]["display_name"] == "Visual Studio Code"
    assert payload["app"]["window_title"] is None


def test_payload_includes_window_title_when_enabled() -> None:
    cfg = default_config()
    cfg.report_window_title = True
    payload = build_payload(cfg, _info("docs.md — MyProject"), status="active")
    assert payload["app"]["window_title"] == "docs.md — MyProject"


def test_payload_redacts_blacklist() -> None:
    cfg = default_config()
    cfg.app_name_blacklist = ["Code.exe"]
    payload = build_payload(cfg, _info(), status="active")
    assert payload["app"]["process_name"] == "redacted"
    assert payload["app"]["window_title"] is None


def test_payload_paused_has_no_app() -> None:
    cfg = default_config()
    payload = build_payload(cfg, _info(), status="paused")
    assert payload["app"] is None
    assert payload["status"] == "paused"


def test_sample_once_respects_privacy_pause() -> None:
    cfg = default_config()
    cfg.privacy_pause = True
    payload = sample_once(cfg, info=_info())
    assert payload["status"] == "paused"
    assert payload["app"] is None


def test_report_url_joins() -> None:
    cfg = default_config()
    assert report_url(cfg).endswith("/report")
    assert report_url(cfg).startswith("http")


def test_send_report_uses_http_post_seam() -> None:
    cfg = default_config()
    seen = {}

    def fake_post(url, json_body, headers):
        seen["url"] = url
        seen["body"] = json_body
        seen["headers"] = headers
        return 201

    payload = build_payload(cfg, _info(), status="active")
    assert send_report(cfg, payload, http_post=fake_post) is True
    assert seen["headers"]["Authorization"] == f"Bearer {cfg.device_token}"
    assert seen["body"]["device_id"] == cfg.device_id


def test_send_report_false_on_error_status() -> None:
    cfg = default_config()
    payload = build_payload(cfg, _info(), status="active")
    assert send_report(cfg, payload, http_post=lambda *a: 500) is False
