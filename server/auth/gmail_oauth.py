import logging
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


class GmailAuth:
    def __init__(self, credentials_path: str, token_path: str):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._service = None

    async def authenticate(self):
        creds = self._load_credentials()
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self._save_credentials(creds)
            else:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(
                        f"OAuth credentials not found at {self.credentials_path}. "
                        "Download from GCP Console: APIs & Services > Credentials > OAuth Client ID"
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=9999, open_browser=True)
                self._save_credentials(creds)

        self._service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail authenticated successfully")

    def _load_credentials(self):
        if os.path.exists(self.token_path):
            try:
                return Credentials.from_authorized_user_file(self.token_path, SCOPES)
            except Exception as e:
                logger.warning(f"Failed to load Gmail token: {e}")
                os.remove(self.token_path)
        return None

    def _save_credentials(self, creds):
        os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
        with open(self.token_path, "w") as token:
            token.write(creds.to_json())

    def users(self):
        if not self._service:
            raise RuntimeError("Gmail not authenticated. Call authenticate() first.")
        return self._service.users()
