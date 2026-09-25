"""SQLite-backed device state and history storage (read-only APIs use this)."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class DeviceState:
    device_id: str
    device_name: str
    status: str = "active"
    app: dict[str, Any] | None = None
    updated_at: str = ""
    window_title: str | None = None

    def to_public_dict(self, show_window_title: bool = False) -> dict[str, Any]:
        """Viewer-facing projection. Never mutates stored privacy fields."""
        app = self.app
        if isinstance(app, dict):
            app = dict(app)
            if not show_window_title:
                app["window_title"] = None
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "status": self.status,
            "app": app,
            "updated_at": self.updated_at,
            "online": False,  # filled by Storage
        }


@dataclass
class HistoryEntry:
    device_id: str
    status: str
    process_name: str | None
    display_name: str | None
    window_title: str | None
    timestamp: str
    id: int = 0

    def to_public_dict(self, show_window_title: bool = False) -> dict[str, Any]:
        return {
            "id": self.id,
            "device_id": self.device_id,
            "status": self.status,
            "process_name": self.process_name,
            "display_name": self.display_name,
            "window_title": self.window_title if show_window_title else None,
            "timestamp": self.timestamp,
        }


class Storage:
    """Thread-safe latest-state map + SQLite history."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._lock = threading.RLock()
        self._latest: dict[str, DeviceState] = {}
        if self._db_path.parent and str(self._db_path.parent) not in ("", "."):
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    process_name TEXT,
                    display_name TEXT,
                    window_title TEXT,
                    timestamp TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_history_device_ts ON history(device_id, timestamp)"
            )
            conn.commit()

    def record_report(self, payload: dict[str, Any], *, keep_history: int | None = None) -> DeviceState:
        """Accept an agent report payload and update latest + history.

        keep_history: if set, trim history to this many rows per device after insert.
        """
        device_id = str(payload["device_id"])
        device_name = str(payload.get("device_name") or device_id)
        status = str(payload.get("status") or "active")
        app = payload.get("app")
        if app is not None and not isinstance(app, dict):
            raise ValueError("app must be object or null")
        timestamp = str(payload.get("timestamp") or utc_now().isoformat())
        window_title = None
        process_name = None
        display_name = None
        if isinstance(app, dict):
            process_name = app.get("process_name")
            display_name = app.get("display_name")
            window_title = app.get("window_title")

        state = DeviceState(
            device_id=device_id,
            device_name=device_name,
            status=status,
            app=dict(app) if isinstance(app, dict) else None,
            updated_at=timestamp,
            window_title=window_title,
        )

        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO history (device_id, status, process_name, display_name, window_title, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (device_id, status, process_name, display_name, window_title, timestamp),
            )
            conn.commit()
            self._latest[device_id] = state
        if keep_history is not None:
            self.trim_history(keep_history)
        return state

    def list_devices(self) -> list[DeviceState]:
        with self._lock:
            return list(self._latest.values())

    def get_device(self, device_id: str) -> DeviceState | None:
        with self._lock:
            return self._latest.get(device_id)

    def history(self, device_id: str, limit: int = 50) -> list[HistoryEntry]:
        limit = max(1, min(int(limit), 1000))
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, device_id, status, process_name, display_name, window_title, timestamp
                FROM history
                WHERE device_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (device_id, limit),
            ).fetchall()
        return [
            HistoryEntry(
                id=row["id"],
                device_id=row["device_id"],
                status=row["status"],
                process_name=row["process_name"],
                display_name=row["display_name"],
                window_title=row["window_title"],
                timestamp=row["timestamp"],
            )
            for row in rows
        ]

    def trim_history(self, keep_per_device: int) -> None:
        keep = max(1, int(keep_per_device))
        with self._lock, self._connect() as conn:
            devices = [r["device_id"] for r in conn.execute("SELECT DISTINCT device_id FROM history")]
            for device_id in devices:
                conn.execute(
                    """
                    DELETE FROM history
                    WHERE device_id = ?
                      AND id NOT IN (
                        SELECT id FROM history
                        WHERE device_id = ?
                        ORDER BY id DESC
                        LIMIT ?
                      )
                    """,
                    (device_id, device_id, keep),
                )
            conn.commit()

    def is_online(self, state: DeviceState, offline_after_seconds: int, now: datetime | None = None) -> bool:
        if not state.updated_at:
            return False
        try:
            updated = parse_ts(state.updated_at)
        except ValueError:
            return False
        now = now or utc_now()
        return (now - updated).total_seconds() <= offline_after_seconds

    def device_public(
        self,
        state: DeviceState,
        *,
        show_window_title: bool = False,
        offline_after_seconds: int = 30,
    ) -> dict[str, Any]:
        data = state.to_public_dict(show_window_title=show_window_title)
        data["online"] = self.is_online(state, offline_after_seconds)
        return data
