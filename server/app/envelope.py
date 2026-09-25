"""Standardized JSON response envelope for all API endpoints.

Shape (always the same):
{
  "code": 0,
  "message": "ok",
  "data": {...} | null
}

code 0 = success. Non-zero codes are grouped by HTTP status family:
  400xx request, 401xx auth, 404xx not found, 429xx rate limit, 500xx server.
"""

from __future__ import annotations

from typing import Any

# Business codes
CODE_OK = 0
CODE_BAD_REQUEST = 40000
CODE_UNAUTHORIZED = 40100
CODE_FORBIDDEN = 40300
CODE_NOT_FOUND = 40400
CODE_RATE_LIMITED = 42900
CODE_INTERNAL = 50000

DEFAULT_MESSAGE = "ok"


def success(data: Any = None, message: str = DEFAULT_MESSAGE) -> dict[str, Any]:
    return {"code": CODE_OK, "message": message, "data": data}


def error(code: int, message: str, data: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "data": data}


def http_status_for_code(code: int) -> int:
    if code == CODE_OK:
        return 200
    if 40000 <= code < 40100:
        return 400
    if 40100 <= code < 40200:
        return 401
    if 40300 <= code < 40400:
        return 403
    if 40400 <= code < 40500:
        return 404
    if 42900 <= code < 43000:
        return 429
    if 50000 <= code < 50100:
        return 500
    return 500
