"""Global sliding-window rate limiter (requests per minute)."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int  # seconds; 0 when allowed


class GlobalRateLimiter:
    """Shared across all clients: max N requests per rolling 60s window."""

    def __init__(self, limit_per_minute: int = 60) -> None:
        self._lock = threading.Lock()
        self._limit = max(1, int(limit_per_minute))
        self._timestamps: list[float] = []
        self._window = 60.0

    @property
    def limit(self) -> int:
        with self._lock:
            return self._limit

    def set_limit(self, limit_per_minute: int) -> None:
        with self._lock:
            self._limit = max(1, int(limit_per_minute))

    def reset(self) -> None:
        with self._lock:
            self._timestamps.clear()

    def check(self, now: float | None = None, *, peek: bool = False) -> RateLimitResult:
        """Return whether a request is allowed.

        peek=True does not consume quota (for headers on denied or dry-run).
        """
        now = time.time() if now is None else now
        with self._lock:
            cutoff = now - self._window
            # Drop expired stamps (kept only while timestamp >= cutoff)
            if self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps = [t for t in self._timestamps if t >= cutoff]

            limit = self._limit
            used = len(self._timestamps)
            if used < limit:
                if not peek:
                    self._timestamps.append(now)
                return RateLimitResult(
                    allowed=True,
                    limit=limit,
                    remaining=limit - used - (0 if peek else 1),
                    retry_after=0,
                )

            oldest = self._timestamps[0]
            retry_after = max(1, int(round(oldest + self._window - now)))
            return RateLimitResult(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after=retry_after,
            )

    def allow(self, now: float | None = None) -> bool:
        return self.check(now).allowed
