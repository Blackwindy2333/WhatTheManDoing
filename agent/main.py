"""WhatTheManDoing agent entrypoint.

Loads persisted config (creates defaults when missing), samples the Windows
foreground app on an interval, and reports to the backend. Do not run this
during the development test phase — use pytest instead.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from agent.config import DEFAULT_CONFIG_PATH, AgentConfig, ensure_config
from agent.foreground import ForegroundError, ForegroundInfo, get_foreground_info
from agent.reporter import build_payload, send_report
from logconfig import get_logger, setup_logging

log = get_logger("agent.main")


def sample_once(config: AgentConfig, info: ForegroundInfo | None = None) -> dict:
    """Build one report payload from the current (or injected) foreground state."""
    if config.privacy_pause:
        return build_payload(config, None, status="paused")
    if info is None:
        info = get_foreground_info()
    return build_payload(config, info, status="active")


def run_loop(config: AgentConfig, *, max_iterations: int | None = None) -> int:
    """Poll foreground app and report. `max_iterations` is for tests."""
    interval = max(config.poll_interval_ms, 100) / 1000.0
    iterations = 0
    while max_iterations is None or iterations < max_iterations:
        try:
            payload = sample_once(config)
        except ForegroundError as exc:
            log.warning("foreground unavailable: %s", exc)
            payload = build_payload(config, None, status="idle")
        result = send_report(config, payload)
        if not result.ok:
            log.warning("report failed: %s", result.error)
        iterations += 1
        if max_iterations is not None and iterations >= max_iterations:
            break
        time.sleep(interval)
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WhatTheManDoing Windows agent")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="path to agent config.json (created with defaults if missing)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="sample and report a single frame then exit",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    setup_logging(app_name="agent")
    config = ensure_config(args.config)
    log.info("agent main starting config=%s device_id=%s", args.config, config.device_id)
    if args.once:
        try:
            payload = sample_once(config)
        except ForegroundError as exc:
            log.warning("foreground unavailable: %s", exc)
            payload = build_payload(config, None, status="idle")
        result = send_report(config, payload)
        if not result.ok:
            log.error("single report failed: %s", result.error)
        return 0 if result.ok else 1
    return run_loop(config)


if __name__ == "__main__":
    raise SystemExit(main())
