"""FastAPI app: standardized JSON API for clients (server-only project).

All JSON bodies use the envelope {code, message, data}.
Global rate limit: rate_limit_per_minute (configurable, GUI-editable).
"""

from __future__ import annotations

import json
from typing import Any, Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.websockets import WebSocket, WebSocketDisconnect

from agent.config import AgentConfig
from logconfig import get_logger, setup_logging
from server.app.auth import check_agent_token, check_viewer_token
from server.app.config import DEFAULT_CONFIG_PATH, ServerConfig, ensure_config
from server.app.envelope import (
    CODE_BAD_REQUEST,
    CODE_INTERNAL,
    CODE_NOT_FOUND,
    CODE_RATE_LIMITED,
    CODE_UNAUTHORIZED,
    error,
    success,
)
from server.app.ratelimit import GlobalRateLimiter
from server.app.status import sample_local_status
from server.app.storage import Storage

log = get_logger("server")


def _ok(data: Any = None, message: str = "ok") -> JSONResponse:
    return JSONResponse(content=success(data, message))


def _fail(status_code: int, code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error(code, message))


def create_app(
    config: ServerConfig | None = None,
    storage: Storage | None = None,
    *,
    agent_config: AgentConfig | None = None,
    status_provider: Callable[[], dict[str, Any]] | None = None,
    limiter: GlobalRateLimiter | None = None,
) -> FastAPI:
    cfg = config or ensure_config(DEFAULT_CONFIG_PATH)
    store = storage or Storage(cfg.db_path)
    rate = limiter or GlobalRateLimiter(cfg.rate_limit_per_minute)
    agent_cfg = agent_config

    app = FastAPI(title="WhatTheManDoing API", version="2.0.0")
    app.state.config = cfg
    app.state.storage = store
    app.state.limiter = rate
    app.state.agent_config = agent_cfg
    app.state.status_provider = status_provider
    app.state.ws_clients: list[WebSocket] = []

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins or ["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            return JSONResponse(status_code=exc.status_code, content=detail)
        if exc.status_code == 401:
            code = CODE_UNAUTHORIZED
        elif exc.status_code == 404:
            code = CODE_NOT_FOUND
        elif exc.status_code == 429:
            code = CODE_RATE_LIMITED
        elif exc.status_code >= 500:
            code = CODE_INTERNAL
        else:
            code = CODE_BAD_REQUEST
        return JSONResponse(
            status_code=exc.status_code,
            content=error(code, str(detail)),
        )

    def require_viewer(authorization: str | None = Header(default=None)) -> None:
        try:
            check_viewer_token(cfg, authorization)
        except HTTPException as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=error(CODE_UNAUTHORIZED, str(exc.detail)),
            ) from exc

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        result = rate.check()
        if not result.allowed:
            log.warning("rate limit exceeded path=%s limit=%s", request.url.path, result.limit)
            body = error(CODE_RATE_LIMITED, "rate limit exceeded, try again later")
            return Response(
                content=json.dumps(body),
                status_code=429,
                media_type="application/json",
                headers={
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": "0",
                    "Retry-After": str(result.retry_after),
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, result.remaining))
        return response

    def _current_status() -> dict[str, Any]:
        if status_provider is not None:
            return status_provider()
        return sample_local_status(config=agent_cfg)

    # ----- core client API -----------------------------------------------

    @app.get("/api/v1/health")
    def health() -> JSONResponse:
        return _ok({"status": "ok", "rate_limit_per_minute": rate.limit})

    @app.get("/api/v1/status")
    def get_status() -> JSONResponse:
        """Current foreground application on this machine (privacy-filtered)."""
        try:
            data = _current_status()
        except Exception as exc:  # noqa: BLE001
            return _fail(500, CODE_INTERNAL, f"status sampling failed: {exc}")
        return _ok(data)

    @app.get("/api/v1/status/history")
    def get_status_history(limit: int = Query(default=50, ge=1, le=1000)) -> JSONResponse:
        device_id = (agent_cfg.device_id if agent_cfg else None) or "local"
        if status_provider is not None:
            try:
                snap = status_provider()
                device_id = snap.get("device_id") or device_id
            except Exception:  # noqa: BLE001
                pass
        entries = store.history(device_id, limit=limit)
        return _ok(
            {
                "device_id": device_id,
                "history": [e.to_public_dict(show_window_title=False) for e in entries],
            }
        )

    # ----- device report (agent → this server) ----------------------------

    @app.post("/api/v1/report")
    async def report(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> JSONResponse:
        device_id = payload.get("device_id")
        if not isinstance(device_id, str) or not device_id:
            return _fail(400, CODE_BAD_REQUEST, "device_id is required")
        try:
            check_agent_token(cfg, device_id, authorization)
        except HTTPException as exc:
            log.warning("report unauthorized device_id=%s", device_id)
            return _fail(401, CODE_UNAUTHORIZED, str(exc.detail))
        try:
            state = store.record_report(payload)
        except (KeyError, ValueError) as exc:
            log.warning("report invalid payload: %s", exc)
            return _fail(400, CODE_BAD_REQUEST, str(exc))

        public = store.device_public(
            state,
            show_window_title=False,
            offline_after_seconds=cfg.offline_after_seconds,
        )
        await _broadcast(app, public)
        log.debug("report stored device_id=%s status=%s", device_id, state.status)
        return _ok({"ok": True})

    @app.get("/api/v1/devices", dependencies=[Depends(require_viewer)])
    def list_devices() -> JSONResponse:
        items = [
            store.device_public(
                state,
                show_window_title=False,
                offline_after_seconds=cfg.offline_after_seconds,
            )
            for state in store.list_devices()
        ]
        items.sort(key=lambda d: d.get("device_name") or "")
        return _ok({"devices": items})

    @app.get("/api/v1/devices/{device_id}", dependencies=[Depends(require_viewer)])
    def get_device(device_id: str) -> JSONResponse:
        state = store.get_device(device_id)
        if state is None:
            return _fail(404, CODE_NOT_FOUND, "device not found")
        return _ok(
            store.device_public(
                state,
                show_window_title=False,
                offline_after_seconds=cfg.offline_after_seconds,
            )
        )

    @app.get("/api/v1/devices/{device_id}/history", dependencies=[Depends(require_viewer)])
    def get_history(device_id: str, limit: int = Query(default=50, ge=1, le=1000)) -> JSONResponse:
        if store.get_device(device_id) is None and not store.history(device_id, limit=1):
            return _fail(404, CODE_NOT_FOUND, "device not found")
        entries = store.history(device_id, limit=limit)
        return _ok(
            {
                "device_id": device_id,
                "history": [e.to_public_dict(show_window_title=False) for e in entries],
            }
        )

    @app.websocket("/api/v1/ws")
    async def ws_endpoint(websocket: WebSocket, token: str | None = Query(default=None)) -> None:
        authorization = f"Bearer {token}" if token else websocket.headers.get("authorization")
        try:
            check_viewer_token(cfg, authorization)
        except HTTPException:
            await websocket.close(code=4401)
            return
        await websocket.accept()
        app.state.ws_clients.append(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            if websocket in app.state.ws_clients:
                app.state.ws_clients.remove(websocket)

    return app


async def _broadcast(app: FastAPI, message: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    for ws in list(app.state.ws_clients):
        try:
            await ws.send_json({"type": "device", "data": message})
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in app.state.ws_clients:
            app.state.ws_clients.remove(ws)


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    log_file = setup_logging(app_name="server")
    cfg = ensure_config(DEFAULT_CONFIG_PATH)
    log.info(
        "API server starting host=%s port=%s rate_limit=%s log=%s",
        cfg.host,
        cfg.port,
        cfg.rate_limit_per_minute,
        log_file,
    )
    uvicorn.run(
        create_app(cfg),
        host=cfg.host,
        port=cfg.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
