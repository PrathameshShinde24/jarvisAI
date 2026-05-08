"""
tools/productivity.py — Gmail + Google Calendar tools (Phase 5).

Requires Google OAuth — see README for setup steps.
Credentials JSON saved to data/credentials.json (git-ignored).

Tools:
  - list_emails(max_results)
  - send_email(to, subject, body)        ← requires verbal confirmation
  - list_calendar_events(max_results)
  - create_calendar_event(summary, start, end, description)  ← requires confirmation
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# OAuth token storage (git-ignored)
TOKEN_PATH = Path(__file__).parent.parent / "data" / "google_token.json"
CREDENTIALS_PATH = Path(__file__).parent.parent / "data" / "credentials.json"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
]

# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "list_emails",
        "description": "List recent unread emails showing sender and subject.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Number of emails to return (default 5)."}
            },
            "required": [],
        },
    },
    {
        "name": "send_email",
        "description": "Send an email. ALWAYS confirm details with the user before calling this.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string", "description": "Recipient email address."},
                "subject": {"type": "string", "description": "Email subject line."},
                "body": {"type": "string", "description": "Plain-text email body."},
            },
            "required": ["to", "subject", "body"],
        },
    },
    {
        "name": "list_calendar_events",
        "description": "List upcoming Google Calendar events.",
        "input_schema": {
            "type": "object",
            "properties": {
                "max_results": {"type": "integer", "description": "Number of events to return (default 5)."}
            },
            "required": [],
        },
    },
    {
        "name": "create_calendar_event",
        "description": "Create a Google Calendar event. ALWAYS confirm details with the user first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "Event title."},
                "start": {"type": "string", "description": "Start time in ISO 8601 format, e.g. 2025-06-01T14:00:00."},
                "end": {"type": "string", "description": "End time in ISO 8601 format."},
                "description": {"type": "string", "description": "Optional event description."},
            },
            "required": ["summary", "start", "end"],
        },
    },
]

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _get_google_service(api: str, version: str):
    """Return an authenticated Google API service client."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
    return build(api, version, credentials=creds)

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def list_emails(inputs: dict[str, Any]) -> str:
    max_results = inputs.get("max_results", 5)
    try:
        service = _get_google_service("gmail", "v1")
        msgs = service.users().messages().list(
            userId="me", labelIds=["UNREAD"], maxResults=max_results
        ).execute().get("messages", [])

        if not msgs:
            return "No unread emails."

        summaries = []
        for m in msgs:
            detail = service.users().messages().get(userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject"]).execute()
            headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
            summaries.append(f"From {headers.get('From', '?')}: {headers.get('Subject', '(no subject)')}")
        return "\n".join(summaries)
    except Exception as exc:
        return f"Couldn't list emails: {exc}"


def send_email(inputs: dict[str, Any]) -> str:
    import base64
    from email.mime.text import MIMEText
    try:
        service = _get_google_service("gmail", "v1")
        msg = MIMEText(inputs["body"])
        msg["to"] = inputs["to"]
        msg["subject"] = inputs["subject"]
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return f"Email sent to {inputs['to']}."
    except Exception as exc:
        return f"Couldn't send email: {exc}"


def list_calendar_events(inputs: dict[str, Any]) -> str:
    from datetime import datetime, timezone
    max_results = inputs.get("max_results", 5)
    try:
        service = _get_google_service("calendar", "v3")
        now = datetime.now(timezone.utc).isoformat()
        events = service.events().list(
            calendarId="primary", timeMin=now, maxResults=max_results,
            singleEvents=True, orderBy="startTime"
        ).execute().get("items", [])

        if not events:
            return "No upcoming events."
        lines = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date", "?"))
            lines.append(f"{start}: {e.get('summary', '(no title)')}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Couldn't list events: {exc}"


def create_calendar_event(inputs: dict[str, Any]) -> str:
    try:
        service = _get_google_service("calendar", "v3")
        event = {
            "summary": inputs["summary"],
            "description": inputs.get("description", ""),
            "start": {"dateTime": inputs["start"], "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": inputs["end"], "timeZone": "Asia/Kolkata"},
        }
        created = service.events().insert(calendarId="primary", body=event).execute()
        return f"Event created: {created.get('summary')} on {inputs['start']}."
    except Exception as exc:
        return f"Couldn't create event: {exc}"


# ---------------------------------------------------------------------------
# Handler registry
# ---------------------------------------------------------------------------

TOOL_HANDLERS: dict[str, Any] = {
    "list_emails": list_emails,
    "send_email": send_email,
    "list_calendar_events": list_calendar_events,
    "create_calendar_event": create_calendar_event,
}
