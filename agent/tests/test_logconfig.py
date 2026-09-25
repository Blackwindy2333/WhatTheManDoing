"""Tests for shared logging setup."""

from __future__ import annotations

from pathlib import Path

from logconfig import get_logger, log_file_path, resolve_level, setup_logging


def test_resolve_level() -> None:
    import logging

    assert resolve_level("info") == logging.INFO
    assert resolve_level("DEBUG") == logging.DEBUG
    assert resolve_level(30) == 30
    assert resolve_level(None) == logging.INFO


def test_setup_logging_creates_file(tmp_path: Path) -> None:
    path = setup_logging(app_name="testapp", log_dir=tmp_path, level="INFO", to_console=False)
    assert path.exists()
    logger = get_logger("unit")
    logger.info("hello log")
    # Flush handlers
    for h in logger.handlers:
        h.flush()
    content = path.read_text(encoding="utf-8")
    assert "hello log" in content
    assert "logging initialized" in content


def test_log_file_path_helper(tmp_path: Path) -> None:
    assert log_file_path("gui", tmp_path) == tmp_path / "gui.log"
