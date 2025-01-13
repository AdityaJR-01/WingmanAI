import os
import json
from openai import OpenAI
from datetime import datetime
from google.oauth2.credentials import Credentials # NEW: Import Credentials
from Tools.CalendarTool import GoogleCalendarTool # Update path if needed, keeping your current reference
from dotenv import load_dotenv 
load_dotenv()

class CalendarAgent:
    # 1. CRITICAL: Accept credentials object
    def __init__(self, credentials: Credentials):
        # Store credentials (if needed)
        self.credentials = credentials
        # Setup LLM client
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.today_date = datetime.today().strftime("%Y-%m-%d")
        # 2. CRITICAL: Instantiate the tool by passing the credentials
        self.CalendarTool = GoogleCalendarTool(credentials=credentials) 

    # 3. CRITICAL: Rename Calendar_Agent method to internal standard
    def _analyze_query_to_json(self, user_query):
        # The logic here remains the same: LLM translates query to JSON action
        system_prompt = (
            f"You are an AI assistant that helps manage calendar events.\n"
    f"Today's date is {self.today_date}. Interpret all dates in the user's query relative to this date.\n\n"

    "Always respond in **pure JSON format**, using double quotes and without any explanatory text. "
    "The expected JSON keys are:\n"
    '{\n'
    '  "action",\n'
    '  "event_name",\n'
    '  "start_time",\n'
    '  "end_time"\n'
    '}\n\n'

    "If the user is updating or deleting an event and hasn't specified the event name, start time, or end time, "
    "you must include two extra keys: \"potential_start\" and \"potential_end\". "
    "These define the time window for retrieving possible matching events.\n\n"

    "Supported actions:\n"
    "- \"create\": Schedule a new event.\n"
    "- \"update\": Modify an existing event at the specified time.\n"
    "- \"delete\": Remove an event. If no exact match is found, the system will extract nearby events for you to pick the most likely one.\n"
    "- \"check\": Verify if an event exists in the given time range.\n"
    "- \"extract\": Get scheduled events/tasks for today (default), tomorrow, or the week, depending on the user's request.\n\n"

    "Assumptions:\n"
    "- If the user doesn't provide an end time, assume the event lasts 1 hour from the start time.\n"
    "- If the user's request is ambiguous or missing critical information, ask follow-up questions.\n\n"

    "For updates and deletions, if no matching event is found, we will call the 'extract_event_details' function to show you the list of events. "
    "Analyze that list, pick the most likely match, and confirm it with the user before proceeding."
)
       
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query},
            ]
        )
        message = response.choices[0].message.content.strip()
        try:
            return json.loads(message)
        except json.JSONDecodeError:
            print("⚠ Error: Could not parse JSON.")
            return {"error": "Invalid JSON format from ChatGPT."}

    # 4. Standardized handle_query method
    def handle_query(self, user_query):
        print("Calendar Agent has recieved the query...")
        task = self._analyze_query_to_json(user_query) # Use the renamed analysis function
        print("Task:", task)
        response = self.handle_action(task)
        return response

    def normal_query(self, continual_query):
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Here is the response from the calendar API:"},
                {"role": "user", "content": continual_query},
            ]
        )
        return response.choices[0].message.content.strip()
    
    def handle_action(self, response_data):

        if "error" in response_data:
            return response_data["error"]

        action = response_data.get("action")
        event_name = response_data.get("event_name")
        start_time = response_data.get("start_time")
        end_time = response_data.get("end_time")

        if action == "create":
            print(f"📆 Creating '{event_name}' from {start_time} to {end_time}...")
            if event_name and start_time and end_time:
                response = self.CalendarTool.create_event(event_name, start_time, end_time)
                return response
            return "⚠ Missing event details for creation."

        elif action == "update":
            if event_name and start_time and end_time:
                print(f"📆 Updating '{event_name}' from {start_time} to {end_time}...")
                success = self.CalendarTool.update_event(event_name, start_time, end_time)
                if not success:
                    window_start = response_data.get("potential_start")
                    window_end = response_data.get("potential_end")
                    print(f"📆 Updating an event from {window_start} to {window_end}...")        
                    existing_events = self.CalendarTool.extract_schedule(window_start, window_end)
                    probable_event = self.normal_query(f"Which event best matches the specified event from the following based on event name, start time and end time whichever and whatever is available: {existing_events}?")
                    confirm = input(f"Do you want to update '{probable_event}'? (yes/no): ")
                    if confirm.lower() == "yes":
                        return self.CalendarTool.update_event(probable_event, start_time, end_time)
                    return "What do you want to update?"
                return "✅ Event updated successfully."

        elif action == "delete":
            if event_name:
                print(f"📆 Deleting '{event_name}'...")
                success = self.CalendarTool.delete_event(event_name)
            elif not event_name or not success:
                window_start = response_data.get("potential_start")
                window_end = response_data.get("potential_end")
                print(f"📆 Searching for event to delete from {window_start} to {window_end}...")
                existing_events = self.CalendarTool.extract_schedule(window_start, window_end)
                print(existing_events)

                probable_event = self.normal_query(
                    f"Which of these events best matches the user's intent to delete: {existing_events}? Reply only with the event name as it is."
                )
                confirm = input(f"Do you want to delete '{probable_event}'? (yes/no): ")

                if confirm.lower() == "yes":
                    event_details = self._analyze_query_to_json(
                        f"""From this selection: {existing_events}, the user wants to delete this event: {probable_event}.
                            Return the event details in the following JSON format ONLY:
                            {{
                            "event_name": "...",
                            "start_time": "YYYY-MM-DDTHH:MM:SS",
                            "end_time": "YYYY-MM-DDTHH:MM:SS"
                            }}"""
                    )
                    return self.CalendarTool.delete_event(event_details)
                else:
                    new_query = "That was not the event. " + reply
                    # Re-analyze the user's correction
                    new_task = self._analyze_query_to_json(new_query)
                    
                    if 'error' in new_task:
                        return f"❌ Error re-analyzing request: {new_task['error']}"
                    
                    # Execute the new, corrected action recursively
                    return self.handle_action(new_task) 

            return "✅ Event deleted successfully."
        
        elif action == "check":
            print(f"📆 Checking if any event exists from {start_time} to {end_time}...")
            events = self.CalendarTool.extract_event_details()
            return self.normal_query(f"Which events are scheduled in the specified time '{events}'?")
        
        elif action == "extract":
            print("📆 Extracting events...")
            return self.CalendarTool.extract_schedule(start_time, end_time) if start_time else "⚠ Missing event details."

        return "⚠ Invalid action type."
        # ... (inside handle_action) ...
        # Ensure any recursive call uses the renamed function:
        # e.g., in the delete logic:
        # return self.CalendarTool.delete_event(event_details) # this is fine
        
        # The recursive call in delete:
        # reply = input("Okay, what would you like to delete instead?\n")
        # return self._analyze_query_to_json("That was not the event. " + reply) # Use renamed function here
        
        # And in the update logic:
        # probable_event = self.normal_query(...) # Fine
        
        pass # Assuming all other logic is copied correctly