import os
import requests
import json
import urllib.parse as urlparse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
import time
from typing import Dict, Any

def _load_linkedin_secrets():
    try:
        with open("config/client_secret.json", "r") as f:
            secrets = json.load(f)["linkedin"]
            return secrets
    except Exception as e:
        raise FileNotFoundError(f"Cannot load LinkedIn secrets from client_secret.json: {e}")

def get_linkedin_token_and_user_id(auth_code: str) -> Dict[str, Any]:
    
    secrets = _load_linkedin_secrets() # Load secrets centrally

    # 1. Access Token Exchange
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": secrets["redirect_uri"], # Use secret
        "client_id": secrets["client_id"],       # Use secret
        "client_secret": secrets["client_secret"] # Use secret
    }
    
    token_response = requests.post(token_url, data=data)
    token_data = token_response.json()
    
    if token_response.status_code != 200 or "access_token" not in token_data:
        raise Exception(f"Failed to get LinkedIn access token: {token_data.get('error_description', token_data)}")

    access_token = token_data["access_token"]
    
    # 2. Fetch User ID (from original Userinfo.py logic)
    userinfo_url = "https://api.linkedin.com/v2/userinfo"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Restli-Protocol-Version": "2.0.0"
    }
    
    user_response = requests.get(userinfo_url, headers=headers)
    user_data = user_response.json()
    
    if user_response.status_code != 200 or "sub" not in user_data:
        raise Exception(f"Failed to get LinkedIn user ID: {user_data}")
    
    # The 'sub' field in userinfo is the necessary User ID for the API
    user_id = user_data["sub"] 
    
    return {
        "access_token": access_token,
        "user_id": user_id,
        "expires_in": token_data.get("expires_in", 5184000) # Typically 60 days
    }


def login_linkedin_user() -> Dict[str, Any]:
    """Runs the Selenium OAuth flow to get the Authorization Code."""
    secrets = _load_linkedin_secrets()
    REDIRECT_URI = secrets["redirect_uri"]
    
    service = ChromeService(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)
    
    scope = "profile email w_member_social openid"
    auth_url = f"https://www.linkedin.com/oauth/v2/authorization?response_type=code&client_id={secrets['client_id']}&redirect_uri={secrets['redirect_uri']}&scope={scope}"
    
    driver.get(auth_url)
    print("🔹 WingMan opened the LinkedIn login page.")
    print("   Please log in and authorize the app in the browser.")
    
    # Wait for manual authorization (using a large loop to continuously check the URL)
    max_wait_time = 120 # Wait for 2 minutes
    start_time = time.time()
    auth_code = None

    while time.time() - start_time < max_wait_time:
        time.sleep(1)
        redirected_url = driver.current_url
        if redirected_url.startswith(REDIRECT_URI):
            parsed_url = urlparse.urlparse(redirected_url)
            auth_code = urlparse.parse_qs(parsed_url.query).get("code", [None])[0]
            if auth_code:
                print("\n✅ Authorization Code captured!")
                break
    
    driver.quit()
    
    if not auth_code:
        raise Exception("LinkedIn authorization failed: Timed out or code not found.")
        
    return get_linkedin_token_and_user_id(auth_code)