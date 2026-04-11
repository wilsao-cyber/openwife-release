"""
Code Skill — lets the AI write and execute Python scripts in a sandboxed environment.
Scripts are stored in scripts/ai_generated/ and executed via subprocess with timeout.
"""

import ast
import logging
import subprocess
from pathlib import Path
from skills.base_skill import BaseSkill

logger = logging.getLogger(__name__)

SCRIPTS_DIR = Path(__file__).parent.parent.parent.parent / "scripts" / "ai_generated"
SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)

# Modules that are not allowed in AI-generated scripts
BLOCKED_MODULES = {
    "shutil", "ctypes", "socket", "http.server",
    "xmlrpc", "ftplib", "smtplib", "telnetlib",
    "multiprocessing", "signal", "pty", "resource",
}

BLOCKED_ATTRIBUTES = {
    "system", "popen", "exec", "eval", "compile",
    "rmtree", "unlink", "remove", "rmdir",
    "kill", "terminate",
}

EXEC_TIMEOUT = 30  # seconds


def _check_code_safety(code: str) -> list[str]:
    """Static analysis: check for dangerous patterns. Returns list of violations."""
    violations = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [f"Syntax error: {e}"]

    for node in ast.walk(tree):
        # Check imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                mod = alias.name.split(".")[0]
                if mod in BLOCKED_MODULES:
                    violations.append(f"Blocked import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mod = node.module.split(".")[0]
                if mod in BLOCKED_MODULES:
                    violations.append(f"Blocked import: {node.module}")
        # Check dangerous function calls
        elif isinstance(node, ast.Attribute):
            if node.attr in BLOCKED_ATTRIBUTES:
                violations.append(f"Blocked attribute: .{node.attr}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in ("exec", "eval", "compile", "__import__"):
                violations.append(f"Blocked builtin: {node.func.id}()")

    return violations


class CodeSkill(BaseSkill):
    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "code_write",
                    "description": f"撰寫一個 Python 腳本並儲存到 {SCRIPTS_DIR}/ 目錄。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string", "description": "檔名（如 hello.py）"},
                            "code": {"type": "string", "description": "Python 程式碼"},
                        },
                        "required": ["filename", "code"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "code_execute",
                    "description": "執行一個已儲存的 Python 腳本（需使用者確認）。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filename": {"type": "string", "description": "要執行的腳本檔名"},
                        },
                        "required": ["filename"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "code_list",
                    "description": "列出所有已產生的腳本。",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

    async def execute(self, tool_name: str, **kwargs) -> dict:
        try:
            if tool_name == "code_write":
                return self._write(kwargs["filename"], kwargs["code"])
            elif tool_name == "code_execute":
                return self._execute(kwargs["filename"])
            elif tool_name == "code_list":
                return self._list()
            return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.error(f"CodeSkill {tool_name} failed: {e}")
            return {"error": str(e)}

    def _write(self, filename: str, code: str) -> dict:
        # Sanitize filename
        safe = Path(filename).name
        if not safe.endswith(".py"):
            safe += ".py"

        # Safety check
        violations = _check_code_safety(code)
        if violations:
            return {"error": f"程式碼安全檢查未通過：\n" + "\n".join(f"- {v}" for v in violations)}

        path = SCRIPTS_DIR / safe
        path.write_text(code, encoding="utf-8")
        logger.info(f"AI script saved: {path}")
        return {"content": f"腳本已儲存：{safe}\n路徑：{path}\n\n使用 code_execute 來執行。"}

    def _execute(self, filename: str) -> dict:
        safe = Path(filename).name
        path = SCRIPTS_DIR / safe
        if not path.exists():
            return {"error": f"腳本不存在：{safe}"}

        # Re-check safety before execution
        code = path.read_text(encoding="utf-8")
        violations = _check_code_safety(code)
        if violations:
            return {"error": f"腳本安全檢查未通過：\n" + "\n".join(f"- {v}" for v in violations)}

        try:
            result = subprocess.run(
                ["python3", str(path)],
                capture_output=True,
                text=True,
                timeout=EXEC_TIMEOUT,
                cwd=str(SCRIPTS_DIR),
            )
            output = ""
            if result.stdout:
                output += f"stdout:\n{result.stdout[:2000]}\n"
            if result.stderr:
                output += f"stderr:\n{result.stderr[:1000]}\n"
            if result.returncode != 0:
                output += f"Exit code: {result.returncode}"
            return {"content": output or "(無輸出)"}
        except subprocess.TimeoutExpired:
            return {"error": f"腳本執行超時（{EXEC_TIMEOUT}秒限制）"}

    def _list(self) -> dict:
        files = sorted(SCRIPTS_DIR.glob("*.py"))
        if not files:
            return {"content": "目前沒有已產生的腳本。"}
        lines = []
        for f in files:
            size = f.stat().st_size
            lines.append(f"- {f.name} ({size} bytes)")
        return {"content": "\n".join(lines)}
