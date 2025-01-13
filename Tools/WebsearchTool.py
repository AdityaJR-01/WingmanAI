import os
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

class WebSearchTool:
    def __init__(self):
        # 1. Load keys from JSON
        try:
            with open("config/client_secret.json", "r") as f:
                secrets = json.load(f)
                self.api_key = secrets.get("tavily", {}).get("api_key")
        except FileNotFoundError:
            self.api_key = None
            
        # 2. Set availability based on the key
        self.available = bool(self.api_key) 
        if not self.available:
            print("⚠️ WARNING: TAVILY API key missing from client_secret.json. Web search disabled.")
            
        self.base_url = "https://api.tavily.com/search"

    def search(self, query: str, search_depth: str = "basic") -> Dict:
        if not self.available:
            return {"error": "TAVILY_API_KEY is not configured.", "results": []}
        
        """
        Perform a web search using Tavily API.
        
        Args:
            query (str): Search query
            search_depth (str): 'basic' or 'deep' search (affects response time and detail)
        
        Returns:
            Dict containing search results and metadata
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "query": query,
                "search_depth": search_depth,
                "include_images": False,
                "include_answer": True,
                "max_results": 5,
                "api_key": self.api_key
            }
            
            response = requests.post(
                self.base_url,
                headers=headers,
                json=data
            )
            
            print(f"Debug - API response status: {response.status_code}")
            print(f"Debug - Response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                print(f"Debug - Error response body: {response.text}")
                
            response.raise_for_status()
            result = response.json()
            
            if result.get("answer"):
                print(f"Debug - Search result: {result['answer'][:100]}...")
            else:
                print("Debug - No direct answer in response")
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"Search error: {str(e)}")
            if hasattr(e.response, 'text'):
                print(f"Error response: {e.response.text}")
            return {
                "error": f"Search failed: {str(e)}",
                "results": []
            }
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            return {
                "error": f"Unexpected error: {str(e)}",
                "results": []
            }

    def get_quick_answer(self, query: str) -> Dict:
        """
        Get a quick answer for simple queries.
        
        Args:
            query (str): Search query
        
        Returns:
            Dict containing the answer and source
        """
        try:
            result = self.search(query, search_depth="basic")
            
            if "answer" in result and result["answer"]:
                return {
                    "answer": result["answer"],
                    "source": result.get("results", [{}])[0].get("url", "Unknown source")
                }
            
            if result.get("results"):
                first_result = result["results"][0]
                return {
                    "answer": first_result.get("snippet", "No direct answer available"),
                    "source": first_result.get("url", "Unknown source")
                }
            
            return {
                "answer": None,
                "source": None,
                "error": "No quick answer available"
            }
            
        except Exception as e:
            print(f"Quick answer error: {str(e)}")
            return {
                "answer": None,
                "source": None,
                "error": f"Quick answer failed: {str(e)}"
            }

    def get_detailed_search(self, query: str) -> Dict:
        """
        Perform a detailed search for complex queries.
        
        Args:
            query (str): Search query
        
        Returns:
            Dict containing detailed search results
        """
        try:
            result = self.search(query, search_depth="deep")
            
            if "results" in result and result["results"]:
                return {
                    "results": result["results"],
                    "answer": result.get("answer"),
                    "topic": query
                }
            
            return {
                "error": "No results found",
                "results": []
            }
            
        except Exception as e:
            print(f"Detailed search error: {str(e)}")
            return {
                "error": f"Detailed search failed: {str(e)}",
                "results": []
            } 