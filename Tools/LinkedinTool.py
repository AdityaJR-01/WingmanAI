import requests
import json
from typing import Dict, Any, Optional

class LinkedInTool:
    def __init__(self, access_token: str, user_id: str):
        """Initialize the tool with required credentials (access_token and user_id)."""
        if not access_token or not user_id:
            raise ValueError("LinkedIn access_token and user_id are required.")
            
        self.access_token = access_token
        self.user_id = user_id
        self.base_url = "https://api.linkedin.com/v2"

    def post_content(self, content: str) -> Dict:
        """Post content directly to LinkedIn's UGC API."""
        url = f"{self.base_url}/ugcPosts"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Content-Type": "application/json"
        }
        payload = {
            "author": f"urn:li:person:{self.user_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": content},
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }
        
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 201:
            return {"status": "success", "message": "Successfully posted on LinkedIn!"}
        else:
            try:
                error_details = response.json()
            except json.JSONDecodeError:
                error_details = {"message": response.text}
            
            return {"status": "error", "message": f"LinkedIn API Error ({response.status_code}): {error_details.get('message', 'Unknown Error')}"}