"""Tests for JSON envelope helpers."""

from __future__ import annotations

from server.app import envelope as env


def test_success_shape() -> None:
    body = env.success({"a": 1})
    assert body == {"code": 0, "message": "ok", "data": {"a": 1}}


def test_success_null_data() -> None:
    assert env.success() == {"code": 0, "message": "ok", "data": None}


def test_error_shape() -> None:
    body = env.error(env.CODE_RATE_LIMITED, "rate limit exceeded")
    assert body["code"] == 42900
    assert body["message"] == "rate limit exceeded"
    assert body["data"] is None


def test_http_status_mapping() -> None:
    assert env.http_status_for_code(0) == 200
    assert env.http_status_for_code(40000) == 400
    assert env.http_status_for_code(40100) == 401
    assert env.http_status_for_code(40400) == 404
    assert env.http_status_for_code(42900) == 429
    assert env.http_status_for_code(50000) == 500
    assert env.http_status_for_code(99999) == 500
