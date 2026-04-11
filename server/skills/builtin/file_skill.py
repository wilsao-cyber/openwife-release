import os
from skills.base_skill import BaseSkill
from tools.file_ops_tool import FileOpsTool


class FileSkill(BaseSkill):
    def __init__(self):
        self._tool = FileOpsTool()

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "file_write",
                    "description": "建立或寫入檔案 (Create or write a file). content 參數要包含完整的檔案內容。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "檔案路徑，例如 ~/Downloads/note.txt",
                            },
                            "content": {
                                "type": "string",
                                "description": "要寫入的完整內容",
                            },
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file_read",
                    "description": "讀取檔案內容 (Read file contents). 回傳檔案的完整文字內容。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "檔案路徑"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file_list",
                    "description": "列出資料夾中的檔案和子資料夾 (List directory contents).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "資料夾路徑，預設 ~/Downloads",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file_delete",
                    "description": "刪除檔案或資料夾 (Delete file or directory). 請謹慎使用。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "要刪除的路徑"},
                        },
                        "required": ["path"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, **kwargs) -> dict:
        if "path" in kwargs:
            kwargs["path"] = os.path.expanduser(kwargs["path"])
        dispatch = {
            "file_write": self._tool.write_file,
            "file_read": self._tool.read_file,
            "file_list": self._tool.list_directory,
            "file_delete": self._tool.delete_file,
        }
        method = dispatch.get(tool_name)
        if not method:
            return {"error": f"Unknown file tool: {tool_name}"}
        result = await method(**kwargs)
        # Add rich text media for large file content
        if tool_name == "file_read" and result.get("content"):
            content = result["content"]
            if len(content) > 200:
                html = f"<pre style='white-space:pre-wrap;'>{content}</pre>"
                result["media"] = [{"type": "richtext", "title": kwargs.get("path", "File"), "html": html}]
        return result
