"""WebSocket endpoint for real-time agent activity feed."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.neo4j_service import Neo4jService
from app.graph import queries

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Connected clients
_connections: list[WebSocket] = []


async def broadcast(event: dict[str, Any]) -> None:
    """Broadcast an event to all connected WebSocket clients."""
    dead: list[WebSocket] = []
    message = json.dumps(event, default=str)

    for ws in _connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)

    for ws in dead:
        _connections.remove(ws)


@router.websocket("/ws/activity")
async def activity_feed(websocket: WebSocket):
    """Real-time activity feed via WebSocket.

    Sends new agent actions as they occur and periodically pushes
    the latest activity summary.
    """
    await websocket.accept()
    _connections.append(websocket)
    logger.info("WebSocket client connected (%d total)", len(_connections))

    try:
        # Send initial batch of recent activity
        rows = await Neo4jService.run_query(
            queries.RECENT_ACTIVITY,
            {"limit": 20},
        )
        await websocket.send_text(
            json.dumps({"type": "initial", "data": rows}, default=str)
        )

        # Keep alive + periodic updates
        while True:
            try:
                # Wait for client messages (pings) or timeout
                data = await asyncio.wait_for(
                    websocket.receive_text(), timeout=30.0
                )

                if data == "ping":
                    await websocket.send_text(
                        json.dumps({"type": "pong"})
                    )
                elif data == "refresh":
                    rows = await Neo4jService.run_query(
                        queries.RECENT_ACTIVITY,
                        {"limit": 20},
                    )
                    await websocket.send_text(
                        json.dumps(
                            {"type": "refresh", "data": rows}, default=str
                        )
                    )

            except asyncio.TimeoutError:
                # Send periodic heartbeat with latest stats
                rows = await Neo4jService.run_query(
                    queries.RECENT_ACTIVITY,
                    {"limit": 5},
                )
                await websocket.send_text(
                    json.dumps(
                        {"type": "heartbeat", "data": rows}, default=str
                    )
                )

    except WebSocketDisconnect:
        pass
    finally:
        if websocket in _connections:
            _connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected (%d remaining)", len(_connections)
        )
