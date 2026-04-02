"""
MCP Client for Ubuntu Desktop Control
讓 AI 老婆可以控制桌面操作
"""

import asyncio
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional, Any

logger = logging.getLogger(__name__)


class MCPDesktopControl:
    """MCP Client for ubuntu-desktop-control-mcp"""

    def __init__(self, mcp_server_path: str = None):
        self.mcp_server_path = mcp_server_path or "ubuntu-desktop-control"
        self._process: Optional[asyncio.subprocess.Process] = None
        self._message_id = 0
        self._initialized = False

    async def start(self):
        """啟動 MCP server 進程"""
        if self._process and self._process.returncode is None:
            return

        logger.info("Starting ubuntu-desktop-control MCP server...")
        try:
            self._process = await asyncio.create_subprocess_exec(
                self.mcp_server_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._initialized = False
            logger.info("MCP server started")
        except FileNotFoundError:
            logger.warning(
                f"MCP server executable not found: '{self.mcp_server_path}'. "
                "Desktop control is disabled. Install ubuntu-desktop-control-mcp to enable."
            )
            self._process = None
            self._initialized = False
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            self._process = None
            self._initialized = False

    async def stop(self):
        """停止 MCP server"""
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
            self._process = None
            self._initialized = False

    async def _send_request(self, method: str, params: dict = None) -> dict:
        """發送 MCP JSON-RPC 請求"""
        if not self._process or self._process.returncode is not None:
            try:
                await self.start()
            except Exception:
                return {"error": "MCP server not available"}

        if not self._process:
            return {"error": "MCP server executable not found"}

        self._message_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._message_id,
            "method": method,
            "params": params or {},
        }

        # 發送請求
        request_json = json.dumps(request) + "\n"
        self._process.stdin.write(request_json.encode())
        await self._process.stdin.drain()

        # 讀取回應（10 秒 timeout）
        response_line = await asyncio.wait_for(self._process.stdout.readline(), timeout=10)
        if not response_line:
            raise RuntimeError("MCP server closed connection")

        response = json.loads(response_line.decode())

        if "error" in response:
            raise RuntimeError(f"MCP error: {response['error']}")

        return response.get("result", {})

    async def initialize(self):
        """初始化 MCP session"""
        result = await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ai-wife-server", "version": "1.0.0"},
            },
        )
        self._initialized = True
        # Send notification (no id, no response expected)
        notification = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        self._process.stdin.write(notification.encode())
        await self._process.stdin.drain()
        logger.info("MCP session initialized")
        return result

    async def take_screenshot(self, detect_elements: bool = True) -> dict:
        """截圖並自動偵測 UI 元素"""
        return await self._send_request(
            "tools/call",
            {
                "name": "take_screenshot",
                "arguments": {"detect_elements": detect_elements},
            },
        )

    async def click_screen(
        self, element_id: int = None, x_percent: float = None, y_percent: float = None
    ) -> dict:
        """點擊螢幕（元素 ID 或百分比座標）"""
        args = {}
        if element_id is not None:
            args["element_id"] = element_id
        if x_percent is not None:
            args["x_percent"] = x_percent
        if y_percent is not None:
            args["y_percent"] = y_percent
        return await self._send_request(
            "tools/call",
            {
                "name": "click_screen",
                "arguments": args,
            },
        )

    async def type_text(self, text: str) -> dict:
        """輸入文字"""
        return await self._send_request(
            "tools/call",
            {
                "name": "type_text",
                "arguments": {"text": text},
            },
        )

    async def press_key(self, key: str) -> dict:
        """按下按鍵"""
        return await self._send_request(
            "tools/call",
            {
                "name": "press_key",
                "arguments": {"key": key},
            },
        )

    async def press_hotkey(self, keys: list[str]) -> dict:
        """按下組合鍵"""
        return await self._send_request(
            "tools/call",
            {
                "name": "press_hotkey",
                "arguments": {"keys": keys},
            },
        )

    async def move_mouse(
        self, element_id: int = None, x_percent: float = None, y_percent: float = None
    ) -> dict:
        """移動滑鼠"""
        args = {}
        if element_id is not None:
            args["element_id"] = element_id
        if x_percent is not None:
            args["x_percent"] = x_percent
        if y_percent is not None:
            args["y_percent"] = y_percent
        return await self._send_request(
            "tools/call",
            {
                "name": "move_mouse",
                "arguments": args,
            },
        )

    async def execute_workflow(self, actions: list[dict]) -> dict:
        """批量執行操作"""
        return await self._send_request(
            "tools/call",
            {
                "name": "execute_workflow",
                "arguments": {"actions": actions},
            },
        )

    async def get_screen_info(self) -> dict:
        """取得螢幕資訊"""
        return await self._send_request(
            "tools/call",
            {
                "name": "get_screen_info",
                "arguments": {},
            },
        )

    async def map_gui_elements(self) -> dict:
        """偵測並映射 GUI 元素位置"""
        return await self._send_request(
            "tools/call",
            {
                "name": "map_GUI_elements_location",
                "arguments": {},
            },
        )
