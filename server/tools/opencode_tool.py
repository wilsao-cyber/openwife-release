import asyncio
import logging
import subprocess
import json
import os
from pathlib import Path
from typing import Optional
from config import OpenCodeConfig

logger = logging.getLogger(__name__)


async def run_claude_computer_use(task: str, env_vars: dict = None) -> dict:
    """執行 Claude Computer Use 自動化任務"""
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    script_path = Path("./scripts/claude_computer_use_pipeline.py")
    if not script_path.exists():
        return {"error": "Claude Computer Use script not found"}

    try:
        process = await asyncio.create_subprocess_exec(
            "python",
            str(script_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return {"success": True, "output": stdout.decode("utf-8")}
        else:
            return {"error": stderr.decode("utf-8")}
    except Exception as e:
        return {"error": str(e)}


class OpenCodeTool:
    def __init__(self, config: OpenCodeConfig):
        self.config = config
        self.server_url = config.server_url
        self.auto_start = config.auto_start
        self.timeout = config.timeout
        self.allowed_paths = [Path(p).resolve() for p in config.allowed_paths]
        self._server_process = None

    def _is_path_allowed(self, path: str) -> bool:
        target = Path(path).resolve()
        for allowed in self.allowed_paths:
            try:
                target.relative_to(allowed)
                return True
            except ValueError:
                continue
        return False

    async def start_server(self) -> bool:
        if not self.auto_start:
            return False

        try:
            import httpx

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.server_url}/health")
                if response.status_code == 200:
                    logger.info("OpenCode server already running")
                    return True
        except Exception:
            pass

        logger.info("Starting OpenCode server...")
        self._server_process = await asyncio.create_subprocess_exec(
            "opencode",
            "serve",
            "--port",
            self.server_url.split(":")[-1],
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.sleep(3)
        logger.info("OpenCode server started")
        return True

    async def execute(
        self,
        task_description: str,
        project_path: str = "./mobile_app",
    ) -> dict:
        if not self._is_path_allowed(project_path):
            return {"error": f"Path not allowed: {project_path}"}

        await self.start_server()

        try:
            import httpx

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.server_url}/v1/sessions",
                    json={
                        "prompt": task_description,
                        "working_directory": str(Path(project_path).resolve()),
                    },
                )
                response.raise_for_status()
                session_data = response.json()
                session_id = session_data.get("session_id") or session_data.get("id")

                if not session_id:
                    return {
                        "error": "Failed to create session",
                        "response": session_data,
                    }

                result = await self._wait_for_completion(session_id)
                return result

        except Exception as e:
            logger.error(f"OpenCode execution failed: {e}")
            return {"error": str(e)}

    async def _wait_for_completion(self, session_id: str) -> dict:
        import httpx

        poll_interval = 2
        max_polls = self.timeout // poll_interval

        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{self.server_url}/v1/sessions/{session_id}"
                    )
                    response.raise_for_status()
                    session = response.json()

                    state = session.get("state", "")
                    if state in ["completed", "done", "finished"]:
                        return {
                            "success": True,
                            "session_id": session_id,
                            "result": session.get("result", ""),
                            "files_changed": session.get("files_changed", []),
                        }
                    elif state in ["failed", "error"]:
                        return {
                            "success": False,
                            "session_id": session_id,
                            "error": session.get("error", "Unknown error"),
                        }
            except Exception as e:
                logger.warning(f"Poll failed: {e}")
                continue

        return {
            "success": False,
            "session_id": session_id,
            "error": "Task timed out",
        }

    async def run_command(
        self, prompt: str, project_path: str = "./mobile_app"
    ) -> dict:
        if not self._is_path_allowed(project_path):
            return {"error": f"Path not allowed: {project_path}"}

        try:
            process = await asyncio.create_subprocess_exec(
                "opencode",
                "run",
                "--format",
                "json",
                prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(Path(project_path).resolve()),
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout
            )

            if process.returncode == 0:
                return {
                    "success": True,
                    "output": stdout.decode("utf-8"),
                }
            else:
                return {
                    "success": False,
                    "error": stderr.decode("utf-8"),
                }
        except asyncio.TimeoutError:
            return {"error": "Command timed out"}
        except Exception as e:
            logger.error(f"OpenCode command failed: {e}")
            return {"error": str(e)}

    async def stop_server(self) -> bool:
        if self._server_process:
            self._server_process.terminate()
            try:
                await asyncio.wait_for(self._server_process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._server_process.kill()
            self._server_process = None
            logger.info("OpenCode server stopped")
            return True
        return False
