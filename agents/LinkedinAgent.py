import os
import json
from openai import OpenAI
from dotenv import load_dotenv
from Tools.LinkedinTool import LinkedInTool # NEW Import
from google.oauth2.credentials import Credentials as GoogleCredentials # Import GoogleCredentials for type hint
# NEW Imports for scheduling logic (needed later for schedule_post)
import schedule
import time 
from datetime import datetime
from typing import Dict, Any 
import sys
import re

load_dotenv()

class LinkedinAgent:
    # 1. CRITICAL: Standardized __init__ signature
    # We expect the Director to pass the LinkedIn token/ID in this 'credentials' dict
    def __init__(self, credentials: Dict[str, Any]): 
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # 2. CRITICAL: Extract LinkedIn credentials from the 'credentials' dict
        # We assume the Director/Token Manager has structured this dict after auth
        access_token = credentials.get("access_token")
        user_id = credentials.get("user_id")
        
        # 3. Instantiate the Tool with the LinkedIn credentials
        try:
            self.linkedin_tool = LinkedInTool(access_token, user_id)
        except ValueError as e:
            # Handle case where Director/TokenManager failed to provide necessary tokens
            self.available = False
            print(f"❌ LinkedIn Agent not initialized: {e}")
            return
            
        self.available = True

    def _analyze_query_to_json(self, user_query):
        """Ask the LLM to parse the user query into a structured LinkedIn action."""
        agent_prompt = (
            """You are an assistant for managing LinkedIn posts. Return a JSON with double quotes only. Supported actions:

- "generate": Generate a LinkedIn post from a topic. Required keys: "action", "topic"
- "post": Post the given content now. Required keys: "action", "content"
- "generate_and_post": Generate from topic and post immediately. Required keys: "action", "topic"
- "generate_and_schedule": Generate from topic and schedule a post. Required keys: "action", "topic", "time"
- "schedule": Schedule existing content. Required keys: "action", "content", "time"

The "time" key must be in "HH:MM" 24-hour format (e.g., "15:30").
Only return a valid JSON object. Do not explain.
"""
        )
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": agent_prompt},
                    {"role": "user", "content": user_query}
                ]
            )

            content = response.choices[0].message.content.strip()
            # Clean and parse JSON
            if content.startswith("```json"):
                content = content.replace("```json", "").strip()
            if content.endswith("```"):
                content = content[:-3].strip()
            
            return json.loads(content)
        except Exception:
            return {"error": "Invalid format returned by model."}


    def is_valid_time_format(self, t):
        return re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", t) is not None

    def pad_time_format(self, t):
        parts = t.strip().split(":")
        if len(parts) == 2:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:00"
        elif len(parts) == 3:
            return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}:{parts[2].zfill(2)}"
        return t

    def schedule_post(self, post_content, post_time):
        """Schedule the post at the specified time."""
        post_time = self.pad_time_format(post_time)

        if not self.is_valid_time_format(post_time):
            print("❌ Invalid time format. Please use HH:MM or HH:MM:SS (24h format).")
            return f"❌ Scheduling failed: Invalid time format {post_time}."

        def job():
            print(f"\n🕒 Time Reached: {datetime.now().strftime('%H:%M:%S')}")
            print("🚀 Posting now...")
            result = self.post_to_linkedin(post_content)
            print(result)
            
            # CRITICAL: Stop the scheduling loop once the job is done
            sys.exit(0) 

        try:
            schedule.every().day.at(post_time).do(job)
            return f"📅 Post scheduled for {post_time}. This process must remain running until posting time."
        except schedule.ScheduleValueError as e:
            return f"❌ Schedule Error: {e}"
        
        
    def handle_query(self, user_query):
        """Main handler to interpret user input and perform actions."""
        print("🧠 LinkedIn Agent received a query...")

        if not self.available:
            return "❌ LinkedIn service is unavailable due to missing credentials."
            
        task = self._analyze_query_to_json(user_query)

        if "error" in task:
            return f"Error analyzing request: {task['error']}"

        action = task.get("action")
        topic = task.get("topic")
        post_content = task.get("content")
        post_time = task.get("time")

        # --- Action Execution Logic ---
        if action == "generate":
            generated = self.generate_post_content(topic)
            # Since this is a head-less agent called by the Director, 
            # we should return the suggested post and ask the user to confirm/schedule in the main loop
            return f"Suggested Post (Ready for scheduling/posting):\n\n---\n{generated}\n\n---"
            
        elif action == "post":
            return self.post_to_linkedin(post_content)
            
        elif action == "generate_and_post":
            generated = self.generate_post_content(topic)
            return self.post_to_linkedin(generated)
            
        elif action == "generate_and_schedule":
            generated = self.generate_post_content(topic)
            return self.schedule_post(generated, post_time)
            
        elif action == "schedule":
            return self.schedule_post(post_content, post_time)
            
        else:
            return f"Unknown action: {action}"
        
    def generate_post_content(self, topic):
        """Generate a professional LinkedIn post using the OpenAI client."""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional LinkedIn content writer. Be inspiring, concise, and add emojis and 3-5 relevant hashtags."},
                {"role": "user", "content": f"Write an engaging LinkedIn post about my project: {topic}"}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()

    # 4. CRITICAL: Update API call to use the Tool
    def post_to_linkedin(self, content):
        """Post content directly to LinkedIn using the Tool."""
        return self.linkedin_tool.post_content(content)
        
    # 5. Handle Query and Action (This logic is mostly fine, but should check availability)
    def handle_query(self, user_query):
        if not self.available:
            return "❌ LinkedIn service is unavailable due to missing credentials."
            
        # ... (Rest of handle_query logic remains the same, but remove the old
        # post_to_linkedin helper functions and API calls)
        
        # NOTE: The scheduling logic in schedule_post is tightly coupled to the main script.
        # This is generally problematic in an interactive assistant, but for now, we leave it.