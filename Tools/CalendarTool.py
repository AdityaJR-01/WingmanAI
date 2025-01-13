import os
import json
from datetime import datetime, timezone, timedelta
from google.oauth2.credentials import Credentials # Keep for type hinting
from google.auth.transport.requests import Request # Keep for internal Creds use if needed, but not for refresh
from googleapiclient.discovery import build
from typing import List, Dict, Optional # Import typing modules

# REMOVE: load_dotenv()

class GoogleCalendarTool:
    SCOPES = ["https://www.googleapis.com/auth/calendar"] 
    CALENDAR_ID = "primary"

    # 2. CRITICAL: Accept Credentials object
    def __init__(self, credentials: Credentials):
        """Initialize with a guaranteed valid Credentials object."""
        self.credentials = credentials
        self.service = self._get_service()

    # 3. CRITICAL: Replace authenticate() with simplified service getter
    def _get_service(self):
        """Build the Google Calendar API service using the provided Credentials."""
        try:
            # The credentials object is guaranteed to be refreshed by the Director/Token Manager
            return build("calendar", "v3", credentials=self.credentials)
        except Exception as e:
            # You should log this error for debugging
            print(f"Error building Calendar service: {e}") 
            raise
    def extract_event_details(self, start_time=None, end_time=None):
        """Fetch events from Google Calendar in a date range."""
        start_dt = datetime.utcnow() if not start_time else datetime.fromisoformat(start_time.replace("Z", ""))
        end_dt = start_dt + timedelta(days=7) if not end_time else datetime.fromisoformat(end_time.replace("Z", ""))

        time_min = start_dt.isoformat() + "Z"
        time_max = end_dt.isoformat() + "Z"

        events_result = (
            self.service.events()
            .list(
                calendarId=self.CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=50,
                singleEvents=True,
                orderBy="startTime"
            )
            .execute()
        )

        events = events_result.get("items", [])
        if not events:
            return "No events found in the specified range."

        return [
            {
                "event_name": event.get("summary", "Unnamed Event"),
                "start_time": event["start"].get("dateTime", event["start"].get("date")),
                "end_time": event["end"].get("dateTime", event["end"].get("date")),
                "event_id": event["id"]
            }
            for event in events
        ]
    
    def create_event(self, event_name, start_time, end_time):
        print("Creating the event...")
        """Creates a new calendar event."""
        event = {
            "summary": event_name,
            "start": {"dateTime": start_time, "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": end_time, "timeZone": "Asia/Kolkata"},
        }
        created_event = self.service.events().insert(calendarId=self.CALENDAR_ID, body=event).execute()
        return created_event.get("htmlLink")
    
    def update_event(self, event_name, new_start_time, new_end_time):
        """Updates an existing calendar event."""
        events = self.extract_event_details()

        match = next((e for e in events if e["event_name"].lower() == event_name.lower()), None)
        if not match:
            return "⚠ No event found with that name."

        updated_event = {
            "event_name": match["event_name"],
            "start": {"dateTime": new_start_time, "timeZone": "Asia/Kolkata"},
            "end": {"dateTime": new_end_time, "timeZone": "Asia/Kolkata"},
        }

        self.service.events().patch(
            calendarId=self.CALENDAR_ID,
            eventId=match["event_id"],
            body=updated_event
        ).execute()

        return "✅ Event updated successfully."
    
    def extract_schedule(self, start_time, end_time=None):
        """Fetch events between start and end time (ISO format)."""
        start_dt = datetime.fromisoformat(start_time)
        end_dt = start_dt + timedelta(days=7) if not end_time else datetime.fromisoformat(end_time)

        time_min = start_dt.astimezone(timezone.utc).isoformat()
        time_max = end_dt.astimezone(timezone.utc).isoformat()

        events_result = (
            self.service.events()
            .list(
                calendarId=self.CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        if not events:
            return "📅 No events found in the given range."

        return [
            {
                "event_name": event.get("summary", "Unnamed Event"),
                "start_time": event["start"].get("dateTime", event["start"].get("date")),
                "end_time": event["end"].get("dateTime", event["end"].get("date")),
                "event_id": event["id"]
            }
            for event in events
        ]

    def delete_event(self, event_input):
        """Delete a Google Calendar event by name or full detail."""
        events = self.extract_event_details()

        if isinstance(event_input, str):
            matches = [e for e in events if e["event_name"].lower() == event_input.lower()]
        elif isinstance(event_input, dict):
            name = event_input.get("event_name", "").lower()
            start = event_input.get("start_time")
            end = event_input.get("end_time")
            matches = [
                e for e in events
                if e["event_name"].lower() == name and e["start_time"] == start and e["end_time"] == end
            ]
        else:
            return "❌ Invalid input format for deleting an event."

        if not matches:
            return "⚠️ No matching event found for deletion."

        for event in matches:
            self.service.events().delete(calendarId=self.CALENDAR_ID, eventId=event["event_id"]).execute()

        return f"🗑️ Deleted {len(matches)} event(s) successfully."
