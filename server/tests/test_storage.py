"""Tests for storage latest-state, history, and online calculation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from server.app.storage import Storage, parse_ts


def _payload(device_id: str = "my-pc", title: str = "secret", ts: str | None = None) -> dict:
    return {
        "device_id": device_id,
        "device_name": "My PC",
        "status": "active",
        "timestamp": ts or "2026-01-01T00:00:00Z",
        "app": {
            "process_name": "Code.exe",
            "display_name": "Visual Studio Code",
            "window_title": title,
        },
    }


def test_record_and_get(tmp_path: Path) -> None:
    store = Storage(tmp_path / "m.db")
    state = store.record_report(_payload())
    assert state.device_id == "my-pc"
    assert store.get_device("my-pc") is not None
    assert store.get_device("other") is None


def test_history_order_and_limit(tmp_path: Path) -> None:
    store = Storage(tmp_path / "m.db")
    for i in range(5):
        store.record_report(_payload(ts=f"2026-01-01T00:00:0{i}Z", title=f"t{i}"))
    hist = store.history("my-pc", limit=2)
    assert len(hist) == 2
    assert hist[0].window_title == "t4"


def test_public_dict_hides_window_title(tmp_path: Path) -> None:
    store = Storage(tmp_path / "m.db")
    state = store.record_report(_payload(title="TOP SECRET"))
    public = store.device_public(state, show_window_title=False, offline_after_seconds=30)
    assert public["app"]["window_title"] is None
    public2 = store.device_public(state, show_window_title=True, offline_after_seconds=30)
    assert public2["app"]["window_title"] == "TOP SECRET"
    hist = store.history("my-pc")[0]
    assert hist.to_public_dict(show_window_title=False)["window_title"] is None
    assert hist.to_public_dict(show_window_title=True)["window_title"] == "TOP SECRET"


def test_online_uses_offline_after_seconds(tmp_path: Path) -> None:
    store = Storage(tmp_path / "m.db")
    now = datetime(2026, 1, 1, 0, 0, 30, tzinfo=timezone.utc)
    state = store.record_report(_payload(ts="2026-01-01T00:00:00Z"))
    assert store.is_online(state, offline_after_seconds=30, now=now) is True
    later = now + timedelta(seconds=1)
    assert store.is_online(state, offline_after_seconds=30, now=later) is False


def test_trim_history(tmp_path: Path) -> None:
    store = Storage(tmp_path / "m.db")
    for i in range(10):
        store.record_report(_payload(ts=f"2026-01-01T00:00:{i:02d}Z"))
    store.trim_history(keep_per_device=3)
    assert len(store.history("my-pc", limit=50)) == 3


def test_record_report_auto_trims_history(tmp_path: Path) -> None:
    store = Storage(tmp_path / "m.db")
    for i in range(10):
        store.record_report(_payload(ts=f"2026-01-01T00:00:{i:02d}Z"), keep_history=3)
    assert len(store.history("my-pc", limit=50)) == 3


def test_parse_ts_naive_assumed_utc() -> None:
    dt = parse_ts("2026-01-01T12:00:00")
    assert dt == datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_ts_z_suffix() -> None:
    dt = parse_ts("2026-01-01T00:00:00Z")
    assert dt == datetime(2026, 1, 1, tzinfo=timezone.utc)
