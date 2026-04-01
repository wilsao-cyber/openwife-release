import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from websocket_manager import WebSocketManager


@pytest.fixture
def manager():
    return WebSocketManager()


@pytest.fixture
def mock_ws():
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.send_text = AsyncMock()
    ws.send_bytes = AsyncMock()
    return ws


class TestWebSocketManager:
    @pytest.mark.asyncio
    async def test_connect_and_disconnect(self, manager, mock_ws):
        await manager.connect(mock_ws, "client1")
        assert manager.is_connected("client1")
        assert "client1" in manager.get_active_clients()

        manager.disconnect("client1")
        assert not manager.is_connected("client1")
        assert "client1" not in manager.get_active_clients()

    @pytest.mark.asyncio
    async def test_send_json(self, manager, mock_ws):
        await manager.connect(mock_ws, "client1")
        await manager.send_json("client1", {"msg": "hello"})
        mock_ws.send_json.assert_called_with({"msg": "hello"})

    @pytest.mark.asyncio
    async def test_send_to_disconnected_client_no_error(self, manager):
        await manager.send_json("nonexistent", {"msg": "hello"})

    @pytest.mark.asyncio
    async def test_send_json_disconnects_on_error(self, manager, mock_ws):
        mock_ws.send_json.side_effect = Exception("connection lost")
        await manager.connect(mock_ws, "client1")

        # Cancel heartbeat so it doesn't interfere
        manager._ping_tasks["client1"].cancel()

        await manager.send_json("client1", {"msg": "hello"})
        assert not manager.is_connected("client1")

    @pytest.mark.asyncio
    async def test_broadcast(self, manager):
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        await manager.connect(ws1, "c1")
        await manager.connect(ws2, "c2")

        await manager.broadcast({"event": "test"}, exclude="c1")

        ws1.send_json.reset_mock()
        ws2.send_json.assert_called()

    @pytest.mark.asyncio
    async def test_heartbeat_starts_on_connect(self, manager, mock_ws):
        await manager.connect(mock_ws, "client1")
        assert "client1" in manager._ping_tasks
        task = manager._ping_tasks["client1"]
        assert not task.done()

        manager.disconnect("client1")
        await asyncio.sleep(0.05)
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_send_audio(self, manager, mock_ws):
        await manager.connect(mock_ws, "client1")
        await manager.send_audio("client1", b"audio_data")
        mock_ws.send_bytes.assert_called_with(b"audio_data")

    @pytest.mark.asyncio
    async def test_disconnect_cancels_heartbeat(self, manager, mock_ws):
        await manager.connect(mock_ws, "client1")
        task = manager._ping_tasks["client1"]
        manager.disconnect("client1")
        await asyncio.sleep(0.05)
        assert task.cancelled()
        assert "client1" not in manager._ping_tasks
