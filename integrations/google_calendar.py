"""
Google Calendar API integration for bidirectional sync.

Handles OAuth2 authentication, event creation, update, deletion,
and incremental sync from Google Calendar.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class GoogleCalendarService:
    """Service for interacting with Google Calendar API."""

    SCOPES = ["https://www.googleapis.com/auth/calendar"]

    def __init__(self, integration=None):
        """
        Initialize with optional GoogleCalendarIntegration instance.

        Args:
            integration: GoogleCalendarIntegration model instance.
        """
        self.integration = integration

    def get_auth_url(self, redirect_uri):
        """
        Generate the OAuth2 authorization URL.

        Args:
            redirect_uri: The callback URL after Google auth.

        Returns:
            Authorization URL string.
        """
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=self.SCOPES,
            redirect_uri=redirect_uri,
        )

        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
        )
        return auth_url

    def exchange_code(self, code, redirect_uri):
        """
        Exchange authorization code for access/refresh tokens.

        Args:
            code: Authorization code from Google callback.
            redirect_uri: Same redirect_uri used in get_auth_url.

        Returns:
            Dict with access_token, refresh_token, token_expiry.
        """
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            },
            scopes=self.SCOPES,
            redirect_uri=redirect_uri,
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        return {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_expiry": credentials.expiry,
        }

    def _get_credentials(self):
        """Build google.oauth2.credentials.Credentials from stored tokens."""
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=self.integration.access_token,
            refresh_token=self.integration.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CALENDAR_CLIENT_ID,
            client_secret=settings.GOOGLE_CALENDAR_CLIENT_SECRET,
        )

        # Refresh if expired
        if self.integration.token_expiry <= timezone.now():
            from google.auth.transport.requests import Request

            creds.refresh(Request())
            self.integration.access_token = creds.token
            self.integration.token_expiry = creds.expiry
            self.integration.save(
                update_fields=["access_token", "token_expiry", "updated_at"]
            )

        return creds

    def _get_service(self):
        """Build the Google Calendar API service."""
        from googleapiclient.discovery import build

        creds = self._get_credentials()
        return build("calendar", "v3", credentials=creds)

    def push_event(self, calendar_event):
        """
        Create or update an event in Google Calendar.

        Args:
            calendar_event: CalendarEvent model instance.

        Returns:
            Google Calendar event ID.
        """
        service = self._get_service()

        body = {
            "summary": calendar_event.title,
            "description": calendar_event.description,
            "start": {
                "dateTime": calendar_event.start_time.isoformat(),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": calendar_event.end_time.isoformat(),
                "timeZone": "UTC",
            },
        }

        if calendar_event.location:
            body["location"] = calendar_event.location

        # Check if event already has a Google Calendar ID
        google_id = calendar_event.google_event_id or None

        if google_id:
            event = (
                service.events()
                .update(
                    calendarId=self.integration.calendar_id,
                    eventId=google_id,
                    body=body,
                )
                .execute()
            )
        else:
            event = (
                service.events()
                .insert(
                    calendarId=self.integration.calendar_id,
                    body=body,
                )
                .execute()
            )
            # Persist the new Google event ID back to the local record
            calendar_event.google_event_id = event["id"]
            calendar_event.save(update_fields=["google_event_id", "updated_at"])

        return event["id"]

    def delete_event(self, google_event_id):
        """Delete an event from Google Calendar."""
        service = self._get_service()
        service.events().delete(
            calendarId=self.integration.calendar_id,
            eventId=google_event_id,
        ).execute()

    def pull_events(self):
        """
        Pull events from Google Calendar using incremental sync.

        Uses sync tokens to only fetch changed events since last sync.

        Returns:
            List of Google Calendar event dicts.
        """
        service = self._get_service()

        kwargs = {
            "calendarId": self.integration.calendar_id,
            "singleEvents": True,
            "orderBy": "startTime",
        }

        if self.integration.sync_token:
            kwargs["syncToken"] = self.integration.sync_token
        else:
            # First sync: pull events from 30 days ago to 90 days ahead
            now = timezone.now()
            kwargs["timeMin"] = (now - timedelta(days=30)).isoformat()
            kwargs["timeMax"] = (now + timedelta(days=90)).isoformat()

        all_events = []
        page_token = None

        while True:
            if page_token:
                kwargs["pageToken"] = page_token

            try:
                result = service.events().list(**kwargs).execute()
            except Exception as e:
                # If sync token is invalid, do a full sync
                if "fullSyncRequired" in str(e) or "410" in str(e):
                    logger.warning(
                        "Full sync required for user %s", self.integration.user.email
                    )
                    self.integration.sync_token = ""
                    self.integration.save(update_fields=["sync_token"])
                    return self.pull_events()
                raise

            all_events.extend(result.get("items", []))
            page_token = result.get("nextPageToken")

            if not page_token:
                # Save sync token for next incremental sync
                new_sync_token = result.get("nextSyncToken", "")
                if new_sync_token:
                    self.integration.sync_token = new_sync_token
                    self.integration.last_sync_at = timezone.now()
                    self.integration.save(
                        update_fields=["sync_token", "last_sync_at", "updated_at"]
                    )
                break

        return all_events
