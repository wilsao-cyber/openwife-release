from skills.base_skill import BaseSkill
from tools.email_tool import EmailTool
from config import config


class EmailSkill(BaseSkill):
    def __init__(self):
        self._tool = EmailTool(config.email)

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "email_list",
                    "description": "列出收件件匣中的郵件 (List emails in inbox). 可以指定未讀或數量限制。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "回傳的郵件數量上限，預設 10",
                            },
                            "unread_only": {
                                "type": "boolean",
                                "description": "只列出未讀郵件，預設 false",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "email_send",
                    "description": "發送一封郵件 (Send an email). 需要提供收件人、主旨和內文。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "to": {
                                "type": "string",
                                "description": "收件人 Email 地址",
                            },
                            "subject": {"type": "string", "description": "郵件主旨"},
                            "body": {"type": "string", "description": "郵件內文"},
                        },
                        "required": ["to", "subject", "body"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "email_read",
                    "description": "讀取指定郵件的完整內容 (Read the full content of a specific email).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "email_id": {"type": "string", "description": "郵件 ID"},
                        },
                        "required": ["email_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "email_search",
                    "description": "搜尋郵件 (Search emails by keyword or query).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "搜尋關鍵字或查詢語句",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "回傳結果數量上限，預設 20",
                            },
                        },
                        "required": ["query"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "email_delete",
                    "description": "刪除指定郵件 (Delete an email).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "email_id": {
                                "type": "string",
                                "description": "要刪除的郵件 ID",
                            },
                        },
                        "required": ["email_id"],
                    },
                },
            },
        ]

    async def initialize(self):
        await self._tool.initialize()

    async def execute(self, tool_name: str, **kwargs) -> dict:
        dispatch = {
            "email_list": lambda: self._tool.list_emails(
                limit=kwargs.get("limit", 10),
                unread_only=kwargs.get("unread_only", False),
            ),
            "email_send": lambda: self._tool.send_email(
                to=kwargs["to"],
                subject=kwargs["subject"],
                body=kwargs["body"],
                cc=kwargs.get("cc"),
            ),
            "email_read": lambda: self._tool.read_email(
                email_id=kwargs["email_id"],
            ),
            "email_search": lambda: self._tool.search_emails(
                query=kwargs["query"],
                limit=kwargs.get("limit", 20),
            ),
            "email_delete": lambda: self._tool.delete_email(
                email_id=kwargs["email_id"],
            ),
        }
        method = dispatch.get(tool_name)
        if not method:
            return {"error": f"Unknown email tool: {tool_name}"}

        # Validate email_id for read/delete
        if tool_name in ("email_read", "email_delete"):
            eid = kwargs.get("email_id", "")
            if not eid or len(eid) < 10 or not eid.replace("-", "").replace("_", "").isalnum():
                # Numeric index → auto-fetch from list
                if eid.isdigit():
                    listing = await self._tool.list_emails(limit=10)
                    emails = listing.get("emails", [])
                    if not emails:
                        return {"error": "No emails found"}
                    idx = max(0, min(int(eid) - 1, len(emails) - 1))
                    kwargs["email_id"] = emails[idx]["id"]
                    if tool_name == "email_read":
                        method = lambda: self._tool.read_email(email_id=kwargs["email_id"])
                    else:
                        method = lambda: self._tool.delete_email(email_id=kwargs["email_id"])
                else:
                    return {"error": f"Invalid email_id: '{eid}'. Use email_list first to get valid IDs, or pass a number (1=first, 2=second)."}

        result = await method()
        # Add rich text media for email_read
        if tool_name == "email_read" and result.get("body"):
            subject = result.get("subject", "No subject")
            sender = result.get("from", "")
            date = result.get("date", "")
            body = result["body"]
            html = f"<h2>{subject}</h2><p><b>From:</b> {sender}<br><b>Date:</b> {date}</p><hr>{body}"
            result["media"] = [{"type": "richtext", "title": subject, "html": html}]
        return result
