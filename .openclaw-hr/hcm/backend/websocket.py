"""WebSocket connection manager for real-time dashboard updates."""

import json
from datetime import datetime
from fastapi import WebSocket
class ConnectionManager:
    """Manages active WebSocket connections and broadcasts state changes."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()  # noqa: E501

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)

    async def broadcast(self, event_type: str, payload: dict):
        """Send a JSON event to all connected clients."""
        message = json.dumps(
            {"event": event_type, "data": payload, "ts": datetime.utcnow().isoformat()},
            ensure_ascii=False,
        )
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_connections.discard(ws)


manager = ConnectionManager()
