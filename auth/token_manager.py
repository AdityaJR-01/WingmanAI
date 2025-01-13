from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import logging

def _load_all_users() -> List[Dict]:
    """Loads the entire user list from users.json."""
    if os.path.exists("data/users.json"):
        try:
            with open("data/users.json", "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            logging.error("Error decoding users.json. File may be corrupted.")
            return []
    return []

def _save_all_users(users: List[Dict]):
    """Saves the entire user list back to users.json."""
    try:
        with open("data/users.json", "w") as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        logging.error(f"Error saving users.json: {e}")

# --- Core Token Management ---

def save_credentials(email: str, service: str, data: Dict[str, Any]):
    """Saves or updates a user's credentials for a specific service."""
    
    users = _load_all_users()
    
    # Find user or create new entry
    user_found = False
    for i, user in enumerate(users):
        if user["email"] == email:
            # Update existing user
            if "services" not in user:
                user["services"] = {}
            user["services"][service] = data
            users[i] = user
            user_found = True
            break
    
    if not user_found:
        # Create new user entry
        new_user = {
            "email": email,
            "services": {service: data}
        }
        users.append(new_user)
    
    _save_all_users(users)
    logging.info(f"✅ Credentials for service '{service}' saved/updated for {email}.")


def load_google_credentials(email: str) -> Credentials:
    """
    Loads Google credentials, performs refresh if necessary, and returns a 
    google.oauth2.credentials.Credentials object.
    """
    users = _load_all_users()
    
    user = next((u for u in users if u["email"] == email), None)
    if not user:
        raise ValueError(f"User {email} not found in user database.")
    
    # 1. Check for the 'google' service token data
    google_data = user.get("services", {}).get("google")
    if not google_data or not google_data.get("refresh_token"):
        raise ValueError(f"Google credentials not found for {email}.")

    # 2. Load OAuth client details from client_secret.json (needed for refresh)
    try:
        with open("config/client_secret.json", "r") as f:
            full_secrets = json.load(f) # Load the file ONCE
        
        # CRITICAL FIX: Check for the required keys in the loaded object
        client_data = full_secrets.get("installed") or full_secrets.get("web")

        if not client_data:
            raise KeyError("Google client secrets not found under 'installed' or 'web' key.")
            
    except FileNotFoundError:
        raise FileNotFoundError("config/client_secret.json not found, cannot refresh token.")
    except KeyError as e:
        raise KeyError(f"Client secret structure error during refresh: {e}") 
        
    # 3. Create Credentials object
    creds = Credentials(
        token=google_data.get("access_token"),
        refresh_token=google_data.get("refresh_token"),
        token_uri=client_data["token_uri"],
        client_id=client_data["client_id"],
        client_secret=client_data["client_secret"],
        scopes=google_data.get("scopes", [])
    )

    # 4. Refresh token if expired
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            
            # 5. Save the refreshed token data back to users.json
            google_data["access_token"] = creds.token
            google_data["expiry"] = creds.expiry.isoformat()
            
            _save_all_users(users)
            logging.info(f"🔄 Google token refreshed and saved for {email}.")
        except Exception as e:
            logging.error(f"❌ Failed to refresh Google token for {email}: {e}")
            raise RuntimeError("Failed to refresh Google credentials. Please re-run login.py.")
    
    return creds

def load_linkedin_tokens(email: str) -> Dict[str, Any]:
    """
    Loads LinkedIn token data, checks expiration if possible (optional), 
    and returns the raw dictionary.
    """
    users = _load_all_users()
    
    user = next((u for u in users if u["email"] == email), None)
    if not user:
        raise ValueError(f"User {email} not found in user database.")
    
    linkedin_data = user.get("services", {}).get("linkedin")
    
    if not linkedin_data or not linkedin_data.get("access_token"):
        raise ValueError(f"LinkedIn tokens not found for {email}.")
        
    # NOTE: LinkedIn's token refresh flow is often complex/manual. 
    # For now, we rely on the access token and assume it is good until expired_in runs out, 
    # but actual refresh logic should be handled by a dedicated function later if necessary.
    
    return linkedin_data

# --- Deprecated/Legacy Functions (for clean-up later) ---

def load_user_credentials(email):
    """(DEPRECATED) Legacy function now calling load_google_credentials."""
    return load_google_credentials(email) 

def has_scope(user_email, required_scope):
    """Checks if a user has authorized a specific Google scope."""
    users = _load_all_users()
    user = next((u for u in users if u["email"] == user_email), None)
    if not user:
        return False
        
    google_data = user.get("services", {}).get("google", {})
    return required_scope in google_data.get("scopes", [])