import asyncio
import logging
import imaplib
import email
from email.header import decode_header
from typing import Optional
from config import EmailConfig
from auth.gmail_oauth import GmailAuth

logger = logging.getLogger(__name__)


class EmailTool:
    def __init__(self, config: EmailConfig):
        self.config = config
        self.provider = config.provider
        self.credentials_path = config.credentials_path
        self.token_path = config.token_path
        self._gmail_service = None
        self._imap_connection = None

    async def initialize(self):
        if self.provider == "gmail":
            self._gmail_service = GmailAuth(self.credentials_path, self.token_path)
            await self._gmail_service.authenticate()
        logger.info(f"Email tool initialized with provider: {self.provider}")

    async def list_emails(
        self,
        limit: int = 20,
        unread_only: bool = False,
        folder: str = "INBOX",
    ) -> dict:
        if self.provider == "gmail":
            return await self._list_gmail(limit, unread_only)
        else:
            return await self._list_imap(limit, unread_only, folder)

    async def read_email(self, email_id: str) -> dict:
        if self.provider == "gmail":
            return await self._read_gmail(email_id)
        else:
            return await self._read_imap(email_id)

    async def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        attachments: Optional[list[str]] = None,
    ) -> dict:
        if self.provider == "gmail":
            return await self._send_gmail(to, subject, body, cc)
        else:
            return await self._send_smtp(to, subject, body, cc)

    async def search_emails(
        self,
        query: str,
        limit: int = 20,
    ) -> dict:
        if self.provider == "gmail":
            return await self._search_gmail(query, limit)
        else:
            return await self._search_imap(query, limit)

    async def delete_email(self, email_id: str) -> dict:
        if self.provider == "gmail":
            return await self._delete_gmail(email_id)
        else:
            return await self._delete_imap(email_id)

    async def _list_gmail(self, limit: int, unread_only: bool) -> dict:
        try:
            q = "is:unread" if unread_only else ""
            results = await asyncio.to_thread(
                self._gmail_service.users()
                .messages()
                .list(userId="me", maxResults=limit, q=q)
                .execute
            )
            messages = results.get("messages", [])
            emails_list = []
            for msg in messages:
                detail = await asyncio.to_thread(
                    self._gmail_service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=msg["id"],
                        format="metadata",
                        metadataHeaders=["From", "Subject", "Date"],
                    )
                    .execute
                )
                headers = detail.get("payload", {}).get("headers", [])
                emails_list.append(
                    {
                        "id": msg["id"],
                        "subject": self._get_header(headers, "Subject"),
                        "from": self._get_header(headers, "From"),
                        "date": self._get_header(headers, "Date"),
                        "snippet": detail.get("snippet", ""),
                    }
                )
            return {"emails": emails_list, "total": len(emails_list)}
        except Exception as e:
            logger.error(f"Gmail list failed: {e}")
            return {"error": str(e)}

    async def _read_gmail(self, email_id: str) -> dict:
        try:
            msg = await asyncio.to_thread(
                self._gmail_service.users()
                .messages()
                .get(userId="me", id=email_id, format="full")
                .execute
            )
            body = self._extract_body(msg)
            return {
                "id": email_id,
                "subject": self._get_header(msg["payload"]["headers"], "Subject"),
                "from": self._get_header(msg["payload"]["headers"], "From"),
                "date": self._get_header(msg["payload"]["headers"], "Date"),
                "body": body,
            }
        except Exception as e:
            logger.error(f"Gmail read failed: {e}")
            return {"error": str(e)}

    async def _send_gmail(
        self, to: str, subject: str, body: str, cc: Optional[str]
    ) -> dict:
        try:
            from email.message import EmailMessage

            msg = EmailMessage()
            msg.set_content(body)
            msg["To"] = to
            msg["Subject"] = subject
            if cc:
                msg["Cc"] = cc

            import base64

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            result = await asyncio.to_thread(
                self._gmail_service.users()
                .messages()
                .send(userId="me", body={"raw": raw})
                .execute
            )
            return {"success": True, "message_id": result["id"]}
        except Exception as e:
            logger.error(f"Gmail send failed: {e}")
            return {"error": str(e)}

    async def _search_gmail(self, query: str, limit: int) -> dict:
        try:
            results = await asyncio.to_thread(
                self._gmail_service.users()
                .messages()
                .list(userId="me", maxResults=limit, q=query)
                .execute
            )
            messages = results.get("messages", [])
            return {"emails": messages, "total": len(messages)}
        except Exception as e:
            logger.error(f"Gmail search failed: {e}")
            return {"error": str(e)}

    async def _delete_gmail(self, email_id: str) -> dict:
        try:
            await asyncio.to_thread(
                self._gmail_service.users()
                .messages()
                .trash(userId="me", id=email_id)
                .execute
            )
            return {"success": True, "message_id": email_id}
        except Exception as e:
            logger.error(f"Gmail delete failed: {e}")
            return {"error": str(e)}

    async def _list_imap(self, limit: int, unread_only: bool, folder: str) -> dict:
        return {"emails": [], "total": 0, "note": "IMAP not fully implemented"}

    async def _read_imap(self, email_id: str) -> dict:
        return {"error": "IMAP not fully implemented"}

    async def _send_smtp(
        self, to: str, subject: str, body: str, cc: Optional[str]
    ) -> dict:
        return {"error": "SMTP not fully implemented"}

    async def _search_imap(self, query: str, limit: int) -> dict:
        return {"emails": [], "total": 0}

    async def _delete_imap(self, email_id: str) -> dict:
        return {"error": "IMAP not fully implemented"}

    def _get_header(self, headers: list, name: str) -> str:
        for h in headers:
            if h["name"].lower() == name.lower():
                return h["value"]
        return ""

    def _extract_body(self, msg: dict) -> str:
        import base64

        def _decode(data: str) -> str:
            if not data:
                return ""
            try:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            except Exception:
                return ""

        def _extract_from_parts(parts: list) -> str:
            plain = ""
            html = ""
            for part in parts:
                mime = part.get("mimeType", "")
                # Recurse into nested multipart
                if "parts" in part:
                    nested = _extract_from_parts(part["parts"])
                    if nested:
                        return nested
                data = part.get("body", {}).get("data", "")
                if mime == "text/plain" and not plain:
                    plain = _decode(data)
                elif mime == "text/html" and not html:
                    html = _decode(data)
            if plain:
                return plain
            if html:
                # Strip HTML tags for a readable text version
                import re
                text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text
            return ""

        payload = msg.get("payload", {})
        if "parts" in payload:
            return _extract_from_parts(payload["parts"])
        elif "body" in payload:
            return _decode(payload["body"].get("data", ""))
        return ""
