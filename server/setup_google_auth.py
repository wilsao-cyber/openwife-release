#!/usr/bin/env python3
"""
Setup Google OAuth for Gmail and Calendar.

Prerequisites:
1. Go to https://console.cloud.google.com/apis/credentials/consent?project=ai-wife-app-2026
   - Choose External -> Create
   - App name: AI Wife App, email: your email
   - Add scopes: Gmail API, Calendar API
   - Add test user: your email
   - Save

2. Go to https://console.cloud.google.com/apis/credentials?project=ai-wife-app-2026
   - Create Credentials -> OAuth Client ID -> Desktop app
   - Download JSON -> save as ../config/credentials.json

3. Run this script: python setup_google_auth.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

CREDENTIALS_PATH = "../config/credentials.json"
GMAIL_TOKEN_PATH = "../config/gmail_token.json"
CALENDAR_TOKEN_PATH = "../config/calendar_token.json"

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


def check_credentials():
    if not os.path.exists(CREDENTIALS_PATH):
        print(f"ERROR: {CREDENTIALS_PATH} not found!")
        print("Download from GCP Console: APIs & Services > Credentials > OAuth Client ID")
        return False

    import json
    with open(CREDENTIALS_PATH) as f:
        data = json.load(f)

    client_id = data.get("installed", data.get("web", {})).get("client_id", "")
    if "YOUR_CLIENT_ID" in client_id:
        print("ERROR: credentials.json still has placeholder values!")
        print("Replace with real OAuth credentials from GCP Console.")
        return False

    print(f"✓ credentials.json found (client_id: {client_id[:30]}...)")
    return True


def authenticate_gmail():
    print("\n--- Gmail Authentication ---")
    creds = None
    if os.path.exists(GMAIL_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(GMAIL_TOKEN_PATH, GMAIL_SCOPES)

    if creds and creds.valid:
        print("✓ Gmail already authenticated")
        return True

    if creds and creds.expired and creds.refresh_token:
        print("Refreshing Gmail token...")
        creds.refresh(Request())
    else:
        print("Opening browser for Gmail authorization...")
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, GMAIL_SCOPES)
        creds = flow.run_local_server(port=9999, open_browser=True)

    os.makedirs(os.path.dirname(GMAIL_TOKEN_PATH), exist_ok=True)
    with open(GMAIL_TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    # Verify
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    print(f"✓ Gmail authenticated as: {profile.get('emailAddress')}")
    return True


def authenticate_calendar():
    print("\n--- Calendar Authentication ---")
    creds = None
    if os.path.exists(CALENDAR_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(CALENDAR_TOKEN_PATH, CALENDAR_SCOPES)

    if creds and creds.valid:
        print("✓ Calendar already authenticated")
        return True

    if creds and creds.expired and creds.refresh_token:
        print("Refreshing Calendar token...")
        creds.refresh(Request())
    else:
        print("Opening browser for Calendar authorization...")
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, CALENDAR_SCOPES)
        creds = flow.run_local_server(port=9998, open_browser=True)

    os.makedirs(os.path.dirname(CALENDAR_TOKEN_PATH), exist_ok=True)
    with open(CALENDAR_TOKEN_PATH, "w") as f:
        f.write(creds.to_json())

    # Verify
    service = build("calendar", "v3", credentials=creds)
    calendars = service.calendarList().list(maxResults=3).execute()
    items = calendars.get("items", [])
    print(f"✓ Calendar authenticated, found {len(items)} calendars")
    for cal in items[:3]:
        print(f"  - {cal.get('summary', 'Untitled')}")
    return True


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=== AI Wife App - Google OAuth Setup ===\n")

    if not check_credentials():
        sys.exit(1)

    gmail_ok = authenticate_gmail()
    calendar_ok = authenticate_calendar()

    print("\n=== Summary ===")
    print(f"Gmail:    {'✓ Ready' if gmail_ok else '✗ Failed'}")
    print(f"Calendar: {'✓ Ready' if calendar_ok else '✗ Failed'}")

    if gmail_ok and calendar_ok:
        print("\nAll set! Start the server with: python main.py")
