import requests
import geocoder
from geopy.geocoders import Nominatim
from typing import Optional, Dict, Union
from datetime import datetime
import pytz


class WeatherTool:
    def __init__(self):
        self.geolocator = Nominatim(user_agent="wingman_weather_agent")

    def figure_out_location(self, location_data: dict) -> Optional[Dict[str, float]]:
        """Determine coordinates based on whether current location is requested or a specific location is provided."""
        try:
            if location_data["current_location"]:
                return self.get_current_gps_coordinates()
            elif location_data.get("location"):
                return self.get_location_gps_coordinates(location_data["location"])
            return None
        except Exception as e:
            print(f"Error in figure_out_location: {e}")
            return None

    def get_current_gps_coordinates(self) -> Optional[Dict[str, float]]:
        """Get current location coordinates using IP geolocation."""
        try:
            g = geocoder.ip('me')
            if g.latlng:
                return {"latitude": g.latlng[0], "longitude": g.latlng[1]}
            print("Could not determine current location from IP")
            return None
        except Exception as e:
            print(f"Error fetching current location coordinates: {e}")
            return None

    def get_location_gps_coordinates(self, location_name: str) -> Optional[Dict[str, float]]:
        """Get coordinates for a specified location name."""
        try:
            # Add more specific location query
            location = self.geolocator.geocode(location_name, exactly_one=True, addressdetails=True)
            if location:
                return {"latitude": location.latitude, "longitude": location.longitude}
            print(f"Could not find coordinates for {location_name}")
            return None
        except Exception as e:
            print(f"Error fetching coordinates: {e}")
            return None

    def get_weather(self, latitude: float, longitude: float) -> Dict[str, Union[float, str]]:
        """Get weather data for provided GPS coordinates."""
        # Get timezone for the location
        timezone = self._get_timezone(latitude, longitude)
        
        # Add timezone and time parameters to the API call
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}&longitude={longitude}"
            f"&current=temperature_2m,cloudcover,precipitation,rain,relative_humidity_2m,wind_speed_10m,weather_code"
            f"&timezone={timezone}"
        )

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            if "current" in data:
                # Add local time to the response
                current_data = data["current"]
                current_data["local_time"] = datetime.now(pytz.timezone(timezone)).strftime("%I:%M %p")
                return current_data
            return {"error": "Unexpected API response format"}
        except requests.exceptions.RequestException as e:
            return {"error": f"Error fetching weather data: {e}"}

    def _get_timezone(self, latitude: float, longitude: float) -> str:
        """Get timezone string for given coordinates."""
        try:
            # First try to get timezone from Open-Meteo timezone API
            url = f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&timezone=auto"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            if "timezone" in data:
                return data["timezone"]
            
            # Fallback to UTC if timezone cannot be determined
            return "UTC"
        except:
            # Default to UTC in case of any error
            return "UTC"