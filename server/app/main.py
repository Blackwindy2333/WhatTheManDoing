"""FastAPI app: agent report + read-only viewer APIs."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from server.app.auth import check_agent_token, check_viewer_token
from server.app.config import DEFAULT_CONFIG_PATH, ServerConfig, ensure_config
from server.app.storage import Storage


def create_app(config: ServerConfig | None = None, storage: Storage | None = None) -> FastAPI:
    cfg = config or ensure_config(DEFAULT_CONFIG_PATH)
    store = storage or Storage(cfg.db_path)

    app = FastAPI(title="WhatTheManDoing API", version="1.0.0")
    app.state.config = cfg
    app.state.storage = store
    app.state.ws_clients: list[WebSocket] = []

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins or ["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    def viewer_auth(authorization: str | None = Header(default=None)) -> None:
        check_viewer_token(cfg, authorization)

    @app.get("/api/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/v1/report")
    async def report(
        payload: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        device_id = payload.get("device_id")
        if not isinstance(device_id, str) or not device_id:
            raise HTTPException(status_code=400, detail="device_id is required")
        check_agent_token(cfg, device_id, authorization)
        try:
            state = store.record_report(payload)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        public = store.device_public(
            state,
            show_window_title=False,
            offline_after_seconds=cfg.offline_after_seconds,
        )
        await _broadcast(app, public)
        return {"ok": True}

    @app.get("/api/v1/devices", dependencies=[Depends(viewer_auth)])
    def list_devices() -> dict[str, Any]:
        items = [
            store.device_public(
                state,
                show_window_title=False,
                offline_after_seconds=cfg.offline_after_seconds,
            )
            for state in store.list_devices()
        ]
        items.sort(key=lambda d: d["device_name"])
        return {"devices": items}

    @app.get("/api/v1/devices/{device_id}", dependencies=[Depends(viewer_auth)])
    def get_device(device_id: str) -> dict[str, Any]:
        state = store.get_device(device_id)
        if state is None:
            raise HTTPException(status_code=404, detail="device not found")
        return store.device_public(
            state,
            show_window_title=False,
            offline_after_seconds=cfg.offline_after_seconds,
        )

    @app.get("/api/v1/devices/{device_id}/history", dependencies=[Depends(viewer_auth)])
    def get_history(
        device_id: str,
        limit: int = Query(default=50, ge=1, le=1000),
    ) -> dict[str, Any]:
        if store.get_device(device_id) is None and not store.history(device_id, limit=1):
            raise HTTPException(status_code=404, detail="device not found")
        entries = store.history(device_id, limit=limit)
        return {
            "device_id": device_id,
            "history": [e.to_public_dict(show_window_title=False) for e in entries],
        }

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
                # Keep the connection open; client messages are ignored (read-only channel).
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

    cfg = ensure_config(DEFAULT_CONFIG_PATH)
    uvicorn.run(
        create_app(cfg),
        host=cfg.host,
        port=cfg.port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
