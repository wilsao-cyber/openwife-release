import asyncio
import logging
from fastapi import WebSocket
from typing import Dict, Set

logger = logging.getLogger(__name__)


class WebSocketManager:
    PING_INTERVAL = 30
    PONG_TIMEOUT = 10

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_sessions: Dict[str, Set[str]] = {}
        self._ping_tasks: Dict[str, asyncio.Task] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.client_sessions.setdefault(client_id, set())
        self._ping_tasks[client_id] = asyncio.create_task(
            self._heartbeat(client_id)
        )
        logger.info(f"Client connected: {client_id}")

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)
        self.client_sessions.pop(client_id, None)
        task = self._ping_tasks.pop(client_id, None)
        if task:
            task.cancel()
        logger.info(f"Client disconnected: {client_id}")

    async def _heartbeat(self, client_id: str):
        try:
            while client_id in self.active_connections:
                await asyncio.sleep(self.PING_INTERVAL)
                ws = self.active_connections.get(client_id)
                if ws is None:
                    break
                try:
                    await asyncio.wait_for(
                        ws.send_json({"type": "ping"}),
                        timeout=self.PONG_TIMEOUT,
                    )
                except (asyncio.TimeoutError, Exception) as e:
                    logger.warning(f"Heartbeat failed for {client_id}: {e}")
                    self.disconnect(client_id)
                    break
        except asyncio.CancelledError:
            pass

    async def send_json(self, client_id: str, data: dict):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(data)
            except Exception:
                self.disconnect(client_id)

    async def send_text(self, client_id: str, text: str):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(text)
            except Exception:
                self.disconnect(client_id)

    async def broadcast(self, data: dict, exclude: str = None):
        disconnected = []
        for client_id, ws in self.active_connections.items():
            if client_id != exclude:
                try:
                    await ws.send_json(data)
                except Exception as e:
                    logger.error(f"Broadcast failed to {client_id}: {e}")
                    disconnected.append(client_id)
        for client_id in disconnected:
            self.disconnect(client_id)

    async def send_audio(self, client_id: str, audio_data: bytes):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_bytes(audio_data)
            except Exception:
                self.disconnect(client_id)

    def get_active_clients(self) -> list[str]:
        return list(self.active_connections.keys())

    def is_connected(self, client_id: str) -> bool:
        return client_id in self.active_connections
