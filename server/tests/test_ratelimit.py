"""Tests for global RPM rate limiter."""

from __future__ import annotations

from server.app.ratelimit import GlobalRateLimiter


def test_allows_up_to_limit() -> None:
    rl = GlobalRateLimiter(limit_per_minute=3)
    t0 = 1000.0
    assert rl.allow(t0) is True
    assert rl.allow(t0 + 1) is True
    assert rl.allow(t0 + 2) is True
    assert rl.allow(t0 + 3) is False


def test_remaining_and_retry_after() -> None:
    rl = GlobalRateLimiter(limit_per_minute=2)
    r1 = rl.check(2000.0)
    assert r1.allowed is True and r1.remaining == 1
    r2 = rl.check(2001.0)
    assert r2.allowed is True and r2.remaining == 0
    r3 = rl.check(2002.0)
    assert r3.allowed is False
    assert r3.remaining == 0
    assert r3.retry_after >= 1
    assert r3.limit == 2


def test_window_slides() -> None:
    rl = GlobalRateLimiter(limit_per_minute=2)
    assert rl.allow(3000.0) is True
    assert rl.allow(3001.0) is True
    assert rl.allow(3002.0) is False
    # After 60s the oldest expires
    assert rl.allow(3062.0) is True


def test_set_limit_and_peek() -> None:
    rl = GlobalRateLimiter(limit_per_minute=1)
    assert rl.allow(4000.0) is True
    assert rl.allow(4000.1) is False
    rl.set_limit(5)
    assert rl.limit == 5
    # peek does not consume
    before = rl.check(4001.0, peek=True)
    after = rl.check(4001.0, peek=True)
    assert before.remaining == after.remaining


def test_min_limit_is_one() -> None:
    rl = GlobalRateLimiter(limit_per_minute=0)
    assert rl.limit == 1
