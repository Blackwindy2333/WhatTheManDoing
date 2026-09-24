"""Read-only viewer and agent auth checks."""

from __future__ import annotations

from fastapi import HTTPException, status

from server.app.config import ServerConfig


def extract_bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    token = token.strip()
    return token or None


def check_agent_token(config: ServerConfig, device_id: str, authorization: str | None) -> None:
    """Agent reports must present the device token configured for that device_id."""
    token = extract_bearer(authorization)
    expected = config.agent_tokens.get(device_id)
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unknown device_id",
        )
    if not token or token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid device token",
        )


def check_viewer_token(config: ServerConfig, authorization: str | None) -> None:
    """Viewer APIs are read-only. Empty viewer_token means public read access."""
    if config.viewer_token == "":
        return
    token = extract_bearer(authorization)
    if not token or token != config.viewer_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid viewer token",
        )
