import os
import json
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from app.core.config import settings
from app.models.setting import AppSetting
from app.models.meeting import Meeting
from app.models.intern import Intern
from app.models.log import AuditLog

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar"
]

SETTING_KEY_GOOGLE_TOKEN = "google_calendar_oauth_token"

class GoogleCalendarService:
    def __init__(self):
        self.client_id = settings.GOOGLE_CLIENT_ID
        self.client_secret = settings.GOOGLE_CLIENT_SECRET
        self.redirect_uri = settings.GOOGLE_REDIRECT_URI

    def is_configured(self) -> bool:
        """Checks if Google OAuth app credentials are provided in .env."""
        return bool(self.client_id and self.client_secret and self.client_id.strip() and self.client_secret.strip())

    def get_status(self, db: Session) -> Dict[str, Any]:
        """Returns OAuth configuration and authorization status."""
        configured = self.is_configured()
        authorized = False
        token_info = None

        if configured:
            token_setting = db.query(AppSetting).filter(AppSetting.key == SETTING_KEY_GOOGLE_TOKEN).first()
            if token_setting and token_setting.value:
                try:
                    data = json.loads(token_setting.value)
                    authorized = bool(data.get("token") or data.get("refresh_token"))
                    token_info = {
                        "expiry": data.get("expiry"),
                        "has_refresh_token": bool(data.get("refresh_token"))
                    }
                except Exception:
                    authorized = False

        status_text = "Authorized & Ready" if authorized else (
            "Credentials Present (Authorization Required)" if configured else "Setup Required (client_id / client_secret needed in .env)"
        )

        return {
            "configured": configured,
            "authorized": authorized,
            "status_text": status_text,
            "redirect_uri": self.redirect_uri,
            "token_info": token_info
        }

    def get_authorization_url(self) -> Tuple[Optional[str], Optional[str]]:
        """Generates Google OAuth 2.0 authorization URL."""
        if not self.is_configured():
            return None, "Google OAuth client_id and client_secret are not configured in .env."

        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }

        try:
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=self.redirect_uri
            )
            auth_url, state = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent"
            )
            return auth_url, None
        except Exception as e:
            return None, str(e)

    def handle_auth_callback(self, code: str, db: Session) -> Tuple[bool, str]:
        """Exchanges authorization code for tokens and persists in database."""
        if not self.is_configured():
            return False, "Google OAuth credentials not configured."

        client_config = {
            "web": {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [self.redirect_uri]
            }
        }

        try:
            flow = Flow.from_client_config(
                client_config,
                scopes=SCOPES,
                redirect_uri=self.redirect_uri
            )
            flow.fetch_token(code=code)
            credentials = flow.credentials

            token_data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
                "expiry": credentials.expiry.isoformat() if credentials.expiry else None
            }

            setting = db.query(AppSetting).filter(AppSetting.key == SETTING_KEY_GOOGLE_TOKEN).first()
            if not setting:
                setting = AppSetting(
                    key=SETTING_KEY_GOOGLE_TOKEN,
                    value=json.dumps(token_data),
                    description="Google Calendar OAuth 2.0 Tokens"
                )
                db.add(setting)
            else:
                setting.value = json.dumps(token_data)

            db.commit()
            return True, "Google Calendar authorization successful."
        except Exception as e:
            return False, f"Token exchange failed: {str(e)}"

    def _get_calendar_client(self, db: Session) -> Optional[Any]:
        """Constructs authenticated Google Calendar Resource client."""
        setting = db.query(AppSetting).filter(AppSetting.key == SETTING_KEY_GOOGLE_TOKEN).first()
        if not setting or not setting.value:
            return None

        try:
            token_data = json.loads(setting.value)
            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=token_data.get("client_id", self.client_id),
                client_secret=token_data.get("client_secret", self.client_secret),
                scopes=token_data.get("scopes", SCOPES)
            )
            service = build("calendar", "v3", credentials=creds)
            return service
        except Exception as e:
            logger.error(f"Failed to build Google Calendar client: {e}")
            return None

    def create_meeting_event(
        self,
        meeting: Meeting,
        attendee_emails: List[str],
        db: Session
    ) -> Dict[str, Any]:
        """
        Creates genuine Google Calendar event with Hangouts/Google Meet conferenceData.
        NEVER generates fake URLs. If not authorized, reports setup required.
        """
        calendar_client = self._get_calendar_client(db)
        if not calendar_client:
            status_info = self.get_status(db)
            return {
                "success": False,
                "google_synced": False,
                "google_meet_url": None,
                "status_text": "Setup Required: Authorize Google OAuth to create genuine Google Meet links.",
                "details": status_info["status_text"]
            }

        start_time = meeting.scheduled_time
        end_time = start_time + timedelta(minutes=meeting.duration_minutes)

        event_body = {
            "summary": meeting.title,
            "description": meeting.description or "InternFlow AI Technical Review & Sync",
            "start": {
                "dateTime": start_time.isoformat(),
                "timeZone": "UTC"
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": "UTC"
            },
            "attendees": [{"email": email} for email in attendee_emails if email],
            "conferenceData": {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {
                        "type": "hangoutsMeet"
                    }
                }
            },
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 60},
                    {"method": "popup", "minutes": 15}
                ]
            }
        }

        try:
            created_event = calendar_client.events().insert(
                calendarId="primary",
                body=event_body,
                conferenceDataVersion=1
            ).execute()

            # Extract genuine Google Meet URL
            meet_url = None
            conf_data = created_event.get("conferenceData", {})
            entry_points = conf_data.get("entryPoints", [])
            for ep in entry_points:
                if ep.get("entryPointType") == "video":
                    meet_url = ep.get("uri")
                    break

            meeting.google_event_id = created_event.get("id")
            meeting.google_meet_url = meet_url
            meeting.is_google_calendar_synced = True
            if meet_url:
                meeting.meeting_link = meet_url

            db.commit()

            return {
                "success": True,
                "google_synced": True,
                "event_id": created_event.get("id"),
                "google_meet_url": meet_url,
                "html_link": created_event.get("htmlLink")
            }
        except Exception as e:
            logger.error(f"Google Calendar event creation failed: {e}")
            return {
                "success": False,
                "google_synced": False,
                "google_meet_url": None,
                "error": str(e)
            }

    def cancel_meeting_event(self, meeting: Meeting, db: Session) -> bool:
        """Cancels event from Google Calendar."""
        if not meeting.google_event_id:
            return False

        calendar_client = self._get_calendar_client(db)
        if not calendar_client:
            return False

        try:
            calendar_client.events().delete(
                calendarId="primary",
                eventId=meeting.google_event_id
            ).execute()
            meeting.status = "cancelled"
            db.commit()
            return True
        except Exception as e:
            logger.error(f"Google Calendar cancel failed: {e}")
            return False

google_calendar_service = GoogleCalendarService()
