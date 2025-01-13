import os
from openai import OpenAI
from dotenv import load_dotenv
from Tools.WeatherTool import WeatherTool
from typing import Dict, Any
from google.oauth2.credentials import Credentials 


class WeatherAgent:
    # 1. CRITICAL: Add the standardized credentials argument
    def __init__(self, credentials: Credentials = None):
        # We ignore the credentials, as the agent doesn't need them.
        # But accepting them ensures Director.py doesn't crash on initialization.
        
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.weather_tool = WeatherTool()

        # system prompt
        self.system_prompt = """
            You are the Weather Agent of WingMan, a hyper-personalized assistant. You provide weather information in a helpful,
            friendly and concise manner.
            Include the relevant details such as the location, local time, temperature, humidity, cloud cover, precipitation, rain, and when relevant,
            add practical implications like (e.g., "Might want to use sunscreen" or "Stay hydrated" or "Might want to grab an umbrella").
            Present the information in a way that is conversational and engaging.
            """

    def check_location(self, user_query: str):
        """Analyze user query to determine location intent using a structured LLM response."""
        messages = [
            {
                "role": "system",
                "content": """
                You are WingMan's location analyzer. Your task is to extract the intended location from the user's query.
                
                ALWAYS return a single JSON object with these keys:
                "location_type": "current" OR "specific"
                "location_name": The exact city/area name mentioned (or null if location_type is "current").
                
                Example:
                User: "How's the weather in Seattle, Washington?"
                Output: {"location_type": "specific", "location_name": "Seattle, Washington"}
                
                User: "Is it going to rain today?"
                Output: {"location_type": "current", "location_name": null}
                """
            },
            {"role": "user", "content": user_query},
        ]

        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )

        try:
            # Clean and load JSON
            content = completion.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.strip("```json").strip("```").strip()
            
            data = json.loads(content)
            
            return {
                "current_location": data.get("location_type", "").lower() == "current",
                "location": data.get("location_name")
            }
        except Exception:
            # Fallback to current location on parsing error
            return {"current_location": True, "location": None}

    def format_weather_response(self, weather_data, location_data):
        """Generate a natural language response from weather data using GPT."""
        location_context = "your location" if location_data[
            "current_location"] else location_data["location"]

        # Add local time to the context
        local_time = weather_data.get("local_time", "")
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"Create a weather summary for {location_context} (Local time: {local_time}) based on this data: {weather_data}"
            }
        ]

        completion = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )

        return completion.choices[0].message.content

    def handle_query(self, user_query: str):
        """Handles user request by fetching and returning weather information."""
        try:
            # Step 1: Determine location type from user query
            location_data = self.check_location(user_query)
            
            # Debug print
            print(f"Debug - Location data: {location_data}")

            # Step 2: Get coordinates using WeatherTool
            location_coordinates = self.weather_tool.figure_out_location(location_data)
            
            # Debug print
            print(f"Debug - Coordinates: {location_coordinates}")

            if not location_coordinates:
                return "WingMan: I couldn't pinpoint that location. Could you please specify the city name more clearly?"

            # Step 3: Get weather data using coordinates
            weather_data = self.weather_tool.get_weather(
                latitude=location_coordinates["latitude"],
                longitude=location_coordinates["longitude"]
            )

            if "error" in weather_data:
                return f"WingMan: Oops! Ran into a snag: {weather_data['error']}"

            # Step 4: Format the response using GPT
            response = self.format_weather_response(weather_data, location_data)
            return f"WingMan: {response}"

        except Exception as e:
            return f"WingMan: System error: {str(e)}"